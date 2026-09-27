"""
OoEngine — evaluates each message against active moderation rules.
"""

import logging

from .oo_automod import check
from .oo_actions import OoActions
from .oo_rules import OoRules
from .oo_watchlist import OoWatchlist

log = logging.getLogger('oo.mod.engine')


class OoEngine:

    def __init__(self, rules: OoRules, actions: OoActions,
                 watchlist: OoWatchlist, identity):
        self._rules     = rules
        self._actions   = actions
        self._watchlist = watchlist
        self._identity  = identity

    async def evaluate(self, room: str, nick: str, handle: str, text: str,
                        message_id: str = '', platform_name: str = '') -> bool:
        """Returns True if message was actioned (caller may want to suppress AI reply)."""
        # Exempt owners/mods
        role = self._identity.get_role(nick, handle)
        if self._rules.is_exempt(role):
            return False

        # Shadow-banned users — silently ignore
        if self._actions.is_shadow_banned(nick):
            return True

        # Already banned
        if self._watchlist.is_banned(nick):
            return True

        # Muted
        if self._watchlist.is_muted(nick):
            return True

        for rule in self._rules.get_active():
            if not check(rule, nick, text):
                continue

            action      = rule.get('action', 'warn')
            duration    = rule.get('mute_duration_sec',
                          rule.get('duration_sec', 300))
            rule_id     = rule.get('id', '')

            # Auto-escalate: if enough strikes, upgrade warn to mute
            if action == 'warn':
                threshold = rule.get('strikes_before_mute', 3)
                strikes   = self._watchlist.get_strikes(nick)
                if strikes >= threshold - 1:
                    action   = 'mute'
                    duration = rule.get('mute_duration_sec', 300)

            await self._actions.execute(
                action, room, nick, rule_id=rule_id,
                duration_sec=duration, platform_name=platform_name,
            )

            # Delete if needed
            if 'delete' in action and message_id:
                plat = self._actions._get_platform(platform_name)
                if plat:
                    try:
                        await plat.delete_message(room, message_id)
                    except Exception:
                        pass

            # DM the user if configured
            if self._rules.dm_on_action():
                desc = rule.get('description', 'message violated room rules')
                try:
                    plat = self._actions._get_platform(platform_name)
                    if plat:
                        await plat.send_pm(nick, f'hey {nick}: {desc}', handle)
                except Exception:
                    pass

            return True

        return False
