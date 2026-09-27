"""
# ═══════════════════════════════════════════════════════════════════
# PLATFORM FILE — safe to edit when the protocol changes.
#   1. Field renamed? Update PROTOCOL dict at the top.
#   2. New incoming event? Add a case to _dispatch().
#   3. Outgoing format changed? Edit the matching _msg_*() function.
# Hit up Death / D-D if you're unsure what to change.
# ═══════════════════════════════════════════════════════════════════

ChatCommon WebSocket platform adapter.

Auth flow:
  1. curl_cffi fetches https://chatcommon.com to get Cloudflare cf_clearance cookie
  2. Raw websockets connection to wss://ws.chatcommon.com/ with that cookie
  3. Server sends 'welcome' with clientId
  4. We send client_identify + login (is_logged_in: true)
  5. Server sends login_success

If curl_cffi Cloudflare bypass fails (CF updates their challenge):
  See PLAYWRIGHT FALLBACK comment block below.
"""

import asyncio
import json
import logging
import os
import random
import string
import time
from typing import Any

import websockets

from .base import OoPlatform

log = logging.getLogger('oo.platform.chatcommon')

# ── Protocol constants — edit here if ChatCommon renames fields ───────────────
PROTOCOL = {
    # Outgoing message types
    'out_identify':     'client_identify',
    'out_login':        'login',
    'out_join':         'join_room',
    'out_leave':        'leave_room',
    'out_send':         'send_message',
    'out_pong':         'pong',
    'out_pm':           'private_message',
    # Incoming message types
    'in_welcome':       'welcome',
    'in_login_ok':      'login_success',
    'in_login_err':     'login_error',
    'in_chat':          'chat_message',
    'in_live_log':      'live_log_push',    # richer event — prefer over chat_message
    'in_room_joined':   'room_joined',
    'in_join_success':  'join_room_success',
    'in_joined_room':   'joined_room',
    'in_user_join':     'user_join',
    'in_user_joined':   'user_joined',
    'in_user_leave':    'user_leave',
    'in_user_left':     'user_left',
    'in_user_list':     'user_list',
    'in_pm':            'private_message',
    'in_ping':          'ping',
    'in_nick_change':   'nick_change',
    'in_batch':         'batch',
    # Payload field names
    'f_type':           'type',
    'f_client_id':      'clientId',
    'f_room':           'room',
    'f_username':       'username',
    'f_message':        'message',
    'f_user_id':        'userId',
    'f_role':           'role',
    'f_timestamp':      'timestamp',
    'f_sender':         'sender',
    'f_recipient':      'recipient',
    'f_msg_id':         'message_id',
    'f_live_user':      'user',
    'f_live_msg':       'msg',
    'f_old_nick':       'oldNick',
    'f_new_nick':       'newNick',
    'f_handle':         'handle',
}

P = PROTOCOL  # shorthand

CC_WS_URL   = 'wss://ws.chatcommon.com/'
CC_HTTP_URL = 'https://chatcommon.com'

# ── Cloudflare bypass — curl_cffi approach ────────────────────────────────────
#
# PLAYWRIGHT FALLBACK: if curl_cffi stops working (CF changes challenge type),
# replace _get_cf_cookie() with:
#
#   async def _get_cf_cookie(self) -> dict:
#       from playwright.async_api import async_playwright
#       async with async_playwright() as p:
#           browser = await p.chromium.launch(headless=True)
#           ctx = await browser.new_context()
#           page = await ctx.new_page()
#           await page.goto(CC_HTTP_URL, wait_until='networkidle')
#           await asyncio.sleep(3)
#           cookies = await ctx.cookies()
#           await browser.close()
#           return {c['name']: c['value'] for c in cookies}
#
# Then add 'playwright' to requirements.txt.
# ─────────────────────────────────────────────────────────────────────────────

async def _get_cf_cookie() -> dict:
    try:
        from curl_cffi.requests import AsyncSession
        async with AsyncSession(impersonate='chrome110') as s:
            r = await s.get(CC_HTTP_URL, timeout=15)
            return {c.name: c.value for c in s.cookies}
    except Exception as e:
        log.warning(f'[CC] curl_cffi cookie fetch failed: {e} — trying direct WS')
        return {}


def _pm_id() -> str:
    return 'pm-' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))


