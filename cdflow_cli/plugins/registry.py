"""
Plugin registry for adapter customization.

Provides decorator-based registration system for plugins that can transform
donation data at different stages of processing.
"""

from dataclasses import dataclass
from typing import Callable, Literal

PluginType = Literal["row_transformer", "field_processor", "donation_validator", "person_lookup"]

_registry: dict[str, list[tuple[str, PluginType, Callable]]] = {
    "canadahelps": [],
    "paypal": []
}


@dataclass(frozen=True)
class PluginBundle:
    """Resolved plugin collection for a single adapter run."""

    adapter: str
    all_plugins: list[tuple[str, Callable]]
    by_type: dict[PluginType, list[tuple[str, Callable]]]


def register_plugin(adapter: str, plugin_type: PluginType):
    """
    Decorator to register a plugin for an adapter.

    Args:
        adapter: Adapter name (canadahelps, paypal)
        plugin_type: Type of plugin (row_transformer, field_processor, donation_validator, person_lookup)

    Returns:
        Decorator function that registers the plugin

    Example:
        @register_plugin("canadahelps", "row_transformer")
        def sanitize_anon_fields(row_data: dict) -> dict:
            for key, value in row_data.items():
                if value == "ANON":
                    row_data[key] = ""
            return row_data
    """
    def decorator(func: Callable):
        if adapter not in _registry:
            _registry[adapter] = []
        _registry[adapter].append((func.__name__, plugin_type, func))
        return func
    return decorator


def get_plugins(adapter: str, plugin_type: PluginType = None) -> list[tuple[str, Callable]]:
    """
    Get registered plugins for an adapter, optionally filtered by type.

    Args:
        adapter: Adapter name (canadahelps, paypal)
        plugin_type: Optional filter by plugin type

    Returns:
        List of (plugin_name, plugin_function) tuples
    """
    plugins = _registry.get(adapter, [])
    if plugin_type:
        return [(name, func) for name, ptype, func in plugins if ptype == plugin_type]
    return [(name, func) for name, _, func in plugins]


def build_plugin_bundle(adapter: str) -> PluginBundle:
    """
    Build a resolved plugin bundle from the current registry state.

    Args:
        adapter: Adapter name

    Returns:
        PluginBundle: Snapshot of current plugins for the adapter
    """
    by_type: dict[PluginType, list[tuple[str, Callable]]] = {
        "row_transformer": get_plugins(adapter, "row_transformer"),
        "field_processor": get_plugins(adapter, "field_processor"),
        "donation_validator": get_plugins(adapter, "donation_validator"),
        "person_lookup": get_plugins(adapter, "person_lookup"),
    }
    return PluginBundle(adapter=adapter, all_plugins=get_plugins(adapter), by_type=by_type)


def clear_registry(adapter: str = None):
    """
    Clear plugin registry (useful for testing).

    Args:
        adapter: Optional adapter name to clear. If None, clears all adapters.
    """
    if adapter:
        _registry[adapter] = []
    else:
        for key in _registry:
            _registry[key] = []
