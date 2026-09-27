"""
OoMusic — weighted genre selector with proactive drop scheduler.
ó_ò is obsessed with house music. She drops tracks naturally.
"""

import asyncio
import json
import logging
import os
import random
import time
from pathlib import Path

log = logging.getLogger('oo.music')

_PACK_DIR = Path(__file__).parent / 'packs'

_GENRES = {
    'house':         30,   # Chicago house — highest weight, her roots
    'deep_house':    25,
    'tech_house':    20,
    'melodic_house': 15,
    'progressive':   10,
    'drum_bass':      5,
    'edm':            8,
    'trance':         4,
}

_DROP_LINES = [
    "{artist} - {title} {url}",
    "been listening to {artist} on repeat   {url}",
    "if you haven't heard {artist} you're genuinely missing out   {url}",
    "{artist} - {title} goes hard   {url}",
    "oi has anyone heard {artist}   {url}",
    "I always come back to this one   {artist} - {title}   {url}",
]


class OoMusic:

    def __init__(self):
        self._packs: dict[str, list[dict]] = {}
        self._weights: list[tuple[str, int]] = []
        self._loaded = 0

    def load(self):
        for genre in _GENRES:
            path = _PACK_DIR / f'{genre}.json'
            if path.exists():
                try:
                    tracks = json.loads(path.read_text('utf-8'))
                    self._packs[genre] = tracks
                    self._loaded += len(tracks)
                except Exception as e:
                    log.warning(f'[Music] Failed to load {genre}: {e}')
        self._weights = [(g, w) for g, w in _GENRES.items() if g in self._packs]
        log.info(f'[Music] Loaded {self._loaded} tracks across {len(self._packs)} genres')

    def get_random(self) -> dict | None:
        genres = [g for g, _ in self._weights]
        weights = [w for _, w in self._weights]
        if not genres:
            return None
        genre = random.choices(genres, weights=weights, k=1)[0]
        tracks = self._packs.get(genre, [])
        return random.choice(tracks) if tracks else None

    def get_genre(self, genre: str) -> dict | None:
        tracks = self._packs.get(genre.lower(), [])
        return random.choice(tracks) if tracks else None

    def youtube_url(self, video_id: str) -> str:
        return f'https://youtu.be/{video_id}' if video_id else ''

    def format_drop(self, track: dict) -> str:
        url  = self.youtube_url(track.get('videoId', ''))
        tmpl = random.choice(_DROP_LINES)
        return tmpl.format(
            artist=track.get('artist', ''),
            title=track.get('title', ''),
            url=url,
        ).strip()

    def total_tracks(self) -> int:
        return self._loaded


class OoMusicDropper:

    def __init__(self, music: OoMusic, queue, rooms: list[str]):
        self._music  = music
        self._queue  = queue
        self._rooms  = [r.lower() for r in rooms]
        self._last   = 0.0

    async def start(self):
        asyncio.ensure_future(self._loop())

    async def _loop(self):
        while True:
            delay = (20 + random.random() * 25) * 60
            await asyncio.sleep(delay)
            if random.random() < 0.4 and self._rooms:
                track = self._music.get_random()
                if track:
                    room = random.choice(self._rooms)
                    line = self._music.format_drop(track)
                    await self._queue.enqueue(room, line, force=True)