class ChatCommonPlatform(OoPlatform):

    def __init__(self, username: str, password: str, rooms: list[str]):
        self._username = username
        self._password = password
        self._rooms    = [r.lower() for r in rooms]
        self._ws       = None
        self._client_id: int | str = 0
        self._joined:  set[str] = set()
        self._running  = False
        self._send_q: asyncio.Queue = asyncio.Queue()
        # username → userId map per room
        self._user_map: dict[str, str] = {}  # f"{room}:{username.lower()}" → userId

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def connect(self):
        self._running = True
        asyncio.ensure_future(self._run())

    async def disconnect(self):
        self._running = False
        if self._ws:
            await self._ws.close()

    # ── Public API ─────────────────────────────────────────────────────────────

    async def join_room(self, room: str):
        room = room.lower()
        if room not in self._rooms:
            self._rooms.append(room)
        await self._send_raw(self._msg_join(room))

    async def leave_room(self, room: str):
        room = room.lower()
        if room in self._rooms:
            self._rooms.remove(room)
        self._joined.discard(room)
        await self._send_raw({P['f_type']: P['out_leave'], 'room': room})

    async def send(self, room: str, text: str):
        await self._send_q.put(self._msg_send(room.lower(), text))

    async def send_pm(self, username: str, text: str, handle: str | None = None):
        await self._send_raw(self._msg_pm(username, text))

    # ── Outgoing message builders (edit these if CC changes payload format) ───

    def _msg_identify(self, fingerprint) -> dict:
        return {P['f_type']: P['out_identify'], 'fingerprint': fingerprint}

    def _msg_login(self, fingerprint) -> dict:
        return {
            P['f_type']:       P['out_login'],
            'username':        self._username,
            'password':        self._password,
            'is_logged_in':    True,
            'stealth':         False,
            'fingerprint':     fingerprint,
        }

    def _msg_join(self, room: str) -> dict:
        return {
            P['f_type']:  P['out_join'],
            'room':       room,
            'username':   self._username,
            'nickname':   None,
        }

    def _msg_send(self, room: str, text: str) -> dict:
        return {P['f_type']: P['out_send'], 'room': room, 'message': text}

    def _msg_pong(self, ts) -> dict:
        return {P['f_type']: P['out_pong'], 'timestamp': ts}

    def _msg_pm(self, recipient: str, text: str) -> dict:
        return {
            P['f_type']:    P['out_pm'],
            'recipient':    recipient,
            'message':      text,
            'message_id':   _pm_id(),
            'timestamp':    int(time.time() * 1000),
        }

    # ── Connection loop ────────────────────────────────────────────────────────

    async def _run(self):
        backoff = 2
        while self._running:
            try:
                cookies = await _get_cf_cookie()
                cookie_hdr = '; '.join(f'{k}={v}' for k, v in cookies.items())
                headers = {'Cookie': cookie_hdr} if cookie_hdr else {}

                async with websockets.connect(CC_WS_URL, extra_headers=headers,
                                              ping_interval=30, ping_timeout=10) as ws:
                    self._ws = ws
                    backoff  = 2
                    log.info('[CC] WebSocket connected')

                    # Start sender coroutine
                    asyncio.ensure_future(self._sender(ws))

                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        await self._dispatch(msg)

            except Exception as e:
                if self._running:
                    log.warning(f'[CC] Connection error: {e} — retry in {backoff}s')
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60)

    async def _sender(self, ws):
        while self._running:
            try:
                msg = await asyncio.wait_for(self._send_q.get(), timeout=1.0)
                await ws.send(json.dumps(msg))
                await asyncio.sleep(0.3 + random.random() * 0.5)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

    async def _send_raw(self, msg: dict):
        if self._ws:
            try:
                await self._ws.send(json.dumps(msg))
            except Exception as e:
                log.debug(f'[CC] send_raw error: {e}')

    # ── Incoming dispatcher (add new event types here) ─────────────────────────

    async def _dispatch(self, msg: dict):
        t = msg.get(P['f_type'], '')

        # Unwrap batch
        if t == P['in_batch']:
            for ev in msg.get('events', []):
                ev['_batchRoom'] = msg.get('room', ev.get('room', ''))
                await self._dispatch(ev)
            return

        if t == P['in_welcome']:
            self._client_id = msg.get(P['f_client_id'], 0)
            await self._send_raw(self._msg_identify(self._client_id))
            await self._send_raw(self._msg_login(self._client_id))
            return

        if t == P['in_login_ok']:
            uname = msg.get('profile', {}).get('username', '') or msg.get(P['f_username'], '')
            log.info(f'[CC] Login success — user: {uname}')
            for room in self._rooms:
                await self._send_raw(self._msg_join(room))
            return

        if t in (P['in_login_err'], 'auth_error'):
            log.error(f'[CC] Login failed: {msg.get("message", "")}')
            return

        if t == P['in_ping']:
            await self._send_raw(self._msg_pong(msg.get(P['f_timestamp'], 0)))
            return

        if t in (P['in_room_joined'], P['in_join_success'], P['in_joined_room']):
            room = (msg.get('room') or msg.get('_batchRoom') or '').lower()
            if room:
                self._joined.add(room)
                users = msg.get('users', [])
                for u in users:
                    self._track_user(room, u)
                log.info(f'[CC] Joined room: {room} ({len(users)} users)')
                self._fire('on_joined', room, self._username, None, self._username)
            return

        if t in (P['in_user_join'], P['in_user_joined']):
            room  = (msg.get(P['f_room']) or msg.get('_batchRoom') or '').lower()
            uname = msg.get(P['f_username'], '')
            uid   = str(msg.get(P['f_user_id'], ''))
            role  = msg.get(P['f_role'], '')
            mod   = 1 if role in ('operator', 'admin', 'mod') else 0
            self._track_user(room, msg)
            self._fire('on_join', room, uname, uid, uname, mod)
            return

        if t in (P['in_user_leave'], P['in_user_left']):
            room  = (msg.get(P['f_room']) or msg.get('_batchRoom') or '').lower()
            uname = msg.get(P['f_username'], '')
            uid   = str(msg.get(P['f_user_id'], ''))
            self._fire('on_leave', room, uname, uid)
            return

        if t == P['in_nick_change']:
            room     = (msg.get(P['f_room']) or '').lower()
            old_nick = msg.get(P['f_old_nick'], '')
            new_nick = msg.get(P['f_new_nick'], '')
            handle   = str(msg.get(P['f_handle'], ''))
            self._fire('on_nick_change', room, old_nick, new_nick, handle)
            return

        # Prefer live_log_push (richer) but fall back to chat_message
        if t == P['in_live_log']:
            entry = msg.get('entry', {})
            room  = (msg.get(P['f_room']) or msg.get('_batchRoom') or '').lower()
            uname = entry.get(P['f_live_user'], '')
            text  = entry.get(P['f_live_msg'], '')
            if uname.lower() == self._username.lower():
                return
            uid = self._user_map.get(f'{room}:{uname.lower()}', uname)
            self._fire('on_message', room, uname, text, uid)
            return

        if t == P['in_chat']:
            room  = (msg.get(P['f_room']) or msg.get('_batchRoom') or '').lower()
            uname = msg.get(P['f_username'], '')
            text  = msg.get(P['f_message'], '')
            uid   = str(msg.get(P['f_user_id'], ''))
            if uname.lower() == self._username.lower():
                return
            self._track_user(room, msg)
            self._fire('on_message', room, uname, text, uid)
            return

        if t == P['in_pm']:
            sender = msg.get(P['f_sender'], '')
            if isinstance(sender, dict):
                uname = sender.get(P['f_username'], '')
            else:
                uname = str(sender)
            if uname.lower() == self._username.lower():
                return
            text   = msg.get(P['f_message'], '')
            uid    = self._user_map.get(uname.lower(), uname)
            self._fire('on_pm', uname, uid, text)
            return

        # Silent drop for high-freq noise
        if t in ('friend_status_update', 'broadcast_media', 'media_stopped',
                 'room_list_batch', 'user_style_update', 'friend_typing',
                 'update_room_limits', 'social_sync', 'forum_structure_changed',
                 'network_news_data', 'room_automation_sync', 'room_visual_update',
                 'bot_settings_data', 'link_metadata', 'broadcast_stopped',
                 'broadcast_started', 'broadcast_active', 'broadcast_ended',
                 'youtube_queue_updated', 'current_video_state', 'pong', ''):
            return

        log.debug(f'[CC] unhandled type: {t}')

    def _track_user(self, room: str, data: dict):
        uname = data.get(P['f_username'], '').lower()
        uid   = str(data.get(P['f_user_id'], ''))
        if uname and uid:
            self._user_map[f'{room}:{uname}'] = uid
