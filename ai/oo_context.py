"""
OoContext — per-room sliding conversation window.
Keeps the last N messages as {role, content} dicts for LLM calls.
"""

from collections import deque
from typing import NamedTuple


class _Msg(NamedTuple):
    role:    str   # 'user' | 'assistant'
    content: str


class OoContext:

    def __init__(self, window: int = 90):
        self._window = window
        self._rooms: dict[str, deque[_Msg]] = {}

    def add_user(self, room: str, nick: str, text: str):
        q = self._get(room)
        q.append(_Msg('user', f'{nick}: {text}'))

    def add_bot(self, room: str, text: str):
        q = self._get(room)
        q.append(_Msg('assistant', text))

    def get_messages(self, room: str, system_prompt: str) -> list[dict]:
        msgs = [{'role': 'system', 'content': system_prompt}]
        for m in self._get(room):
            msgs.append({'role': m.role, 'content': m.content})
        return msgs

    def clear(self, room: str):
        self._rooms.pop(room.lower(), None)

    def _get(self, room: str) -> deque:
        key = room.lower()
        if key not in self._rooms:
            self._rooms[key] = deque(maxlen=self._window)
        return self._rooms[key]
