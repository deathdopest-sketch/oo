"""
OoSiteWatch — proactive room health monitoring and drama alerts.
Reports to owner via PM. Doesn't wait to be asked.
"""

import asyncio
import logging
import os
import time
from collections import defaultdict

import aiohttp

log = logging.getLogger('oo.companion.sitewatch')

_OWNER_USERNAME    = os.environ.get('OO_OWNER_USERNAME', 'n_n').lower()
_WATCH_ROOMS       = [r.strip().lower() for r in
                      os.environ.get('OO_WATCH_ROOMS', '').split(',') if r.strip()]
_DRAMA_THRESHOLD   = int(os.environ.get('OO_DRAMA_THRESHOLD', '3'))
_DAILY_HOUR        = int(os.environ.get('OO_DAILY_SUMMARY_HOUR', '23'))
_MUMBLECHAT_URL    = os.environ.get('MUMBLECHAT_SERVER_URL', 'https://mumblechat.online')
_HEALTH_INTERVAL   = 30 * 60  # 30 minutes


class OoSiteWatch:

    def __init__(self, platforms: dict, queue):
        self._platforms  = platforms  # name → OoPlatform
        self._queue      = queue
        self._room_users: dict[str, list] = defaultdict(list)
        self._room_timestamps: dict[str, float] = {}
        self._mod_actions: dict[str, list[float]] = defaultdict(list)  # room → [timestamps]
        self._action_count: dict[str, int] = defaultdict(int)
        self._daily_stats: dict = {}
        self._last_daily = 0.0
        self._last_health = 0.0

    async def start(self):
        asyncio.ensure_future(self._watch_loop())
        log.info('[SiteWatch] Started')

    def on_user_join(self, room: str, nick: str):
        room = room.lower()
        if nick not in self._room_users[room]:
            self._room_users[room].append(nick)
        self._room_timestamps[room] = time.time()

    def on_user_leave(self, room: str, nick: str):
        room = room.lower()
        if nick in self._room_users[room]:
            self._room_users[room].remove(nick)
        if not self._room_users[room]:
            self._room_timestamps.setdefault(room, time.time())

    def on_mod_action(self, room: str):
        now = time.monotonic()
        room = room.lower()
        window = 10 * 60  # 10 min
        hist = [t for t in self._mod_actions[room] if now - t < window]
        hist.append(now)
        self._mod_actions[room] = hist
        self._action_count[room] = self._action_count.get(room, 0) + 1

        if len(hist) >= _DRAMA_THRESHOLD:
            asyncio.ensure_future(self._alert_drama(room, len(hist)))

    async def _alert_drama(self, room: str, count: int):
        msg = f"heads up nn — {count} mod actions in {room} in the last 10 min. might want to check it"
        await self._pm_owner(msg)

    async def _watch_loop(self):
        while True:
            await asyncio.sleep(60)
            now = time.time()

            # Room health check every 30 min
            if now - self._last_health >= _HEALTH_INTERVAL:
                self._last_health = now
                for room in _WATCH_ROOMS:
                    users = self._room_users.get(room, [])
                    last_activity = self._room_timestamps.get(room, 0)
                    dead_hours = (now - last_activity) / 3600

                    if len(users) == 0 and dead_hours > 2:
                        await self._pm_owner(
                            f"fyi {room} has been empty for {int(dead_hours)}hrs"
                        )
                    elif len(users) > 30:
                        await self._pm_owner(
                            f"{room} is pretty busy rn — {len(users)} people"
                        )

                # Server ping
                await self._check_server()

            # Daily summary
            import datetime
            if datetime.datetime.now().hour == _DAILY_HOUR and now - self._last_daily > 3600:
                self._last_daily = now
                await self._send_daily_summary()

    async def _check_server(self):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(_MUMBLECHAT_URL, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status >= 500:
                        await self._pm_owner(f"mumblechat server might be having issues — got {r.status}")
        except aiohttp.ClientConnectorError:
            await self._pm_owner("can't reach mumblechat server — might be down")
        except Exception:
            pass

    async def _send_daily_summary(self):
        total_actions = sum(self._action_count.values())
        room_summary  = ', '.join(
            f'{r}: {c}' for r, c in self._action_count.items() if c > 0
        ) or 'quiet day'
        peak_rooms = sorted(
            self._room_users.items(), key=lambda x: -len(x[1])
        )
        peak = f"{peak_rooms[0][0]}: {len(peak_rooms[0][1])} users" if peak_rooms else 'n/a'

        msg = (f"daily: {total_actions} mod actions total ({room_summary}). "
               f"biggest room rn: {peak}")
        await self._pm_owner(msg)
        self._action_count.clear()

    async def _pm_owner(self, text: str):
        for plat in self._platforms.values():
            try:
                await plat.send_pm(_OWNER_USERNAME, text)
                return
            except Exception:
                continue
