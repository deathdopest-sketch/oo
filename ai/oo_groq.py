"""
OoGroq — Groq cloud LLM client (OpenAI-compatible API).
Used as fallback when Ollama is unavailable.
"""

import logging
import os
import aiohttp

log = logging.getLogger('oo.ai.groq')

_API_URL = 'https://api.groq.com/openai/v1/chat/completions'
_DEFAULT_MODEL = 'llama-3.1-8b-instant'


class OoGroq:

    def __init__(self):
        self.api_key   = os.environ.get('GROQ_API_KEY', '').strip()
        self.model     = os.environ.get('GROQ_MODEL', _DEFAULT_MODEL)
        self.available = bool(self.api_key)
        self._session: aiohttp.ClientSession | None = None

    async def init(self):
        if self.available:
            self._session = aiohttp.ClientSession(
                headers={'Authorization': f'Bearer {self.api_key}'}
            )
            log.info(f'[Groq] Ready — model: {self.model}')

    async def close(self):
        if self._session:
            await self._session.close()

    async def chat(self, messages: list[dict], max_tokens: int = 100,
                   temperature: float = 0.85) -> str | None:
        if not self.available or not self._session:
            return None
        payload = {
            'model':       self.model,
            'messages':    messages,
            'max_tokens':  max_tokens,
            'temperature': temperature,
        }
        try:
            async with self._session.post(_API_URL, json=payload,
                                           timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                return data['choices'][0]['message']['content'].strip() or None
        except Exception as e:
            log.debug(f'[Groq] Error: {e}')
            return None
