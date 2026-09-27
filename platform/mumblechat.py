"""
# ═══════════════════════════════════════════════════════════════════
# PLATFORM FILE — safe to edit when the protocol changes.
#   1. Field renamed? Update PROTOCOL dict at the top.
#   2. New incoming event? Add a case to _dispatch().
#   3. Outgoing format changed? Edit the matching _msg_*() function.
# Hit up Death / D-D if you're unsure what to change.
# ═══════════════════════════════════════════════════════════════════

MumbleChat Socket.IO platform adapter.
Auth: botKey in Socket.IO handshake (auth={'botKey': KEY}).
"""

import asyncio
import logging
import os

import socketio

from .base import OoPlatform

log = logging.getLogger('oo.platform.mumblechat')

# ── Protocol field names (edit here if server renames anything) ───────────────
PROTOCOL = {
    # Outgoing events
    'join_room':        'join-room',
    'leave_room':       'leave-room',
    'chat_message':     'chat-message',
    'private_message':  'private-message',
    'camera_start':     'bot-camera-start',
    'camera_frame':     'bot-camera-frame',
    'camera_stop':      'bot-camera-stop',
    # Incoming events
    'ev_room_joined':   'room-joined',
    'ev_room_users':    'room-users',
    'ev_chat_message':  'chat-message',
    'ev_user_joined':   'user-joined',
    'ev_user_left':     'user-left',
    'ev_private_msg':   'private-message',
    'ev_chat_history':  'chat-history',
    # Payload fields
    'f_room':           'room',
    'f_content':        'content',
    'f_room_name':      'name',
    'f_participants':   'participants',
    'f_user':           'user',
    'f_user_id':        'id',
    'f_username':       'username',
    'f_display_name':   'display_name',
    'f_socket_id':      'socketId',
    'f_to_user_id':     'toUserId',
    'f_from':           'from',
}

P = PROTOCOL  # shorthand


class MumbleChatPlatform(OoPlatform):

    def __init__(self, server_url: str, bot_key: str, self_username: str = ''):
        self._url      = server_url
        self._bot_key  = bot_key
        self._self_usr = self_username.lower()
        self._sio      = socketio.AsyncClient(reconnection=True,
                                               reconnection_delay=2,
                                               reconnection_delay_max=15)
        self._rooms:   set[str] = set()
        self._joined:  set[str] = set()
        # nick → userId map: key = f"{room}:{nick.lower()}"
        self._nick_map: dict[str, str] = {}
        self._register_handlers()

    def _register_handlers(self):
        sio = self._sio

        @sio.event
        async def connect():
            log.info('[MC] Connected — rejoining rooms')
            for room in list(self._rooms):
                await self._join(room)

        @sio.event
        async def disconnect():
            log.warning('[MC] Disconnected')

        @sio.on(P['ev_room_joined'])
        async def on_room_joined(data):
            room = data.get(P['f_room'], {})
            name = room.get(P['f_room_name'], '') if isinstance(room, dict) else str(room)
            name = name.lower()
            self._joined.add(name)
            for u in data.get('users', []):
                self._track_nick(name, u)
            self._fire('on_joined', name, '', None, self._self_usr)
            self._fire('on_reconnected', name)
            log.info(f'[MC] Joined {name}')

        @sio.on(P['ev_room_users'])
        async def on_room_users(data):
            room = data.get(P['f_room'], '').lower()
            users = [_norm_user(u) for u in data.get('users', [])]
            for u in users:
                self._track_nick(room, u)
            self._fire('on_user_list', room, users)

        @sio.on(P['ev_chat_message'])
        async def on_chat_message(data):
            room  = data.get(P['f_room'], '').lower()
            user  = data.get(P['f_user'], {})
            if not isinstance(user, dict):
                return
            uname = user.get(P['f_username'], '').lower()
            if uname == self._self_usr:
                return
            nick   = user.get(P['f_display_name']) or uname
            handle = user.get(P['f_user_id'], '')
            text   = data.get(P['f_content'], '')
            self._track_nick(room, user)
            self._fire('on_message', room, nick, text, str(handle))

        @sio.on(P['ev_user_joined'])
        async def on_user_joined(data):
            room = data.get(P['f_room'], '').lower()
            user = data.get(P['f_user'], {})
            if not isinstance(user, dict):
                return
            nick   = user.get(P['f_display_name']) or user.get(P['f_username'], '')
            handle = str(user.get(P['f_user_id'], ''))
            uname  = user.get(P['f_username'], '')
            self._track_nick(room, user)
            self._fire('on_join', room, nick, handle, uname, 0)

        @sio.on(P['ev_user_left'])
        async def on_user_left(data):
            room   = data.get(P['f_room'], '').lower()
            user   = data.get(P['f_user']) or {}
            handle = str(data.get('userId') or user.get(P['f_user_id'], ''))
            nick   = user.get(P['f_display_name']) or user.get(P['f_username'], '')
            self._fire('on_leave', room, nick, handle)

        @sio.on(P['ev_private_msg'])
        async def on_private_message(data):
            sender = data.get(P['f_from'], {})
            if not isinstance(sender, dict):
                return
            uname  = sender.get(P['f_username'], '')
            if uname.lower() == self._self_usr:
                return
            nick   = sender.get(P['f_display_name']) or uname
            handle = str(sender.get(P['f_user_id'], ''))
            text   = data.get(P['f_content'], '')
            self._fire('on_pm', nick, handle, text)

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self):
        proxy = os.environ.get('OO_SOCKS_PROXY', '').strip()
        kwargs = {'transports': ['websocket'], 'auth': {'botKey': self._bot_key}}
        if proxy:
            kwargs['socketio_path'] = '/socket.io'
        log.info(f'[MC] Connecting to {self._url}')
        await self._sio.connect(self._url, **kwargs)

    async def disconnect(self):
        await self._sio.disconnect()

    async def join_room(self, room: str):
        room = room.lower()
        self._rooms.add(room)
        await self._join(room)

    async def _join(self, room: str):
        await self._sio.emit(P['join_room'], {'roomName': room})

    async def leave_room(self, room: str):
        room = room.lower()
        self._rooms.discard(room)
        self._joined.discard(room)
        await self._sio.emit(P['leave_room'], {'roomName': room})

    async def send(self, room: str, text: str):
        await self._sio.emit(P['chat_message'], {'roomName': room.lower(), 'content': text})

    async def send_pm(self, username: str, text: str, handle: str | None = None):
        user_id = handle or self._resolve_user_id(username)
        await self._sio.emit(P['private_message'], {'toUserId': user_id, 'content': text})

    # ── Nick/handle tracking ───────────────────────────────────────────────────

    def _track_nick(self, room: str, user: dict):
        nick = (user.get(P['f_display_name']) or user.get(P['f_username'], '')).lower()
        uid  = str(user.get(P['f_user_id'], ''))
        if nick and uid:
            self._nick_map[f'{room}:{nick}'] = uid

    def _resolve_user_id(self, username: str) -> str:
        for key, uid in self._nick_map.items():
            if key.endswith(f':{username.lower()}'):
                return uid
        return username


def _norm_user(u: dict) -> dict:
    return u if isinstance(u, dict) else {}
