"""
OoBot — main orchestrator. Wires all modules together.
"""

import asyncio
import logging
import os
import random
import time

from platform.base import OoPlatform
from core.identity import OoIdentity
from core.commands import OoCommandRouter
from core.queue import OoQueue
from ai.oo_ollama import OoOllama
from ai.oo_groq import OoGroq
from ai.oo_context import OoContext
from ai.oo_memory import OoMemory
from ai.oo_relationship import OoRelationship
from personality.oo_persona import OoPersona, build_system_prompt
from personality.oo_psych import analyze
from personality.oo_mood import OoMood
from personality.oo_nemesis import OoNemesis
from personality.oo_social import OoSocial
from personality.oo_drift import OoDrift
from moderation.oo_rules import OoRules
from moderation.oo_watchlist import OoWatchlist
from moderation.oo_log import OoLog
from moderation.oo_actions import OoActions
from moderation.oo_engine import OoEngine
from moderation.oo_reports import OoReports
from companion.oo_osrs import OoOsrs
from companion.oo_site_watch import OoSiteWatch
from music.oo_music import OoMusic, OoMusicDropper
from features.oo_interbot_guard import OoInterbotGuard
from features.oo_nick_cycle import OoNickCycle
import storage as store
from tools import load_tools

log = logging.getLogger('oo.bot')

_AI_RESPONSE_CHANCE = 0.7   # % of non-commanded messages that get an AI reply


