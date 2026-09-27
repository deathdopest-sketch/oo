"""
OoNickCycle — AI-generated nick rotation.
Rotates every 8–14 hours.
"""

import asyncio
import logging
import random
import time

log = logging.getLogger('oo.features.nick_cycle')

_FALLBACK_NICKS = [
    'ó_ò', 'oo', 'o_o', 'ò_ó', 'oo__', '__oo', 'oo_idle',
    'watching', 'dormant_oo', 'oo_away',
]
_MIN_HOLD_H = 8
_MAX_HOLD_H = 14


class OoNickCycle:

    def __init__(self, ollama, send_fn, default_nick: str = 'ó_ò'):
        self._ollama      = ollama
        self._send_fn     = send_fn
        self._default     = default_nick
        self._running     = False
        self._next_rotate = time.monotonic() + self._roll_delay()

    def _roll_delay(self) -> float:
        return (_MIN_HOLD_H + random.random() * (_MAX_HOLD_H - _MIN_HOLD_H)) * 3600

    def start(self):
        self._running = True
        asyncio.ensure_future(self._loop())

    def stop(self):
        self._running = False

    async def _loop(self):
        await asyncio.sleep(5 * 60)  # 5-min cold start delay
        while self._running:
            if time.monotonic() >= self._next_rotate:
                nick = await self._generate()
                try:
                    await self._send_fn(nick)
                    log.info(f'[NickCycle] Changed to: {nick}')
                except Exception as e:
                    log.debug(f'[NickCycle] send error: {e}')
                self._next_rotate = time.monotonic() + self._roll_delay()
            await asyncio.sleep(60)

    async def _generate(self) -> str:
        if not self._ollama or not self._ollama.available:
            return random.choice(_FALLBACK_NICKS)
        prompt = ("Generate a single chat nickname (2-10 chars). "
                  "Style: lowercase, minimalist, slightly weird or cute letter-face style "
                  "like ó_ò, oo, o-o. No quotes. Just the nick.")
        result = await self._ollama.generate(prompt, max_tokens=10)
        if result:
            clean = result.strip().split()[0][:12]
            if clean:
                return clean
        return random.choice(_FALLBACK_NICKS)
