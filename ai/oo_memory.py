"""
OoMemory — tiered memory system.
  Short-term: rolling window per room (evicts to summaries)
  Summaries:  auto-generated when messages are evicted
  Profiles:   per-user key/value store (persisted to disk)
"""

import logging
import time
from collections import deque
from typing import Any

from storage import read, write

log = logging.getLogger('oo.ai.memory')

_SHORT_WINDOW  = 90
_EVICT_SUMMARY = 12   # generate summary after evicting this many messages


class OoMemory:

    def __init__(self, ollama=None):
        self._ollama   = ollama
        self._rooms:   dict[str, deque]  = {}
        self._summary: dict[str, list]   = {}   # room → list of summary dicts
        self._profiles: dict[str, dict]  = read('memory_profiles', {})
        self._evict_buf: dict[str, list] = {}

    def add(self, room: str, nick: str, text: str):
        key = room.lower()
        q   = self._get_queue(key)
        q.append({'nick': nick, 'text': text, 'ts': time.time()})
        if len(q) == q.maxlen:
            self._evict(key)

    def _evict(self, room: str):
        q = self._get_queue(room)
        # Move oldest messages to eviction buffer
        buf = self._evict_buf.setdefault(room, [])
        while len(q) > _SHORT_WINDOW - _EVICT_SUMMARY:
            buf.append(q.popleft())
        if len(buf) >= _EVICT_SUMMARY and self._ollama:
            import asyncio
            asyncio.ensure_future(self._summarize(room, list(buf)))
            self._evict_buf[room] = []

    async def _summarize(self, room: str, msgs: list):
        text = '\n'.join(f'{m["nick"]}: {m["text"]}' for m in msgs)
        prompt = (f'Summarize this chat segment in 2-3 sentences, '
                  f'noting topics, mood, and who was involved:\n\n{text}')
        summary = await self._ollama.generate(prompt, max_tokens=80)
        if summary:
            topics = [w for w in text.lower().split()
                      if len(w) > 4 and w.isalpha()][:5]
            self._summary.setdefault(room, []).append({
                'ts': time.time(),
                'text': summary,
                'topics': list(set(topics)),
                'msg_count': len(msgs),
            })
            if len(self._summary[room]) > 20:
                self._summary[room] = self._summary[room][-20:]

    def get_summaries(self, room: str) -> list[dict]:
        return self._summary.get(room.lower(), [])

    # ── User profiles ─────────────────────────────────────────────────────────

    def get_profile(self, handle: str) -> dict:
        return self._profiles.get(str(handle), {})

    def set_profile(self, handle: str, key: str, value: Any):
        prof = self._profiles.setdefault(str(handle), {})
        prof[key] = value
        prof['updated_at'] = time.time()
        if len(self._profiles) % 50 == 0:
            self.save()

    def save(self):
        write('memory_profiles', self._profiles)

    def _get_queue(self, room: str) -> deque:
        if room not in self._rooms:
            self._rooms[room] = deque(maxlen=_SHORT_WINDOW)
        return self._rooms[room]
