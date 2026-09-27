"""
OoPlatform — abstract base for chat platform adapters.

Both ChatCommon and MumbleChat implement this interface.
OoBot only talks to this; it never calls platform internals directly.
"""

from abc import ABC, abstractmethod
from typing import Callable, Awaitable


class OoPlatform(ABC):

    # Callbacks — set by OoBot after construction
    on_message:     Callable | None = None   # (room, nick, text, handle)
    on_join:        Callable | None = None   # (room, nick, handle, username, mod)
    on_joined:      Callable | None = None   # (room, nick, handle, username)
    on_leave:       Callable | None = None   # (room, nick, handle)
    on_nick_change: Callable | None = None   # (room, old_nick, new_nick, handle)
    on_pm:          Callable | None = None   # (from_nick, from_handle, text)
    on_reconnected: Callable | None = None   # (room)
    on_closed:      Callable | None = None   # (room)

    @abstractmethod
    async def connect(self): ...

    @abstractmethod
    async def disconnect(self): ...

    @abstractmethod
    async def join_room(self, room: str): ...

    @abstractmethod
    async def leave_room(self, room: str): ...

    @abstractmethod
    async def send(self, room: str, text: str): ...

    @abstractmethod
    async def send_pm(self, username: str, text: str, handle: str | None = None): ...

    async def kick(self, room: str, username: str, reason: str = ''): ...
    async def ban(self, room: str, username: str, reason: str = ''): ...
    async def mute(self, room: str, username: str, duration_sec: int = 300): ...
    async def unmute(self, room: str, username: str): ...
    async def delete_message(self, room: str, message_id: str): ...

    def _fire(self, cb_name: str, *args):
        cb = getattr(self, cb_name, None)
        if cb:
            import asyncio
            if asyncio.iscoroutinefunction(cb):
                asyncio.ensure_future(cb(*args))
            else:
                cb(*args)
