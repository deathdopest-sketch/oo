"""
OSRS hiscores lookup tool.
Usage: .osrs <username>
"""

from .oo_tool_base import OoTool


class OsrsLookupTool(OoTool):
    name        = 'osrs'
    description = 'look up an OSRS account on hiscores — .osrs <username>'
    cooldown_ms = 8_000
    tier        = 'user'

    async def run(self, args: list[str], context: dict) -> str | None:
        if not args:
            return 'usage: .osrs <username>'
        username = ' '.join(args)
        bot = context.get('bot')
        if bot and hasattr(bot, '_osrs'):
            return await bot._osrs.lookup_hiscores(username)
        return f'hiscores lookup not available'
