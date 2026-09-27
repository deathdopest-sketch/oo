"""
OoDrift — long-term personality drift.
Tracks whether the room has been hostile, deep, or active over days.
Persists to storage and subtly shifts ó_ò's prompt.
"""

import time
from storage import read, write


class OoDrift:

    def __init__(self):
        data = read('drift', {})
        self.hostile = float(data.get('hostile', 0.0))
        self.deep    = float(data.get('deep', 0.0))
        self.active  = float(data.get('active', 0.0))
        self._last_decay = float(data.get('last_decay', time.time()))

    def log_emotion(self, emotion: str):
        if emotion == 'angry':
            self.hostile += 1
        elif emotion in ('sad', 'negative'):
            self.deep += 0.5
        self._maybe_decay()

    def log_active(self, word_count: int):
        if word_count > 30:
            self.active += 1
        self._maybe_decay()

    def _maybe_decay(self):
        now    = time.time()
        hours  = (now - self._last_decay) / 3600
        if hours < 1:
            return
        self.hostile = max(0.0, self.hostile - 0.1 * hours)
        self.deep    = max(0.0, self.deep    - 0.1 * hours)
        self.active  = max(0.0, self.active  - 0.2 * hours)
        self._last_decay = now
        self._save()

    def get_hint(self) -> str:
        parts = []
        if self.hostile >= 3:
            parts.append('[Drift: hostile room lately — shorter, harder edges]')
        if self.deep >= 3:
            parts.append('[Drift: heavy emotional energy recently — stay grounded, direct]')
        if self.active >= 5:
            parts.append('[Drift: high activity — quicker, more engaged]')
        return ' '.join(parts)

    def _save(self):
        write('drift', {
            'hostile': self.hostile,
            'deep':    self.deep,
            'active':  self.active,
            'last_decay': self._last_decay,
        })
