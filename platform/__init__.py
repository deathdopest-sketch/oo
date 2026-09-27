from .base import OoPlatform

__all__ = ['OoPlatform']

# ChatCommonPlatform and MumbleChatPlatform are imported lazily in oo.py
# to avoid hard-crashing if a platform's deps aren't installed.
