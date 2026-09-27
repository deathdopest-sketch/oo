"""
OoWatchlist — per-user strike counter and ban state.
"""

import time
from storage import read, write


class OoWatchlist:

    def __init__(self):
        self._data: dict[str, dict] = read('watchlist', {})

    def _get(self, username: str) -> dict:
        key = username.lower()
        if key not in self._data:
            self._data[key] = {
                'username': username,
                'strikes': 0,
                'warns': 0,
                'muted_until': 0,
                'banned': False,
                'ban_reason': '',
                'history': [],
            }
        return self._data[key]

    def add_strike(self, username: str, rule_id: str, action: str):
        entry = self._get(username)
        entry['strikes'] += 1
        if action == 'warn':
            entry['warns'] += 1
        entry['history'].append({
            'ts': time.time(), 'rule': rule_id, 'action': action
        })
        entry['history'] = entry['history'][-50:]
        self._save()
        return entry['strikes']

    def set_muted(self, username: str, duration_sec: int):
        entry = self._get(username)
        entry['muted_until'] = time.time() + duration_sec
        self._save()

    def is_muted(self, username: str) -> bool:
        entry = self._data.get(username.lower())
        if not entry:
            return False
        return entry.get('muted_until', 0) > time.time()

    def set_banned(self, username: str, reason: str = ''):
        entry = self._get(username)
        entry['banned']     = True
        entry['ban_reason'] = reason
        self._save()

    def unban(self, username: str):
        entry = self._get(username)
        entry['banned']     = False
        entry['ban_reason'] = ''
        self._save()

    def is_banned(self, username: str) -> bool:
        return self._data.get(username.lower(), {}).get('banned', False)

    def get_strikes(self, username: str) -> int:
        return self._data.get(username.lower(), {}).get('strikes', 0)

    def clear_strikes(self, username: str):
        entry = self._get(username)
        entry['strikes'] = 0
        self._save()

    def get_active_users(self) -> list[dict]:
        return [e for e in self._data.values() if e.get('strikes', 0) > 0]

    def _save(self):
        write('watchlist', self._data)
