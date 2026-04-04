"""
Plugin loader for auto-discovery and dynamic loading.

Scans plugin directories and loads Python modules containing plugins.
"""

import importlib.util
import logging
from pathlib import Path
import sys

from .registry import PluginBundle, build_plugin_bundle

logger = logging.getLogger(__name__)


def _import_plugin_modules(adapter: str, plugins_dir: Path) -> tuple[int, list[str]]:
    """Import plugin modules for an adapter and return file-level load metadata."""
    loaded_count = 0
    loaded_names = []

    plugin_files = sorted(plugins_dir.glob("*.py"))

    for plugin_file in plugin_files:
        if plugin_file.stem.startswith("_"):
            logger.debug(f"Skipping disabled plugin: {plugin_file.name}")
            continue

        try:
            module_name = f"cdflow_plugin_{adapter}_{plugin_file.stem}"
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)

            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[module_name] = module
                spec.loader.exec_module(module)
                loaded_count += 1
                loaded_names.append(plugin_file.name)
                logger.debug(f"Loaded plugin: {plugin_file.name}")
            else:
                logger.warning(f"Could not load plugin spec: {plugin_file.name}")

        except Exception as e:
            logger.error(f"Error loading plugin {plugin_file.name}: {e}")

    return loaded_count, loaded_names


def load_plugins(adapter: str, plugins_dir: Path) -> int:
    """
    Auto-discover and load plugins from directory.

    Scans the specified directory for Python files and imports them,
    allowing plugins to self-register using the @register_plugin decorator.

    Files are loaded in alphabetical order. Files starting with underscore
    are skipped (convention for disabling plugins).

    Args:
        adapter: Adapter name (canadahelps, paypal)
        plugins_dir: Directory containing plugin files

    Returns:
        Number of plugins loaded

    Example:
        plugins_path = Path("~/.config/cdflow/plugins/canadahelps").expanduser()
        count = load_plugins("canadahelps", plugins_path)
        logger.info(f"Loaded {count} plugins")
    """
    if not plugins_dir.exists():
        logger.info(f"Plugins directory does not exist: {plugins_dir}")
        return 0

    if not plugins_dir.is_dir():
        logger.warning(f"Plugins path is not a directory: {plugins_dir}")
        return 0

    loaded_count, loaded_names = _import_plugin_modules(adapter, plugins_dir)

    if loaded_count > 0:
        logger.info(f"Loaded {loaded_count} plugin(s) for {adapter}: {', '.join(loaded_names)}")

    return loaded_count


def load_plugin_bundle(adapter: str, plugins_dir: Path) -> PluginBundle:
    """
    Load plugins for an adapter and return a resolved plugin bundle snapshot.

    This preserves the current registry-based loading behavior while exposing
    an explicit run-scoped bundle for callers that want to stop reading the
    global registry directly on the hot path.
    """
    if not plugins_dir.exists():
        logger.info(f"Plugins directory does not exist: {plugins_dir}")
        return build_plugin_bundle(adapter)

    if not plugins_dir.is_dir():
        logger.warning(f"Plugins path is not a directory: {plugins_dir}")
        return build_plugin_bundle(adapter)

    loaded_count, loaded_names = _import_plugin_modules(adapter, plugins_dir)

    if loaded_count > 0:
        logger.info(f"Loaded {loaded_count} plugin(s) for {adapter}: {', '.join(loaded_names)}")

    return build_plugin_bundle(adapter)
