"""
Plugin system for DFlow CLI adapters.

Provides extensible plugin architecture for customizing donation data processing
without modifying core adapter code.
"""

from .registry import register_plugin, get_plugins, clear_registry
from .loader import load_plugins

__all__ = [
    "register_plugin",
    "get_plugins",
    "clear_registry",
    "load_plugins",
]
