#!/usr/bin/env python3
"""
ó_ò — entry point.

Usage:
    python oo.py

Reads .env from the same directory, selects platform(s) based on OO_PLATFORM,
launches OoBot, and handles graceful shutdown on SIGTERM/SIGINT.
"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

# Load .env before anything imports config
from dotenv import load_dotenv
_env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=_env_path, override=False)

from config import load_config
from core.bot import OoBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-7s %(name)s — %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger('oo')


def _build_platforms(cfg) -> list[tuple[str, object]]:
    """Returns list of (name, platform_instance) tuples."""
    platforms = []

    use_cc = cfg.platform in ('chatcommon', 'both')
    use_mc = cfg.platform in ('mumblechat', 'both')

    if use_mc:
        if not cfg.mc_bot_key:
            log.warning('MUMBLECHAT_BOT_KEY not set — skipping MumbleChat')
        else:
            from platform.mumblechat import MumbleChatPlatform
            platforms.append(('mumblechat', MumbleChatPlatform(
                server_url=cfg.mc_server_url,
                bot_key=cfg.mc_bot_key,
            )))

    if use_cc:
        if not cfg.cc_username or not cfg.cc_password:
            log.warning('CHATCOMMON_USERNAME/PASSWORD not set — skipping ChatCommon')
        else:
            from platform.chatcommon import ChatCommonPlatform
            platforms.append(('chatcommon', ChatCommonPlatform(
                username=cfg.cc_username,
                password=cfg.cc_password,
                rooms=cfg.cc_rooms,
            )))

    if not platforms:
        log.error('No platforms configured. Set OO_PLATFORM and credentials in .env')
        sys.exit(1)

    return platforms


_BANNER = """
  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
  ░                             ░
  ░    ó _ ò                    ░
  ░    ( ´ _ ` )                ░
  ░                             ░
  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
"""


async def _main():
    cfg = load_config()
    print(_BANNER)
    log.info(f'ó_ò starting — platform={cfg.platform}')

    bot = OoBot()
    for name, plat in _build_platforms(cfg):
        bot.add_platform(name, plat)

    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    def _handle_signal(sig):
        if not stop.done():
            log.info(f'Signal {sig.name} received — shutting down')
            stop.set_result(sig)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler for all signals
            pass

    bot_task = asyncio.create_task(bot.start(), name='oo-bot')

    try:
        await stop
    except asyncio.CancelledError:
        pass
    finally:
        log.info('Stopping ó_ò...')
        await bot.stop()
        bot_task.cancel()
        try:
            await bot_task
        except (asyncio.CancelledError, Exception):
            pass
        log.info('ó_ò stopped.')


if __name__ == '__main__':
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
