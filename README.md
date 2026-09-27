# ó_ò

a companion bot for ChatCommon and MumbleChat. not a utility. not a game engine. a presence.

she runs moderation autonomously, keeps the room alive, plays OSRS like an actual person, knows house music from the ground up, and has genuine opinions about cooking, growing, and code. built in Python for Linux, drops on any server without touching a config file.

---

## what she does

**companion**
sits in the room and actually participates. dry timing, specific knowledge, reads the energy. when she likes someone she shows it. when something bores her she goes quiet. she doesn't perform.

**OSRS**
plays alongside you. invites you to raids. reacts to what you're grinding. looks up hiscores on command. talks like someone who actually logs in, not a wiki.

**house music**
deep knowledge from Chicago '77 to now. drops track recommendations unprompted. has opinions about specific records and isn't shy about them.

**moderation**
full site moderation suite running in the background. customisable rules, auto-escalation, audit log, shadow ban, per-user strike tracking. owner edits `moderation/rules.json` directly — no restart needed to change a rule.

**site watch**
monitors room health and reports to the owner. drama alerts, daily summaries, server uptime checks, room activity spikes — all DM'd proactively.

**tool plugins**
drop a `.py` file in `tools/`, restart, it appears in `.help`. no registration, no config.

---

## knowledge

- **house / EDM** — Paradise Garage to now. Frankie Knuckles, Larry Heard, Kerri Chandler, Fisher, Eric Prydz. actual depth, not surface level
- **OSRS** — current meta, bossing, ironman builds, GE, the community drama cycle
- **cannabis (legal)** — strain genetics, LST/SCROG/manifold, VPD, nutrient diagnosis, dry and cure
- **cooking** — technique first. Maillard, emulsification, acid balance, knife work
- **coding / Linux** — Python, Node, nginx, PM2, systemd, WebSocket debugging, the whole stack
- **random online** — video essays, obscure docs, rabbit holes. "have you seen that thing about..." energy

---

## commands

| command | who | what |
|---------|-----|------|
| `.help` | everyone | lists available commands |
| `.osrs <username>` | everyone | hiscores lookup |
| `.music [genre]` | everyone | drops a track recommendation |
| `.goal` | everyone | what she's currently grinding in OSRS |
| `.report <nick> [reason]` | everyone | flags a user for owner review |
| `.mod rules` | owner | shows active moderation rules |
| `.mod enable/disable <id>` | owner | toggle a rule live |
| `.mod set <id> <field> <value>` | owner | edit a rule field live |
| `.mod warn/mute/kick/ban <nick>` | owner | manual moderation actions |
| `.mod watchlist` | owner | shows users with active strikes |
| `.mod log [n]` | owner | recent mod action log |
| `.mod reports` | owner | pending user reports |
| `.mod exempt <nick>` | owner | session-exempt a user from automod |

---

## setup

```bash
git clone https://github.com/deathdopest-sketch/oo
cd oo
pip install python-socketio[asyncio_client] websockets curl_cffi aiohttp python-dotenv asyncpg
cp .env.example .env
# fill in .env — at minimum: MUMBLECHAT_BOT_KEY and OO_OWNER_USERNAME
python oo.py
```

data writes to `~/.oo/data/` automatically. no path config needed.

---

## adding a tool

```python
# tools/my_tool.py
from tools.oo_tool_base import OoTool

class MyTool(OoTool):
    name        = 'mycommand'
    description = 'does the thing'
    cooldown_ms = 5000
    tier        = 'user'

    async def run(self, args, context):
        return f'you said: {" ".join(args)}'
```

restart the bot. appears in `.help` automatically.

---

## platforms

| platform | method |
|----------|--------|
| MumbleChat | Socket.IO with bot key auth |
| ChatCommon | raw WebSocket + Cloudflare bypass via curl_cffi |

both adapters have a `PROTOCOL` dict at the top of their file. if the server renames a field, change one line.

---

## stack

Python 3.11+ · asyncio · Ollama (local LLM) · Groq (cloud fallback) · aiohttp · websockets · python-socketio · curl_cffi · asyncpg
