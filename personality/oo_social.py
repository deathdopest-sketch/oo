"""
OoSocial — room intel and group dynamics observer.
Tracks who's active, mood of room, dominant voices.
"""

import time
from collections import deque


class _UserObs:
    __slots__ = ('nick', 'messages', 'last_seen', 'recent_texts')

    def __init__(self, nick: str):
        self.nick         = nick
        self.messages     = 0
        self.last_seen    = time.time()
        self.recent_texts = deque(maxlen=5)


class OoSocial:

    def __init__(self):
        self._rooms: dict[str, dict[str, _UserObs]] = {}
        self._room_hist: dict[str, deque] = {}

    def observe(self, room: str, nick: str, handle: str, text: str):
        room = room.lower()
        users = self._rooms.setdefault(room, {})
        key   = handle or nick.lower()
        obs   = users.get(key)
        if obs is None:
            obs = _UserObs(nick)
            users[key] = obs
        obs.nick      = nick
        obs.messages += 1
        obs.last_seen = time.time()
        obs.recent_texts.append(text)

        hist = self._room_hist.setdefault(room, deque(maxlen=15))
        hist.append({'nick': nick, 'text': text})

    def get_room_intel(self, room: str, my_handle: str = '') -> str:
        room  = room.lower()
        users = self._rooms.get(room, {})
        now   = time.time()
        active = [o for o in users.values() if now - o.last_seen < 600]
        if not active:
            return ''

        top = sorted(active, key=lambda o: -o.messages)[:3]
        top_names = ', '.join(o.nick for o in top)
        total = len(active)
        return f'[Room: {total} active. Most vocal: {top_names}]'

    def get_group_dynamic(self, room: str) -> str:
        hist = list(self._room_hist.get(room.lower(), []))
        if len(hist) < 3:
            return ''
        nicks = [m['nick'] for m in hist[-10:]]
        dominant = max(set(nicks), key=nicks.count) if nicks else ''
        energy = 'active' if len(set(nicks)) > 3 else 'quiet'
        return f'[Dynamic: {energy} room, {dominant} driving lately]' if dominant else ''
