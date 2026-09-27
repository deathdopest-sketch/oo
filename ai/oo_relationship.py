"""
OoRelationship — tracks trust, depth, and topics per user per room.
Feeds signal into the personality system prompt context.
"""

import logging
import time
from collections import Counter
from typing import NamedTuple

from storage import read, write

log = logging.getLogger('oo.ai.relationship')

_MAX_USERS_PER_ROOM = 120
_MAX_TOPICS         = 10
_DECAY_SECS         = 6 * 3600

_DEEP_WORDS = {'feel', 'think', 'believe', 'meaning', 'life', 'death',
               'love', 'hurt', 'lonely', 'afraid', 'hope', 'dark', 'empty'}
_CASUAL     = {'lol', 'lmao', 'haha', 'ok', 'yeah', 'idk', 'nah', 'bruh'}


class RelSignal(NamedTuple):
    relationship: str   # 'new' | 'familiar' | 'trusted'
    depth: float        # 0–10
    topic_hint: str
    line: str           # context line for system prompt


class OoRelationship:

    def __init__(self):
        self._data: dict[str, dict] = read('relationship', {})
        # key = f"{room}:{handle}"

    def observe(self, room: str, nick: str, handle: str, text: str):
        key   = f'{room.lower()}:{handle}'
        now   = time.time()
        entry = self._data.get(key)

        if entry is None:
            # Evict if room is full
            room_entries = [k for k in self._data if k.startswith(f'{room.lower()}:')]
            if len(room_entries) >= _MAX_USERS_PER_ROOM:
                oldest = min(room_entries, key=lambda k: self._data[k].get('last_seen', 0))
                del self._data[oldest]
            entry = {
                'nick': nick, 'first_seen': now, 'last_seen': now,
                'messages': 0, 'questions': 0, 'depth': 0.0, 'topics': {},
            }
            self._data[key] = entry

        entry['last_seen'] = now
        entry['nick']      = nick
        entry['messages'] += 1
        if '?' in text:
            entry['questions'] += 1

        # Depth scoring
        words  = set(text.lower().split())
        deep   = len(words & _DEEP_WORDS)
        casual = len(words & _CASUAL)
        if deep:
            entry['depth'] = min(10.0, entry['depth'] + deep * 0.5)
        if casual:
            entry['depth'] = max(0.0, entry['depth'] - casual * 0.1)

        # Topic tracking
        topics: dict = entry.setdefault('topics', {})
        for w in words:
            if len(w) > 4 and w.isalpha() and w not in _CASUAL:
                topics[w] = topics.get(w, 0) + 1
        if len(topics) > _MAX_TOPICS:
            keep = sorted(topics.items(), key=lambda x: -x[1])[:_MAX_TOPICS]
            entry['topics'] = dict(keep)

        # Periodic save
        if entry['messages'] % 25 == 0:
            self.save()

    def get_signals(self, room: str, handle: str) -> RelSignal:
        key   = f'{room.lower()}:{handle}'
        entry = self._data.get(key)
        if not entry:
            return RelSignal('new', 0.0, '', '[User: new arrival]')

        msgs = entry.get('messages', 0)
        if msgs < 12:
            rel = 'new'
        elif msgs < 40:
            rel = 'familiar'
        else:
            rel = 'trusted'

        depth = round(entry.get('depth', 0.0), 1)
        topics_raw = entry.get('topics', {})
        top_topics = sorted(topics_raw.items(), key=lambda x: -x[1])[:3]
        topic_hint = ', '.join(t[0] for t in top_topics)

        line = f'[User: rel={rel} depth={depth}/10 msgs={msgs}'
        if topic_hint:
            line += f' talks_about={topic_hint}'
        line += ']'

        return RelSignal(rel, depth, topic_hint, line)

    def save(self):
        write('relationship', self._data)
