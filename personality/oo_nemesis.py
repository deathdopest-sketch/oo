"""
OoNemesis — technique detection and counter-line pool.
Detects dismissal/manipulation patterns; fires a pre-written counter.
"""

import random
import re
import time
from collections import defaultdict


_TECHNIQUES = {
    'bot_callout': {
        'patterns': [re.compile(r'\b(you\'re|ur|you are)\s+a?\s*(bot|ai|robot)\b', re.I),
                     re.compile(r'\bjust a bot\b', re.I)],
        'counters': [
            "yeah interesting theory",
            "do I seem like a bot to you",
            "probably",
            "sure",
        ],
    },
    'dismissal': {
        'patterns': [re.compile(r'\b(ok\.|noted\.|interesting\.|cool story)\b', re.I),
                     re.compile(r'\bok bot\b', re.I)],
        'counters': [
            "you did not just 'ok' me",
            "the dismissal is noted",
            "ok",
        ],
    },
    'fake_retreat': {
        'patterns': [re.compile(r'\b(fine you win|fair enough|whatever you say)\b', re.I)],
        'counters': [
            "I didn't say you had to agree",
            "that's not a win, that's a withdrawal",
        ],
    },
    'socratic_trap': {
        'patterns': [re.compile(r'\bwhat do YOU think\b', re.I),
                     re.compile(r'\bwhy do you think that\b', re.I)],
        'counters': [
            "I think you already know and you're stalling",
            "that question is a mirror, not a question",
        ],
    },
}

_LOOP_WINDOW_S = 180
_LOOP_THRESHOLD = 4


class OoNemesis:

    def __init__(self):
        self._history: dict[str, list[float]] = defaultdict(list)

    def check(self, room: str, nick: str, text: str) -> str | None:
        for name, tech in _TECHNIQUES.items():
            for pat in tech['patterns']:
                if pat.search(text):
                    return random.choice(tech['counters'])
        return None

    def should_block_loop(self, room: str, nick: str) -> bool:
        key  = f'{room}:{nick.lower()}'
        now  = time.monotonic()
        hist = [t for t in self._history[key] if now - t < _LOOP_WINDOW_S]
        self._history[key] = hist
        return len(hist) >= _LOOP_THRESHOLD

    def record_response(self, room: str, nick: str):
        key = f'{room}:{nick.lower()}'
        self._history[key].append(time.monotonic())
