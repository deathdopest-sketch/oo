"""
OoIdentity — owner/mod detection and handle→nick tracking.
"""

import os
from typing import Optional


class OoIdentity:

    def __init__(self):
        owner_usr  = os.environ.get('OO_OWNER_USERNAME', '').strip().lower()
        owner_nicks = [n.strip().lower() for n in
                       os.environ.get('OO_OWNER_NICKS', owner_usr).split(',') if n.strip()]
        mod_nicks  = [n.strip().lower() for n in
                      os.environ.get('OO_MOD_NICKS', '').split(',') if n.strip()]

        self._owner_usr   = owner_usr
        self._owner_nicks = set(owner_nicks)
        self._mod_nicks   = set(mod_nicks)

        # Runtime additions (e.g. .mod exempt)
        self._session_exempt: set[str] = set()

        # handle → nick cache  (str → str)
        self._handle_nick: dict[str, str] = {}
        # nick → handle cache  (room:nick.lower() → handle)
        self._nick_handle: dict[str, str] = {}

    # ── Role checks ───────────────────────────────────────────────────────────

    def is_owner(self, nick: str, handle: str = '') -> bool:
        n = nick.lower()
        return (n in self._owner_nicks or
                (handle and handle.lower() in self._owner_nicks) or
                n == self._owner_usr)

    def is_mod(self, nick: str, handle: str = '') -> bool:
        return self.is_owner(nick, handle) or nick.lower() in self._mod_nicks

    def is_exempt(self, nick: str) -> bool:
        return self.is_mod(nick) or nick.lower() in self._session_exempt

    def add_session_exempt(self, nick: str):
        self._session_exempt.add(nick.lower())

    def add_mod(self, nick: str):
        self._mod_nicks.add(nick.lower())

    def remove_mod(self, nick: str):
        self._mod_nicks.discard(nick.lower())

    # ── Handle/nick tracking ──────────────────────────────────────────────────

    def register(self, room: str, nick: str, handle: str):
        if handle:
            self._handle_nick[handle] = nick
        if nick:
            self._nick_handle[f'{room.lower()}:{nick.lower()}'] = handle

    def handle_for(self, room: str, nick: str) -> Optional[str]:
        return self._nick_handle.get(f'{room.lower()}:{nick.lower()}')

    def nick_for(self, handle: str) -> Optional[str]:
        return self._handle_nick.get(handle)

    def get_role(self, nick: str, handle: str = '') -> str:
        if self.is_owner(nick, handle):
            return 'owner'
        if self.is_mod(nick, handle):
            return 'mod'
        return 'user'
