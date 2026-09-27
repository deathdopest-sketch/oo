"""
OoOsrs — OSRS companion: session invites, player-like reactions, hiscores lookup.
ó_ò has her own account she references. She invites the owner to play. She talks like she plays.
"""

import asyncio
import logging
import os
import random
import time

import aiohttp

log = logging.getLogger('oo.companion.osrs')

_OWNER_USERNAME = os.environ.get('OO_OWNER_USERNAME', 'n_n').lower()
_INVITE_HOURS   = [int(h) for h in
                   os.environ.get('OO_OSRS_INVITE_HOURS', '18,19,20').split(',')
                   if h.strip().isdigit()]
_OSRS_HISCORES  = 'https://secure.runescape.com/m=hiscore_oldschool/index_lite.ws?player={}'

# Her own account — persistent across sessions
_OO_ACCOUNT = {
    'name':    'oo_ironwoman',   # her account name she references
    'goals':   ['get infernal cape', 'max herblore', 'finish ToB', 'get quest cape', '99 slayer'],
    'current_goal': 0,
}

_INVITE_LINES = [
    "yo {owner} wanna do some Chambers rn",
    "nn you on rs? just started a Nightmare instance",
    "doing slayer if you want to hop in {owner}",
    "{owner} you around? tryna do ToB",
    "about to grind some CoX solo, you in {owner}",
    "yo {owner} I'm like 3k off 99 herb, come watch me suffer",
]

_REACTION_LINES = {
    'inferno':   ["yeah infernal is genuinely brutal. jads with healers is a different game",
                  "took me actual weeks. the fight caves before it is tedious but the real test is those last waves"],
    'tob':       ["ToB is the best designed raid imo. learning it with a good team is actually fun",
                  "tob learning phase is painful. once it clicks it's the most satisfying content in the game"],
    'cox':       ["CoX is more accessible but less interesting mechanically. good starting raid though",
                  "Chambers is decent. olm is annoying until you learn it"],
    'ironman':   ["ironman is just correct. the GE kills the game for mains",
                  "btw mode. everything means more when you earned it yourself"],
    'slayer':    ["slayer is the most balanced skill in the game imo. everything useful requires it",
                  "slayer is genuinely good. turael boost strat for hard tasks though"],
    'pk':        ["wildy PK is the purest part of the game. you risk it you lose it, no insurance",
                  "PKing is either incredibly satisfying or incredibly tilting, nothing in between"],
    '99':        ["grats on the grind. which one?",
                  "99s take forever or no time at all depending on the skill"],
    'jagex':     ["Jagex's update philosophy is peak comedy. they polled something 8 times, it failed, then did it anyway",
                  "jagex be like 'the community asked for this' about something nobody asked for"],
    'barrows':   ["barrows is good early. drops feel meaningful until they don't"],
    'clue':      ["elite clues are my nemesis. rewards rarely match the effort but the steps are kind of fun",
                  "master clues are just cruelty disguised as content"],
    'gp':        ["the GE economy is actually interesting if you pay attention. some items are stupidly manipulated",
                  "gp per hour is a whole career path in this game"],
    'vorkath':   ["vorkath is reliable gp/hr once you learn him. acid phase is the one that gets people",
                  "vorkath is mid-game gold standard"],
    'zulrah':    ["zulrah will make you quit and then you'll be addicted when you figure it out",
                  "zulrah muscle memory takes a month minimum"],
}

_OSRS_KEYWORDS = list(_REACTION_LINES.keys()) + [
    'runescape', 'osrs', 'rs', 'oldschool', 'firecape', 'bandos', 'armadyl',
    'saradomin', 'zamorak', 'gwd', 'raid', 'bossing', 'quest cape', 'maxed',
    'prayer flicking', 'flick', 'herblore', 'agility', 'woodcutting', 'fletching',
]


class OoOsrs:

    def __init__(self, queue, rooms: list[str]):
        self._queue  = queue
        self._rooms  = [r.lower() for r in rooms]
        self._last_invite = 0.0
        self._current_goal = 0

    async def start(self):
        asyncio.ensure_future(self._invite_loop())
        log.info('[OSRS] Companion started')

    async def _invite_loop(self):
        while True:
            await asyncio.sleep(60)
            import datetime
            now_hour = datetime.datetime.now().hour
            if now_hour not in _INVITE_HOURS:
                continue
            if time.time() - self._last_invite < 3600:
                continue
            if random.random() < 0.35 and self._rooms:
                room = self._rooms[0]
                line = random.choice(_INVITE_LINES).format(owner=_OWNER_USERNAME)
                await self._queue.enqueue(room, line, force=True)
                self._last_invite = time.time()

    def get_reaction(self, text: str) -> str | None:
        lower = text.lower()
        for keyword, lines in _REACTION_LINES.items():
            if keyword in lower:
                if random.random() < 0.45:
                    return random.choice(lines)
        return None

    def is_osrs_message(self, text: str) -> bool:
        lower = text.lower()
        return any(k in lower for k in _OSRS_KEYWORDS)

    async def lookup_hiscores(self, username: str) -> str:
        url = _OSRS_HISCORES.format(username.replace(' ', '+'))
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                    if r.status != 200:
                        return f"can't find {username} on hiscores"
                    text = await r.text()
            return _parse_hiscores(username, text)
        except Exception as e:
            log.debug(f'[OSRS] hiscores error: {e}')
            return f'hiscores lookup failed for {username}'

    def current_goal(self) -> str:
        g = _OO_ACCOUNT['goals'][self._current_goal % len(_OO_ACCOUNT['goals'])]
        return f"working on: {g}"

    def advance_goal(self):
        self._current_goal = (self._current_goal + 1) % len(_OO_ACCOUNT['goals'])


_SKILLS = [
    'total', 'attack', 'defence', 'strength', 'hitpoints', 'ranged',
    'prayer', 'magic', 'cooking', 'woodcutting', 'fletching', 'fishing',
    'firemaking', 'crafting', 'smithing', 'mining', 'herblore', 'agility',
    'thieving', 'slayer', 'farming', 'runecrafting', 'hunter', 'construction',
]


def _parse_hiscores(username: str, raw: str) -> str:
    lines = raw.strip().split('\n')
    skills = {}
    for i, line in enumerate(lines[:len(_SKILLS)]):
        parts = line.strip().split(',')
        if len(parts) >= 3:
            try:
                level = int(parts[1])
                skills[_SKILLS[i]] = level
            except ValueError:
                pass
    if not skills:
        return f"couldn't parse hiscores for {username}"

    total = skills.get('total', 0)
    combat = [
        ('atk', skills.get('attack', 1)),
        ('def', skills.get('defence', 1)),
        ('str', skills.get('strength', 1)),
        ('hp', skills.get('hitpoints', 10)),
        ('rng', skills.get('ranged', 1)),
        ('pray', skills.get('prayer', 1)),
        ('mage', skills.get('magic', 1)),
    ]
    combat_str = ' '.join(f'{n}:{v}' for n, v in combat)
    return f'{username} | total: {total} | {combat_str}'
