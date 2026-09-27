"""
OoInterbotGuard — bot loop detection and prevention.
"""

import re
import time
from collections import defaultdict

_BOT_PATTERNS = re.compile(
    r'^(bot|zomb|spackle|lilly|reap|oo|system|demonika|deathdoll)\b|'
    r'\b(bot|ai)$', re.I
)
_MSG_PATTERNS = re.compile(r'^\[.*\]:|^!|\.\.\. loading|^—{3,}', re.I)
_WINDOW_S      = 180
_THRESHOLD     = 4
_FAST_REPLY_MS = 800


class OoInterbotGuard:

    def __init__(self):
        self._scores:   dict[str, float]       = {}  # nick.lower() → score
        self._history:  dict[str, list]        = defaultdict(list)  # room:nick → timestamps
        self._response: dict[str, list[float]] = defaultdict(list)  # room:nick → our reply times

    def register_bot(self, nick: str):
        self._scores[nick.lower()] = 5.0

    def is_bot(self, nick: str) -> bool:
        n = nick.lower()
        score = self._scores.get(n, 0)
        if score >= 3:
            return True
        if _BOT_PATTERNS.match(nick):
            return True
        return False

    def on_message(self, room: str, nick: str, text: str):
        n   = nick.lower()
        key = f'{room}:{n}'
        now = time.monotonic()

        # Check fast replies
        self._history[key].append(now)
        self._history[key] = [t for t in self._history[key] if now - t < _WINDOW_S]

        # Score heuristics
        if _BOT_PATTERNS.match(nick):
            self._scores[n] = self._scores.get(n, 0) + 2
        if _MSG_PATTERNS.match(text):
            self._scores[n] = self._scores.get(n, 0) + 1
        if len(text) > 500:
            self._scores[n] = self._scores.get(n, 0) + 0.5

    def on_bot_response(self, room: str, nick: str):
        key = f'{room}:{nick.lower()}'
        self._response[key].append(time.monotonic())

    def should_block(self, room: str, nick: str) -> bool:
        if not self.is_bot(nick):
            return False
        key   = f'{room}:{nick.lower()}'
        now   = time.monotonic()
        replies = [t for t in self._response[key] if now - t < _WINDOW_S]
        return len(replies) >= _THRESHOLD
