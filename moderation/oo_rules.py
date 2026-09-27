"""
OoRules — load, save, enable/disable rules at runtime.
"""

import json
import logging
from pathlib import Path

log = logging.getLogger('oo.mod.rules')

_DEFAULT_PATH = Path(__file__).parent / 'rules.json'


class OoRules:

    def __init__(self, path: Path | None = None):
        self._path = path or _DEFAULT_PATH
        self._config = self._load()

    def _load(self) -> dict:
        try:
            return json.loads(self._path.read_text('utf-8'))
        except Exception as e:
            log.error(f'[Rules] Failed to load {self._path}: {e}')
            return {'rules': [], 'exempt_roles': [], 'log_all_actions': True,
                    'dm_user_on_action': True}

    def _save(self):
        self._path.write_text(
            json.dumps(self._config, indent=2, ensure_ascii=False), encoding='utf-8'
        )

    def get_active(self) -> list[dict]:
        return [r for r in self._config.get('rules', []) if r.get('enabled', True)]

    def get_all(self) -> list[dict]:
        return self._config.get('rules', [])

    def get_rule(self, rule_id: str) -> dict | None:
        for r in self._config.get('rules', []):
            if r['id'] == rule_id:
                return r
        return None

    def enable(self, rule_id: str) -> bool:
        r = self.get_rule(rule_id)
        if r:
            r['enabled'] = True
            self._save()
            return True
        return False

    def disable(self, rule_id: str) -> bool:
        r = self.get_rule(rule_id)
        if r:
            r['enabled'] = False
            self._save()
            return True
        return False

    def set_field(self, rule_id: str, field: str, value) -> bool:
        r = self.get_rule(rule_id)
        if r and field in r:
            # Try to cast value to the same type as current field
            current = r[field]
            try:
                if isinstance(current, bool):
                    r[field] = value.lower() in ('true', '1', 'yes') if isinstance(value, str) else bool(value)
                elif isinstance(current, int):
                    r[field] = int(value)
                elif isinstance(current, float):
                    r[field] = float(value)
                elif isinstance(current, list):
                    # Value should be JSON-encoded list or comma-sep string
                    try:
                        r[field] = json.loads(value) if isinstance(value, str) else value
                    except json.JSONDecodeError:
                        r[field] = [v.strip() for v in str(value).split(',')]
                else:
                    r[field] = value
            except (ValueError, TypeError):
                r[field] = value
            self._save()
            return True
        return False

    def is_exempt(self, role: str) -> bool:
        return role in self._config.get('exempt_roles', [])

    def dm_on_action(self) -> bool:
        return self._config.get('dm_user_on_action', True)

    def format_rules(self) -> str:
        lines = []
        for r in self.get_all():
            status = '✓' if r.get('enabled') else '✗'
            lines.append(f'{status} [{r["id"]}] {r.get("description", "")} → {r.get("action", "")}')
        return '\n'.join(lines) if lines else 'no rules configured'
