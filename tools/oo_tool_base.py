"""
OoTool — base class for all tool modules.

To add a tool:
  1. Create a .py file in this directory.
  2. Define a class that inherits OoTool.
  3. Set name, description. Implement run().
  4. Restart the bot — it's auto-discovered.
"""

from abc import ABC, abstractmethod


class OoTool(ABC):
    name:        str = ''       # command trigger (e.g. "osrs")
    description: str = ''       # shown in .help
    cooldown_ms: int = 5_000
    tier:        str = 'user'   # 'user' | 'mod' | 'owner'

    @abstractmethod
    async def run(self, args: list[str], context: dict) -> str | None:
        """
        context = {
            'room':   str,
            'nick':   str,
            'handle': str,
            'bot':    OoBot instance,
        }
        Return a string to send as a reply, or None for no reply.
        """
        ...
