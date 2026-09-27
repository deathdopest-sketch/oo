"""
OoLog — immutable append-only audit log of all mod actions.
"""

import json
import time
from storage import log_file


class OoLog:

    def __init__(self):
        self._path = log_file('mod_audit.jsonl')
        self._recent: list[dict] = []

    def record(self, action: str, username: str, room: str,
               rule_id: str = '', reason: str = '', moderator: str = 'ó_ò'):
        entry = {
            'ts':        time.time(),
            'action':    action,
            'username':  username,
            'room':      room,
            'rule':      rule_id,
            'reason':    reason,
            'moderator': moderator,
        }
        with open(self._path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
        self._recent.append(entry)
        if len(self._recent) > 200:
            self._recent = self._recent[-200:]

    def get_recent(self, n: int = 10) -> list[dict]:
        return self._recent[-n:]

    def format_entry(self, e: dict) -> str:
        ts = time.strftime('%H:%M:%S', time.localtime(e['ts']))
        r  = e.get('rule', '')
        reason = e.get('reason', '')
        tail = f' [{r}]' if r else ''
        tail += f' — {reason}' if reason else ''
        return f'[{ts}] {e["action"].upper()} {e["username"]} in {e["room"]}{tail}'
