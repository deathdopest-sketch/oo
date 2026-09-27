"""
OoConfig — typed config object loaded from environment variables.
Call load_config() after dotenv.load_dotenv() has run.
"""

import os
from dataclasses import dataclass, field


@dataclass
class OoConfig:
    platform: str                   # 'chatcommon' | 'mumblechat' | 'both'

    # ChatCommon
    cc_username: str
    cc_password: str
    cc_rooms: list[str]

    # MumbleChat
    mc_bot_key: str
    mc_server_url: str
    mc_rooms: list[str]

    # AI
    ollama_host: str
    ollama_model: str
    groq_api_key: str

    # Identity
    bot_nick: str
    owner_username: str
    owner_nicks: list[str]
    mod_nicks: list[str]

    # Storage
    data_dir: str                   # empty = auto-discover
    pg_url: str                     # empty = no postgres

    # OSRS companion
    osrs_owner_username: str
    osrs_invite_hours: list[int]

    # Site watch
    watch_rooms: list[str]
    drama_threshold: int
    daily_summary_hour: int


def _csv(val: str) -> list[str]:
    return [v.strip() for v in val.split(',') if v.strip()]


def _int_csv(val: str) -> list[int]:
    result = []
    for v in val.split(','):
        v = v.strip()
        if v.isdigit():
            result.append(int(v))
    return result


def load_config() -> OoConfig:
    return OoConfig(
        platform=os.environ.get('OO_PLATFORM', 'mumblechat').lower(),

        cc_username=os.environ.get('CHATCOMMON_USERNAME', ''),
        cc_password=os.environ.get('CHATCOMMON_PASSWORD', ''),
        cc_rooms=_csv(os.environ.get('CHATCOMMON_ROOMS', 'd_d')),

        mc_bot_key=os.environ.get('MUMBLECHAT_BOT_KEY', ''),
        mc_server_url=os.environ.get('MUMBLECHAT_SERVER_URL', 'https://mumblechat.online'),
        mc_rooms=_csv(os.environ.get('MUMBLECHAT_ROOMS', 'ddd')),

        ollama_host=os.environ.get('OLLAMA_HOST', 'http://localhost:11434'),
        ollama_model=os.environ.get('OLLAMA_MODEL', 'dolphin3:8b'),
        groq_api_key=os.environ.get('GROQ_API_KEY', ''),

        bot_nick=os.environ.get('OO_BOT_NICK', 'ó_ò'),
        owner_username=os.environ.get('OO_OWNER_USERNAME', 'n_n'),
        owner_nicks=_csv(os.environ.get('OO_OWNER_NICKS', 'n_n,nn')),
        mod_nicks=_csv(os.environ.get('OO_MOD_NICKS', '')),

        data_dir=os.environ.get('OO_DATA_DIR', '').strip(),
        pg_url=os.environ.get('OO_PG_URL', '').strip(),

        osrs_owner_username=os.environ.get('OO_OSRS_OWNER_USERNAME', ''),
        osrs_invite_hours=_int_csv(os.environ.get('OO_OSRS_INVITE_HOURS', '18,19,20')),

        watch_rooms=_csv(os.environ.get('OO_WATCH_ROOMS', 'd_d,n_n')),
        drama_threshold=int(os.environ.get('OO_DRAMA_THRESHOLD', '3')),
        daily_summary_hour=int(os.environ.get('OO_DAILY_SUMMARY_HOUR', '23')),
    )
