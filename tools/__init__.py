"""
Auto-discovers OoTool subclasses in this directory.
"""

import importlib
import logging
import pkgutil
from pathlib import Path
from .oo_tool_base import OoTool

log = logging.getLogger('oo.tools')
_tools: dict[str, OoTool] = {}


def load_tools() -> dict[str, OoTool]:
    pkg_dir = Path(__file__).parent
    for finder, module_name, _ in pkgutil.iter_modules([str(pkg_dir)]):
        if module_name.startswith('_') or module_name == 'oo_tool_base':
            continue
        try:
            mod = importlib.import_module(f'tools.{module_name}')
            for attr in dir(mod):
                obj = getattr(mod, attr)
                if (isinstance(obj, type) and issubclass(obj, OoTool)
                        and obj is not OoTool and obj.name):
                    instance = obj()
                    _tools[instance.name.lower()] = instance
                    log.info(f'[Tools] Loaded: .{instance.name}')
        except Exception as e:
            log.error(f'[Tools] Failed to load {module_name}: {e}')
    return _tools


def get_tools() -> dict[str, OoTool]:
    return _tools
