"""
OoPsych — message signal processor.
Scores each message for intent, emotion, and social dynamics.
"""

import re
from typing import NamedTuple


class PsychResult(NamedTuple):
    score:       float   # 0–1 overall signal strength
    intent:      str     # 'question' | 'statement' | 'provocation' | 'greeting' | 'command'
    emotion:     str     # 'neutral' | 'positive' | 'negative' | 'angry' | 'sad' | 'excited'
    is_directed: bool    # message seems directed at bot
    tech_mode:   bool    # coding/tech question
    music_mode:  bool    # music discussion
    osrs_mode:   bool    # OSRS discussion
    flirt_mode:  bool
    bot_callout: bool


_POSITIVE = {'good', 'great', 'love', 'amazing', 'nice', 'thanks', 'awesome', 'yes', 'yeah',
             'lol', 'haha', 'fun', 'cool', 'dope', 'sick', 'lit'}
_NEGATIVE = {'bad', 'hate', 'sucks', 'terrible', 'awful', 'no', 'stop', 'wtf', 'fuck', 'shit',
             'idiot', 'stupid', 'dumb', 'boring', 'annoying'}
_ANGRY    = {'fuck', 'fuckyou', 'idiot', 'stupid', 'moron', 'asshole', 'bitch', 'cunt', 'kys'}
_SAD      = {'sad', 'depressed', 'lonely', 'alone', 'hurt', 'cry', 'crying', 'miss', 'lost'}
_EXCITED  = {'!!!', 'omg', 'lmao', 'wtf', 'yoooo', 'noooo', 'plsss', 'rip'}

_TECH_KW  = {'code', 'bug', 'error', 'python', 'node', 'server', 'deploy', 'git', 'css', 'html',
             'api', 'function', 'database', 'crash', 'npm', 'install', 'socket', 'nginx', 'pm2'}
_MUSIC_KW = {'music', 'song', 'track', 'play', 'house', 'edm', 'rave', 'dj', 'set', 'mix',
             'techno', 'bpm', 'drop', 'vinyl', 'club', 'trance', 'drum', 'bass', 'playlist'}
_OSRS_KW  = {'osrs', 'runescape', 'rs', 'gp', 'ge', 'inferno', 'tob', 'cox', 'nex',
             'slayer', 'ironman', 'maxed', 'prayer', 'clue', 'pvm', 'bossing', 'grind',
             'skill', 'cape', 'firecape', 'raid', 'herblore', 'fletching', 'woodcutting',
             'agility', 'zulrah', 'vorkath', 'kalphite', 'barrows', 'flick', 'flicking',
             'jagex', 'mobile', 'oldschool', '99', 'pk', 'pking', 'pvp', 'wildy',
             'wilderness', 'gwd', 'bandos', 'armadyl', 'zamorak', 'saradomin'}
_FLIRT_KW = {'sexy', 'hot', 'cute', 'beautiful', 'attractive', 'gorgeous', 'want you',
             'like you', 'date', 'relationship', 'kiss', 'flirt', 'love you'}
_BOT_KW   = re.compile(r'\b(are you (a )?(bot|ai)|you\'re (a )?(bot|ai)|just a bot)\b', re.I)

_GREETING = re.compile(r'^\s*(hey|hi|hello|sup|yo|hiya|heya|oi)\b', re.I)
_PROVOKE   = re.compile(r'\b(fight|debate|prove|wrong|liar|bullshit|cap|no you)\b', re.I)


def analyze(text: str, bot_nick: str = 'oo') -> PsychResult:
    lower  = text.lower()
    words  = set(re.findall(r'\w+', lower))
    score  = min(1.0, len(text.split()) / 20)

    intent = 'statement'
    if '?' in text:
        intent = 'question'
        score  = min(1.0, score + 0.2)
    elif _PROVOKE.search(lower):
        intent = 'provocation'
        score  = min(1.0, score + 0.3)
    elif _GREETING.match(text):
        intent = 'greeting'

    # Emotion
    if words & _ANGRY:
        emotion = 'angry'
    elif words & _SAD:
        emotion = 'sad'
    elif any(e in text for e in _EXCITED):
        emotion = 'excited'
    elif len(words & _POSITIVE) > len(words & _NEGATIVE):
        emotion = 'positive'
    elif words & _NEGATIVE:
        emotion = 'negative'
    else:
        emotion = 'neutral'

    is_directed = bot_nick.lower() in lower or intent == 'question'
    tech_mode   = bool(words & _TECH_KW)
    music_mode  = bool(words & _MUSIC_KW)
    osrs_mode   = bool(words & _OSRS_KW)
    flirt_mode  = any(k in lower for k in _FLIRT_KW)
    bot_callout = bool(_BOT_KW.search(text))

    return PsychResult(
        score=round(score, 2),
        intent=intent,
        emotion=emotion,
        is_directed=is_directed,
        tech_mode=tech_mode,
        music_mode=music_mode,
        osrs_mode=osrs_mode,
        flirt_mode=flirt_mode,
        bot_callout=bot_callout,
    )
