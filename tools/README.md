# Adding a Tool to ó_ò

1. Create a `.py` file in this directory (e.g. `my_tool.py`)
2. Import `OoTool` and define a subclass:

```python
from oo_tool_base import OoTool

class MyTool(OoTool):
    name        = 'mycommand'        # .mycommand in chat
    description = 'does the thing'
    cooldown_ms = 5000
    tier        = 'user'             # 'user', 'mod', or 'owner'

    async def run(self, args: list[str], context: dict) -> str | None:
        # args = list of words after the command
        # context = {'room', 'nick', 'handle', 'bot'}
        return f'you said: {" ".join(args)}'
```

3. Restart the bot. The tool appears automatically in `.help`.

No other files to edit. Done.
