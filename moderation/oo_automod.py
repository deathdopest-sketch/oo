"""
OoAutomod — built-in check implementations.
Each check() returns True if the rule is triggered.
"""

import re
import time
import urllib.parse
from collections import defaultdict


class _RateTracker:
    def __init__(self):
        self._hist: dict[str, list[float]] = defaultdict(list)

    def add(self, key: str, window_sec: int, limit: int) -> bool:
        now  = time.monotonic()
        hist = [t for t in self._hist[key] if now - t < window_sec]
        hist.append(now)
        self._hist[key] = hist
        return len(hist) > limit

    def add_text(self, key: str, text: str, window_sec: int, count: int) -> bool:
        full_key = f'{key}:{hash(text.strip().lower())}'
        now      = time.monotonic()
        hist     = [t for t in self._hist[full_key] if now - t < window_sec]
        hist.append(now)
        self._hist[full_key] = hist
        return len(hist) >= count


_URL_RE   = re.compile(r'https?://\S+|www\.\S+', re.I)
_rate     = _RateTracker()


def check(rule: dict, username: str, text: str) -> bool:
    kind = rule.get('check', '')

    if kind == 'caps_percent':
        min_len = rule.get('min_length', 8)
        if len(text) < min_len:
            return False
        alpha = [c for c in text if c.isalpha()]
        if not alpha:
            return False
        pct = sum(1 for c in alpha if c.isupper()) / len(alpha) * 100
        return pct >= rule.get('threshold', 70)

    if kind == 'message_rate':
        window = rule.get('window_sec', 10)
        limit  = rule.get('max_messages', 5)
        key    = f'rate:{username.lower()}'
        return _rate.add(key, window, limit)

    if kind == 'word_match':
        words  = rule.get('words', [])
        mode   = rule.get('mode', 'contains')
        lower  = text.lower()
        if mode == 'exact':
            msg_words = set(re.findall(r'\w+', lower))
            return bool(msg_words & set(w.lower() for w in words))
        elif mode == 'contains':
            return any(w.lower() in lower for w in words)
        elif mode == 'regex':
            return any(re.search(w, text, re.I) for w in words)

    if kind == 'link':
        urls = _URL_RE.findall(text)
        if not urls:
            return False
        allow = [d.lower() for d in rule.get('allow_domains', [])]
        if not allow:
            return True
        for url in urls:
            try:
                host = urllib.parse.urlparse(url).netloc.lower()
                host = host.lstrip('www.')
                if not any(host.endswith(d.lstrip('www.')) for d in allow):
                    return True
            except Exception:
                return True
        return False

    if kind == 'repeat':
        count  = rule.get('count', 3)
        window = rule.get('window_sec', 120)
        key    = f'rep:{username.lower()}'
        return _rate.add_text(key, text, window, count)

    return False
