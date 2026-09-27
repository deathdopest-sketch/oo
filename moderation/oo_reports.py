"""
OoReports — user report queue. .report <nick> [reason]
"""

import time
from storage import read, write


class OoReports:

    def __init__(self):
        self._queue: list[dict] = []

    def add(self, reporter: str, target: str, reason: str, room: str):
        self._queue.append({
            'ts': time.time(), 'reporter': reporter,
            'target': target, 'reason': reason, 'room': room,
        })
        if len(self._queue) > 200:
            self._queue = self._queue[-200:]

    def get_pending(self) -> list[dict]:
        return list(self._queue)

    def clear(self):
        self._queue.clear()

    def format_reports(self, n: int = 10) -> str:
        recent = self._queue[-n:]
        if not recent:
            return 'no pending reports'
        lines = []
        for r in recent:
            ts = time.strftime('%H:%M', time.localtime(r['ts']))
            lines.append(f'[{ts}] {r["reporter"]} reported {r["target"]} in {r["room"]}: {r["reason"]}')
        return '\n'.join(lines)
