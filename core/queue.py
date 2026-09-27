"""
OoQueue — rate-limited async message send queue.
Jitter: 350–1400ms between sends to avoid spam detection.
"""

import asyncio
import logging
import random
import time
from typing import Callable, Awaitable

log = logging.getLogger('oo.queue')

_MIN_MS = 350
_MAX_MS = 1400
_MAX_PER_MINUTE = 20


class OoQueue:

    def __init__(self):
        self._q: asyncio.Queue = asyncio.Queue()
        self._send_fn: Callable | None = None
        self._running = False
        self._sent_times: list[float] = []

    def set_send_fn(self, fn: Callable):
        self._send_fn = fn

    async def start(self):
        self._running = True
        asyncio.ensure_future(self._worker())

    async def stop(self):
        self._running = False

    async def enqueue(self, room: str, text: str, force: bool = False):
        if not text:
            return
        await self._q.put((room, text, force))

    async def _worker(self):
        while self._running:
            try:
                room, text, force = await asyncio.wait_for(self._q.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue

            if not self._send_fn:
                continue

            now = time.monotonic()
            self._sent_times = [t for t in self._sent_times if now - t < 60]
            if not force and len(self._sent_times) >= _MAX_PER_MINUTE:
                log.debug('[Queue] Rate limit hit — dropping message')
                continue

            try:
                await self._send_fn(room, text)
                self._sent_times.append(time.monotonic())
            except Exception as e:
                log.error(f'[Queue] Send error: {e}')

            delay = (_MIN_MS + random.random() * (_MAX_MS - _MIN_MS)) / 1000
            await asyncio.sleep(delay)
