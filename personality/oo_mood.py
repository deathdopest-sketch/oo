"""
OoMood — mood state machine. Shifts ó_ò's token budget and temperature.
"""

import random
import time
from typing import NamedTuple

_MOODS = ['chill', 'engaged', 'watchful', 'amused', 'dry', 'tired']

_MOOD_PROFILES = {
    'chill':    {'num_predict':  70, 'temperature': 0.80},
    'engaged':  {'num_predict': 120, 'temperature': 0.88},
    'watchful': {'num_predict':  50, 'temperature': 0.75},
    'amused':   {'num_predict':  80, 'temperature': 0.92},
    'dry':      {'num_predict':  60, 'temperature': 0.82},
    'tired':    {'num_predict':  40, 'temperature': 0.70},
}

_MOOD_HINTS = {
    'chill':    '[Mood: chill and relaxed — easy energy, not forcing anything]',
    'engaged':  '[Mood: genuinely engaged — something caught her attention]',
    'watchful': '[Mood: watching — taking it in before deciding to engage]',
    'amused':   '[Mood: quietly amused — something is funnier than she\'s letting on]',
    'dry':      '[Mood: dry and precise — no excess words]',
    'tired':    '[Mood: low energy — replies are shorter, less interested in small talk]',
}


class MoodState(NamedTuple):
    name: str
    profile: dict
    hint: str


class OoMood:

    def __init__(self):
        self._mood     = 'chill'
        self._set_at   = time.monotonic()
        self._min_hold = 25 * 60  # hold a mood for at least 25 min
        self._next_shift = self._roll_next()

    def _roll_next(self) -> float:
        return time.monotonic() + self._min_hold + random.random() * 45 * 60

    def tick(self):
        if time.monotonic() >= self._next_shift:
            current = self._mood
            choices = [m for m in _MOODS if m != current]
            self._mood      = random.choice(choices)
            self._set_at    = time.monotonic()
            self._next_shift = self._roll_next()

    def get(self) -> MoodState:
        self.tick()
        return MoodState(
            name=self._mood,
            profile=_MOOD_PROFILES[self._mood],
            hint=_MOOD_HINTS[self._mood],
        )

    def force(self, mood: str):
        if mood in _MOODS:
            self._mood = mood
            self._next_shift = self._roll_next()
