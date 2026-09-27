"""
OoCommandRouter — prefix-based command dispatch with cooldowns and tiers.
"""

import logging
import time
from typing import Callable, Awaitable

log = logging.getLogger('oo.commands')

PREFIX = '.'

_ALIASES = {
    'h':         'help',
    'commands':  'help',
    'osrs':      'osrs',
    'rs':        'osrs',
    'mods':      'mod',
    'rules':     'mod rules',
    'report':    'report',
}


class OoCommandRouter:

    def __init__(self, identity):
        self._identity = identity
        self._handlers: dict[str, dict] = {}
        self._cooldowns: dict[str, float] = {}  # f"{nick}:{cmd}" → last_called_ts

    def register(self, names: str | list[str], handler: Callable,
                 tier: str = 'user', cooldown_ms: int = 3000):
        if isinstance(names, str):
            names = [names]
        for name in names:
            self._handlers[name.lower()] = {
                'handler':     handler,
                'tier':        tier,
                'cooldown_ms': cooldown_ms,
            }

    async def dispatch(self, room: str, nick: str, text: str,
                       handle: str = '') -> bool:
        """Returns True if a command was matched (even if denied)."""
        stripped = text.strip()
        if not stripped.startswith(PREFIX):
            return False

        raw = stripped[len(PREFIX):].strip()
        parts = raw.split()
        if not parts:
            return False

        # Support two-word commands like ".mod rules"
        cmd = None
        args = []
        if len(parts) >= 2:
            two = f'{parts[0].lower()} {parts[1].lower()}'
            if two in self._handlers:
                cmd, args = two, parts[2:]
        if cmd is None:
            cmd_key = _ALIASES.get(parts[0].lower(), parts[0].lower())
            if cmd_key in self._handlers:
                cmd, args = cmd_key, parts[1:]

        if cmd is None:
            return False

        entry = self._handlers[cmd]
        tier  = entry['tier']
        role  = self._identity.get_role(nick, handle)

        if tier == 'owner' and role != 'owner':
            return True  # silently ignore non-owners
        if tier == 'mod' and role not in ('owner', 'mod'):
            return True

        # Cooldown check (owners bypass)
        if role not in ('owner', 'mod'):
            cd_key = f'{nick.lower()}:{cmd}'
            last   = self._cooldowns.get(cd_key, 0)
            now    = time.monotonic() * 1000
            if now - last < entry['cooldown_ms']:
                return True
            self._cooldowns[cd_key] = now

        try:
            result = await entry['handler'](room, nick, handle, args)
            return True, result
        except Exception as e:
            log.error(f'[Commands] Error in .{cmd}: {e}', exc_info=True)
            return True, None

    def list_commands(self, role: str = 'user') -> list[str]:
        tiers = {'user': {'user'}, 'mod': {'user', 'mod'}, 'owner': {'user', 'mod', 'owner'}}
        allowed = tiers.get(role, {'user'})
        return [f'{PREFIX}{name}' for name, e in self._handlers.items()
                if e['tier'] in allowed]
