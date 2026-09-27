"""
oo_storage — JSON persistence with optional async Postgres (Neon) sync.

Primary: local JSON files in data dir.
Optional: async fire-and-forget upsert to Neon Postgres (set OO_PG_URL).
"""

import asyncio
import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

from .oo_paths import data_file, get_data_dir

log = logging.getLogger('oo.storage')

_PG_SYNCED_KEYS = {
    'profiles', 'moderation', 'watchlist', 'mod_log',
    'memory', 'relationship', 'osrs_companion', 'music_state',
}

_pg_pool = None
_pg_ready = asyncio.Event()


async def _init_pg(url: str):
    global _pg_pool
    try:
        import asyncpg
        _pg_pool = await asyncpg.create_pool(
            url,
            min_size=1, max_size=2,
            command_timeout=10,
        )
        async with _pg_pool.acquire() as conn:
            await conn.execute(
                "CREATE TABLE IF NOT EXISTS oo_kv "
                "(key TEXT PRIMARY KEY, data JSONB, updated_at TIMESTAMPTZ DEFAULT now())"
            )
        _pg_ready.set()
        log.info('[Storage] Postgres ready')
        asyncio.get_event_loop().create_task(_pg_heartbeat())
    except Exception as e:
        log.warning(f'[Storage] Postgres unavailable: {e}')


async def _pg_heartbeat():
    while True:
        await asyncio.sleep(20)
        try:
            async with _pg_pool.acquire() as conn:
                await conn.execute('SELECT 1')
        except Exception:
            pass


async def init(pg_url: str | None = None):
    url = pg_url or os.environ.get('OO_PG_URL', '').strip()
    if url:
        await _init_pg(url)


# ── Sync read/write (local JSON) ──────────────────────────────────────────────

def read(key: str, fallback: Any = None) -> Any:
    path = data_file(f'{key}.json')
    try:
        return json.loads(path.read_text('utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback if fallback is not None else {}


def write(key: str, data: Any):
    path = data_file(f'{key}.json')
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)
    if _pg_pool and key in _PG_SYNCED_KEYS:
        asyncio.get_event_loop().call_soon_threadsafe(
            lambda: asyncio.ensure_future(_pg_write(key, data))
        )


async def _pg_write(key: str, data: Any):
    if not _pg_pool:
        return
    try:
        async with _pg_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO oo_kv(key, data) VALUES($1, $2) "
                "ON CONFLICT(key) DO UPDATE SET data=$2, updated_at=now()",
                key, json.dumps(data),
            )
    except Exception as e:
        log.debug(f'[Storage] pg write failed for {key}: {e}')


async def restore_from_pg():
    if not _pg_pool:
        return
    try:
        await _pg_ready.wait()
        async with _pg_pool.acquire() as conn:
            rows = await conn.fetch("SELECT key, data FROM oo_kv")
        for row in rows:
            path = data_file(f'{row["key"]}.json')
            path.write_text(row['data'], encoding='utf-8')
        log.info(f'[Storage] Restored {len(rows)} keys from Postgres')
    except Exception as e:
        log.warning(f'[Storage] restore_from_pg failed: {e}')


# ── Backup rotation ───────────────────────────────────────────────────────────

def backup(max_backups: int = 48):
    data_dir = get_data_dir()
    backup_dir = data_dir.parent / 'backups'
    backup_dir.mkdir(exist_ok=True)
    ts = time.strftime('%Y%m%dT%H%M%S')
    slot = backup_dir / ts
    slot.mkdir()
    for f in data_dir.glob('*.json'):
        shutil.copy2(f, slot / f.name)
    # Prune old backups
    entries = sorted(backup_dir.iterdir(), key=lambda p: p.name)
    for old in entries[:-max_backups]:
        shutil.rmtree(old, ignore_errors=True)
    log.debug(f'[Storage] Backup written to {slot}')
