"""
OoOllama — async Ollama HTTP client.
"""

import asyncio
import logging
import os
from typing import Any

import aiohttp

log = logging.getLogger('oo.ai.ollama')

_DEFAULT_HOST  = 'http://localhost:11434'
_DEFAULT_MODEL = 'dolphin3:8b'
_DEFAULT_FAST  = 'llama3.2:1b'

# Token budgets per context type
PROFILES = {
    'banter': {'num_predict':  60, 'temperature': 0.92},
    'normal': {'num_predict': 100, 'temperature': 0.85},
    'deep':   {'num_predict': 150, 'temperature': 0.80},
    'drift':  {'num_predict':  80, 'temperature': 0.70},
}


class OoOllama:

    def __init__(self):
        self.host    = os.environ.get('OLLAMA_HOST', _DEFAULT_HOST).rstrip('/')
        self.model   = os.environ.get('OLLAMA_MODEL', _DEFAULT_MODEL)
        self.fast    = os.environ.get('OLLAMA_FAST_MODEL', _DEFAULT_FAST)
        self.available = False
        self._session: aiohttp.ClientSession | None = None

    async def init(self):
        self._session = aiohttp.ClientSession()
        self.available = await self._check()
        if self.available:
            log.info(f'[Ollama] Ready — model: {self.model} fast: {self.fast}')
        else:
            log.warning('[Ollama] Not reachable — AI responses disabled')

    async def close(self):
        if self._session:
            await self._session.close()

    async def _check(self) -> bool:
        try:
            async with self._session.get(f'{self.host}/api/tags', timeout=aiohttp.ClientTimeout(total=5)) as r:
                return r.status == 200
        except Exception:
            return False

    async def chat(self, messages: list[dict], model: str | None = None,
                   timeout_s: float = 60, **kwargs) -> str | None:
        if not self.available or not self._session:
            return None
        payload = {
            'model':    model or self.model,
            'messages': messages,
            'stream':   False,
            **kwargs,
        }
        try:
            async with self._session.post(
                f'{self.host}/api/chat',
                json=payload,
                timeout=aiohttp.ClientTimeout(total=timeout_s),
            ) as r:
                if r.status != 200:
                    log.debug(f'[Ollama] HTTP {r.status}')
                    return None
                data = await r.json()
                return (data.get('message') or {}).get('content', '').strip() or None
        except asyncio.TimeoutError:
            log.debug('[Ollama] Timeout')
            return None
        except Exception as e:
            log.debug(f'[Ollama] Error: {e}')
            return None

    async def chat_adaptive(self, messages: list[dict],
                             context_type: str = 'normal') -> str | None:
        profile = PROFILES.get(context_type, PROFILES['normal'])
        return await self.chat(messages, **profile)

    async def generate(self, prompt: str, max_tokens: int = 100,
                       model: str | None = None) -> str | None:
        return await self.chat(
            [{'role': 'user', 'content': prompt}],
            model=model or self.fast,
            num_predict=max_tokens,
        )