class OoBot:

    def __init__(self):
        self.nick     = os.environ.get('OO_BOT_NICK', 'ó_ò')
        self.platforms: dict[str, OoPlatform] = {}
        self.rooms:     dict[str, set]  = {}  # room → set of nicks

        # Core
        self.identity = OoIdentity()
        self.commands = OoCommandRouter(self.identity)
        self.queue    = OoQueue()

        # AI
        self.ollama  = OoOllama()
        self.groq    = OoGroq()
        self.context = OoContext()
        self.memory  = None  # built in start() after ollama is ready
        self.relship = OoRelationship()

        # Personality
        self.persona = OoPersona()
        self.mood    = OoMood()
        self.nemesis = OoNemesis()
        self.social  = OoSocial()
        self.drift   = OoDrift()

        # Moderation
        self.rules     = OoRules()
        self.watchlist = OoWatchlist()
        self.mod_log   = OoLog()
        self.mod_acts  = None   # built after platforms are set
        self.mod_engine = None
        self.reports   = OoReports()

        # Companion
        self._osrs     = None
        self._site_watch = None

        # Music
        self.music    = OoMusic()
        self._dropper = None

        # Features
        self.ibguard  = OoInterbotGuard()
        self._nick_cycle = None

    async def start(self):
        log.info(f'[OoBot] Starting {self.nick}')

        # Storage init
        await store.init()
        await store.restore_from_pg()

        # AI
        await self.ollama.init()
        await self.groq.init()
        self.memory = OoMemory(self.ollama)

        # Music
        self.music.load()
        log.info(f'[OoBot] Music: {self.music.total_tracks()} tracks loaded')

        # Moderation wiring (platforms must be set before this)
        self.mod_acts = OoActions(self.platforms, self.watchlist, self.mod_log, self.queue)
        self.mod_engine = OoEngine(self.rules, self.mod_acts, self.watchlist, self.identity)

        # Companions
        cc_rooms = list(self.rooms.keys())
        self._osrs = OoOsrs(self.queue, cc_rooms)
        self._site_watch = OoSiteWatch(self.platforms, self.queue)
        self._dropper = OoMusicDropper(self.music, self.queue, cc_rooms)

        # Tools
        tools = load_tools()
        for name, tool in tools.items():
            t = tool
            async def _handler(room, nick, handle, args, _t=t):
                ctx = {'room': room, 'nick': nick, 'handle': handle, 'bot': self}
                return await _t.run(args, ctx)
            self.commands.register(
                name, _handler,
                tier=tool.tier, cooldown_ms=tool.cooldown_ms,
            )

        # Register built-in commands
        self._register_commands()

        # Queue
        self.queue.set_send_fn(self._route_send)
        await self.queue.start()

        # Start companions + dropper
        await self._osrs.start()
        await self._site_watch.start()
        await self._dropper.start()

        # Auto-save every 60s
        asyncio.ensure_future(self._auto_save())

        # Nick cycle (if platform supports it)
        self._nick_cycle = OoNickCycle(
            self.ollama, self._set_nick, default_nick=self.nick
        )
        self._nick_cycle.start()

        # Wire platform callbacks
        for name, plat in self.platforms.items():
            self._wire_platform(name, plat)
            await plat.connect()
            for room in self._rooms_for_platform(name):
                await plat.join_room(room)

        log.info(f'[OoBot] Ready')

    async def stop(self):
        await self.queue.stop()
        if self._nick_cycle:
            self._nick_cycle.stop()
        for plat in self.platforms.values():
            await plat.disconnect()
        store.backup()
        log.info('[OoBot] Stopped')

    # ── Platform wiring ────────────────────────────────────────────────────────

    def add_platform(self, name: str, platform: OoPlatform):
        self.platforms[name] = platform

    def _wire_platform(self, plat_name: str, plat: OoPlatform):
        plat.on_message     = lambda r, n, t, h: asyncio.ensure_future(
            self._on_message(r, n, t, h, plat_name))
        plat.on_join        = lambda r, n, h, u, m: self._on_join(r, n, h, u, m)
        plat.on_joined      = lambda r, n, h, u: self._on_joined(r, n, h, u)
        plat.on_leave       = lambda r, n, h: self._on_leave(r, n, h)
        plat.on_nick_change = lambda r, o, nw, h: self._on_nick_change(r, o, nw, h)
        plat.on_reconnected = lambda r: log.info(f'[{plat_name}] Reconnected to {r}')
        plat.on_pm          = lambda n, h, t: asyncio.ensure_future(
            self._on_pm(n, h, t, plat_name))

    def _rooms_for_platform(self, plat_name: str) -> list[str]:
        if plat_name == 'chatcommon':
            return [r.strip() for r in os.environ.get('CHATCOMMON_ROOMS', '').split(',') if r.strip()]
        if plat_name == 'mumblechat':
            return [r.strip() for r in os.environ.get('MUMBLECHAT_ROOMS', '').split(',') if r.strip()]
        return []

    async def _route_send(self, room: str, text: str):
        for plat in self.platforms.values():
            try:
                await plat.send(room, text)
                return
            except Exception:
                continue

    async def _set_nick(self, nick: str):
        pass  # platform-specific nick change — override per deployment if needed

    # ── Event handlers ─────────────────────────────────────────────────────────

    async def _on_message(self, room: str, nick: str, text: str,
                           handle: str, plat_name: str = ''):
        if not text.strip():
            return

        self.identity.register(room, nick, handle)
        self.social.observe(room, nick, handle, text)
        self.relship.observe(room, nick, handle, text)
        if self.memory:
            self.memory.add(room, nick, text)

        ps = analyze(text, self.nick)
        self.drift.log_emotion(ps.emotion)
        self.drift.log_active(len(text.split()))

        self.ibguard.on_message(room, nick, text)
        if self.ibguard.is_bot(nick) and self.ibguard.should_block(room, nick):
            return

        actioned = await self.mod_engine.evaluate(room, nick, handle, text,
                                                   platform_name=plat_name)
        if actioned:
            self._site_watch.on_mod_action(room)
            return

        result = await self.commands.dispatch(room, nick, text, handle)
        if result:
            matched, reply = (result if isinstance(result, tuple) else (result, None))
            if matched and reply:
                self.context.add_bot(room, reply)
                await self.queue.enqueue(room, reply)
            return

        if self._osrs and self._osrs.is_osrs_message(text):
            reaction = self._osrs.get_reaction(text)
            if reaction and random.random() < 0.5:
                await self.queue.enqueue(room, reaction)
                return

        counter = self.nemesis.check(room, nick, text)
        if counter and random.random() < 0.6:
            await asyncio.sleep(0.8 + random.random() * 1.2)
            await self.queue.enqueue(room, counter)
            return

        if not ps.is_directed and random.random() > _AI_RESPONSE_CHANCE:
            return

        reply = await self._ai_reply(room, nick, text, handle, ps)
        if reply:
            self.context.add_user(room, nick, text)
            self.context.add_bot(room, reply)
            self.nemesis.record_response(room, nick)
            await asyncio.sleep(0.5 + random.random() * 1.5)
            await self.queue.enqueue(room, reply)

    async def _ai_reply(self, room: str, nick: str, text: str,
                         handle: str, psych) -> str | None:
        ctx_data = {
            'room': room, 'nick': nick, 'handle': handle, 'bot_nick': self.nick
        }
        proc     = self.persona.process(text, ctx_data)

        if proc.get('acronym_reply'):
            return proc['acronym_reply']

        if proc['psych'].bot_callout:
            return self.persona.bot_deflection()

        mood_state  = self.mood.get()
        rel_signals = self.relship.get_signals(room, handle)
        room_intel  = self.social.get_room_intel(room)
        drift_hint  = self.drift.get_hint()
        summary_ctx = ''
        summaries   = self.memory.get_summaries(room) if self.memory else []
        if summaries:
            last = summaries[-1]
            summary_ctx = f'\n[Earlier: {last["text"]}]'

        mode_hint = (
            f'{proc["mode_hint"]}\n'
            f'{mood_state.hint}\n'
            f'{rel_signals.line}'
            f'{summary_ctx}'
        )
        if drift_hint:
            mode_hint += f'\n{drift_hint}'
        if room_intel:
            mode_hint += f'\n{room_intel}'

        system = build_system_prompt(self.nick, room, mode_hint)

        messages = self.context.get_messages(room, system)
        messages.append({'role': 'user', 'content': f'{nick}: {text}'})

        llm_opts = {**mood_state.profile}
        llm_opts['num_predict'] = proc.get('num_predict', 80)
        llm_opts['temperature'] = proc.get('temperature', 0.88)

        reply = await self.ollama.chat(messages, **llm_opts)
        if not reply and self.groq.available:
            reply = await self.groq.chat(messages, max_tokens=llm_opts['num_predict'])

        return reply

    def _on_join(self, room: str, nick: str, handle: str, username: str, mod: int):
        self.rooms.setdefault(room.lower(), set()).add(nick)
        self.identity.register(room, nick, handle)
        self._site_watch.on_user_join(room, nick)

    def _on_joined(self, room: str, nick: str, handle: str, username: str):
        self.rooms.setdefault(room.lower(), set())
        log.info(f'[OoBot] Joined room: {room}')
        greeting = self.persona.greeting()
        if greeting:
            asyncio.ensure_future(self._delayed_send(room, greeting, 1.2))

    def _on_leave(self, room: str, nick: str, handle: str):
        self.rooms.get(room.lower(), set()).discard(nick)
        self._site_watch.on_user_leave(room, nick)

    def _on_nick_change(self, room: str, old: str, new: str, handle: str):
        r = self.rooms.get(room.lower(), set())
        r.discard(old)
        r.add(new)
        self.identity.register(room, new, handle)

    async def _on_pm(self, from_nick: str, from_handle: str, text: str, plat_name: str):
        if not text.strip():
            return
        dm_room = f'_dm_{from_nick.lower()}'
        self.rooms.setdefault(dm_room, set())
        reply = await self._ai_reply(
            dm_room, from_nick, text, from_handle,
            analyze(text, self.nick)
        )
        if reply:
            plat = self.platforms.get(plat_name) or next(iter(self.platforms.values()), None)
            if plat:
                await plat.send_pm(from_nick, reply, from_handle)

    async def _delayed_send(self, room: str, text: str, delay: float):
        await asyncio.sleep(delay)
        await self.queue.enqueue(room, text)

    # ── Built-in commands ─────────────────────────────────────────────────────

    def _register_commands(self):
        cmds = self.commands

        async def cmd_help(room, nick, handle, args):
            role  = self.identity.get_role(nick, handle)
            lines = self.commands.list_commands(role)
            return 'commands: ' + '  '.join(lines)

        async def cmd_mod(room, nick, handle, args):
            if not args:
                return '.mod rules | enable/disable <id> | set <id> <field> <val> | warn/mute/kick/ban/unban <nick> | watchlist | log | reports | exempt <nick>'
            sub = args[0].lower()

            if sub == 'rules':
                return self.rules.format_rules()

            if sub == 'enable' and len(args) >= 2:
                ok = self.rules.enable(args[1])
                return f'enabled {args[1]}' if ok else f'unknown rule: {args[1]}'

            if sub == 'disable' and len(args) >= 2:
                ok = self.rules.disable(args[1])
                return f'disabled {args[1]}' if ok else f'unknown rule: {args[1]}'

            if sub == 'set' and len(args) >= 4:
                ok = self.rules.set_field(args[1], args[2], args[3])
                return f'updated {args[1]}.{args[2]} = {args[3]}' if ok else 'failed'

            if sub in ('warn', 'mute', 'kick', 'ban', 'unban') and len(args) >= 2:
                target = args[1]
                reason = ' '.join(args[2:]) if len(args) > 2 else ''
                plat_name = next(iter(self.platforms), '')
                if sub == 'warn':
                    await self.mod_acts.manual_warn(room, target, reason, nick, plat_name)
                elif sub == 'mute':
                    mins = int(args[2]) if len(args) > 2 and args[2].isdigit() else 30
                    await self.mod_acts.manual_mute(room, target, mins, nick, plat_name)
                elif sub == 'kick':
                    await self.mod_acts.manual_kick(room, target, reason, nick, plat_name)
                elif sub == 'ban':
                    await self.mod_acts.manual_ban(room, target, reason, nick, plat_name)
                elif sub == 'unban':
                    await self.mod_acts.manual_unban(room, target, nick, plat_name)
                return f'{sub}: {target}'

            if sub == 'watchlist':
                users = self.watchlist.get_active_users()
                if not users:
                    return 'watchlist is clear'
                lines = [f'{u["username"]}: {u["strikes"]} strikes' for u in users[:10]]
                return '\n'.join(lines)

            if sub == 'log':
                n = int(args[1]) if len(args) > 1 and args[1].isdigit() else 10
                entries = self.mod_log.get_recent(n)
                return '\n'.join(self.mod_log.format_entry(e) for e in entries) or 'no log entries'

            if sub == 'reports':
                return self.reports.format_reports()

            if sub == 'exempt' and len(args) >= 2:
                self.identity.add_session_exempt(args[1])
                return f'exempted {args[1]} for this session'

            return 'unknown mod subcommand'

        async def cmd_report(room, nick, handle, args):
            if not args:
                return 'usage: .report <nick> [reason]'
            target = args[0]
            reason = ' '.join(args[1:]) if len(args) > 1 else 'no reason given'
            self.reports.add(nick, target, reason, room)
            return f'report logged for {target}'

        async def cmd_music(room, nick, handle, args):
            genre = args[0].lower() if args else None
            track = self.music.get_genre(genre) if genre else self.music.get_random()
            if not track:
                return 'nothing in the bins'
            return self.music.format_drop(track)

        async def cmd_osrs_goal(room, nick, handle, args):
            if self._osrs:
                return self._osrs.current_goal()
            return 'not sure what I\'m grinding rn'

        cmds.register('help',     cmd_help,       tier='user',  cooldown_ms=5000)
        cmds.register('mod',      cmd_mod,        tier='owner', cooldown_ms=0)
        cmds.register('report',   cmd_report,     tier='user',  cooldown_ms=10000)
        cmds.register(['music', 'play'], cmd_music, tier='user', cooldown_ms=15000)
        cmds.register('goal',     cmd_osrs_goal,  tier='user',  cooldown_ms=10000)

    # ── Auto-save ─────────────────────────────────────────────────────────────

    async def _auto_save(self):
        while True:
            await asyncio.sleep(60)
            self.relship.save()
            if self.memory:
                self.memory.save()
            self.drift._save()
