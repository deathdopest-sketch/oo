"""
OoActions — execute moderation actions via the platform adapter.
"""

import asyncio
import logging

log = logging.getLogger('oo.mod.actions')


class OoActions:

    def __init__(self, platform, watchlist, mod_log, queue):
        self._platform  = platform   # dict of platform_name → OoPlatform
        self._watchlist = watchlist
        self._log       = mod_log
        self._queue     = queue
        self._shadow_blocked: set[str] = set()  # usernames shadow-banned

    async def execute(self, action: str, room: str, username: str,
                      rule_id: str = '', reason: str = '',
                      duration_sec: int = 300, platform_name: str = ''):
        plat = self._get_platform(platform_name)
        self._log.record(action, username, room, rule_id, reason)
        self._watchlist.add_strike(username, rule_id, action)

        if action == 'warn':
            await self._warn(plat, room, username, reason)

        elif action == 'delete':
            pass  # handled by caller with message_id

        elif action == 'delete_and_warn':
            await self._warn(plat, room, username, reason)

        elif action == 'mute':
            self._watchlist.set_muted(username, duration_sec)
            if plat:
                await plat.mute(room, username, duration_sec)

        elif action == 'timeout':
            self._watchlist.set_muted(username, duration_sec)
            if plat:
                await plat.mute(room, username, duration_sec)

        elif action == 'kick':
            if plat:
                await plat.kick(room, username, reason)

        elif action == 'ban':
            self._watchlist.set_banned(username, reason)
            if plat:
                await plat.ban(room, username, reason)

        elif action == 'shadow_ban':
            self._shadow_blocked.add(username.lower())

        elif action == 'log_only':
            pass

        log.info(f'[Mod] {action.upper()} {username} in {room} [{rule_id}]')

    def is_shadow_banned(self, username: str) -> bool:
        return username.lower() in self._shadow_blocked

    async def manual_warn(self, room: str, username: str, reason: str,
                          moderator: str, platform_name: str = ''):
        plat = self._get_platform(platform_name)
        self._log.record('warn', username, room, reason=reason, moderator=moderator)
        await self._warn(plat, room, username, reason)

    async def manual_mute(self, room: str, username: str, minutes: int,
                           moderator: str, platform_name: str = ''):
        plat = self._get_platform(platform_name)
        secs = minutes * 60
        self._watchlist.set_muted(username, secs)
        self._log.record('mute', username, room, reason=f'{minutes}m', moderator=moderator)
        if plat:
            await plat.mute(room, username, secs)

    async def manual_kick(self, room: str, username: str, reason: str,
                           moderator: str, platform_name: str = ''):
        plat = self._get_platform(platform_name)
        self._log.record('kick', username, room, reason=reason, moderator=moderator)
        if plat:
            await plat.kick(room, username, reason)

    async def manual_ban(self, room: str, username: str, reason: str,
                          moderator: str, platform_name: str = ''):
        plat = self._get_platform(platform_name)
        self._watchlist.set_banned(username, reason)
        self._log.record('ban', username, room, reason=reason, moderator=moderator)
        if plat:
            await plat.ban(room, username, reason)

    async def manual_unban(self, room: str, username: str, moderator: str,
                            platform_name: str = ''):
        plat = self._get_platform(platform_name)
        self._watchlist.unban(username)
        self._log.record('unban', username, room, moderator=moderator)
        if plat:
            await plat.unmute(room, username)

    async def _warn(self, plat, room: str, username: str, reason: str):
        msg = f'{username}: {reason}' if reason else f'{username}: watch it'
        await self._queue.enqueue(room, msg)

    def _get_platform(self, name: str):
        if not self._platform:
            return None
        if name and name in self._platform:
            return self._platform[name]
        return next(iter(self._platform.values()), None)
