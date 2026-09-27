"""
oo_paths — self-discovering data directory resolver.
No hardcoded paths. Works on any Linux or Windows machine.
"""

from pathlib import Path
import os


def get_data_dir() -> Path:
    # 1. Explicit env var override (highest priority)
    env = os.environ.get('OO_DATA_DIR', '').strip()
    if env:
        p = Path(env)
        p.mkdir(parents=True, exist_ok=True)
        return p

    # 2. ~/.oo/data/ (Linux home — default for site owner)
    home = Path.home() / '.oo' / 'data'
    try:
        home.mkdir(parents=True, exist_ok=True)
        return home
    except OSError:
        pass

    # 3. <script_dir>/oo_data/ (fallback next to oo.py)
    here = Path(__file__).resolve().parent.parent / 'oo_data'
    here.mkdir(parents=True, exist_ok=True)
    return here


def get_log_dir() -> Path:
    p = get_data_dir().parent / 'logs'
    p.mkdir(parents=True, exist_ok=True)
    return p


def data_file(name: str) -> Path:
    return get_data_dir() / name


def log_file(name: str) -> Path:
    return get_log_dir() / name
