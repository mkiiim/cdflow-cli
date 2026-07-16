"""
Plugin loader driven by an explicit per-adapter whitelist.

Loads plugin modules from an adapter directory according to an explicit
whitelist: either the ``enabled_names`` argument (host applications pass
this from their own settings) or a ``plugins.yaml`` file living alongside
the plugin files. Filenames carry no enabled/disabled meaning: a leading
underscore is a purely human convention for reference copies, and the
loader ignores it entirely.
"""

import importlib.util
import logging
from pathlib import Path
from typing import Optional
import sys

import yaml

from .registry import PluginBundle, build_plugin_bundle

logger = logging.getLogger(__name__)

PLUGIN_WHITELIST_FILENAME = "plugins.yaml"


def _read_whitelist(plugins_dir: Path) -> Optional[list[str]]:
    """
    Read enabled plugin stems from the whitelist file in a plugin directory.

    Returns:
        List of enabled stems, or None when the whitelist is absent or
        invalid. None means "load nothing" - there is deliberately no
        fallback to any filename convention.
    """
    whitelist_path = plugins_dir / PLUGIN_WHITELIST_FILENAME

    if not whitelist_path.is_file():
        logger.error(
            f"Plugin whitelist not found: {whitelist_path}. No plugins will be loaded. "
            f"Create {PLUGIN_WHITELIST_FILENAME} with an 'enabled' list of plugin file stems."
        )
        return None

    try:
        data = yaml.safe_load(whitelist_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        logger.error(
            f"Invalid plugin whitelist {whitelist_path}: {e}. No plugins will be loaded."
        )
        return None

    enabled = data.get("enabled") if isinstance(data, dict) else None
    if not isinstance(enabled, list) or not all(isinstance(name, str) for name in enabled):
        logger.error(
            f"Invalid plugin whitelist {whitelist_path}: expected a mapping with an "
            f"'enabled' list of plugin file stems. No plugins will be loaded."
        )
        return None

    return enabled


def _import_plugin_modules(
    adapter: str, plugins_dir: Path, enabled_names: list[str]
) -> tuple[int, list[str]]:
    """Import whitelisted plugin modules and return file-level load metadata."""
    loaded_count = 0
    loaded_names = []

    available_files = {f.stem: f for f in plugins_dir.glob("*.py")}

    for missing_name in sorted(set(enabled_names) - set(available_files)):
        logger.warning(
            f"Whitelisted plugin has no matching file in {plugins_dir}: {missing_name}"
        )

    plugin_files = sorted(
        plugin_file
        for stem, plugin_file in available_files.items()
        if stem in set(enabled_names)
    )

    for plugin_file in plugin_files:
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


def _resolve_and_import(
    adapter: str, plugins_dir: Path, enabled_names: Optional[list[str]]
) -> int:
    """Resolve the effective whitelist and import matching plugin modules."""
    if enabled_names is None:
        enabled_names = _read_whitelist(plugins_dir)
        if enabled_names is None:
            return 0

    loaded_count, loaded_names = _import_plugin_modules(adapter, plugins_dir, enabled_names)

    if loaded_count > 0:
        logger.info(f"Loaded {loaded_count} plugin(s) for {adapter}: {', '.join(loaded_names)}")

    return loaded_count


def load_plugins(
    adapter: str, plugins_dir: Path, enabled_names: Optional[list[str]] = None
) -> int:
    """
    Load whitelisted plugins from a directory.

    Imports the plugin files named by the effective whitelist, allowing
    plugins to self-register using the @register_plugin decorator. The
    whitelist names file stems as-is (no .py extension); a leading
    underscore in a filename has no loader meaning. Matching files load
    in alphabetical order regardless of whitelist order. Whitelisted
    names without a matching file log a warning and are skipped.

    Args:
        adapter: Adapter name (canadahelps, paypal)
        plugins_dir: Directory containing plugin files
        enabled_names: Explicit whitelist of plugin file stems. When None,
            the whitelist is read from plugins.yaml in plugins_dir; if that
            file is absent or invalid, no plugins load and an error is logged.

    Returns:
        Number of plugins loaded

    Example:
        plugins_path = Path("~/.config/caestudy/plugins/canadahelps").expanduser()
        count = load_plugins("canadahelps", plugins_path)
        logger.info(f"Loaded {count} plugins")
    """
    if not plugins_dir.exists():
        logger.info(f"Plugins directory does not exist: {plugins_dir}")
        return 0

    if not plugins_dir.is_dir():
        logger.warning(f"Plugins path is not a directory: {plugins_dir}")
        return 0

    return _resolve_and_import(adapter, plugins_dir, enabled_names)


def load_plugin_bundle(
    adapter: str, plugins_dir: Path, enabled_names: Optional[list[str]] = None
) -> PluginBundle:
    """
    Load whitelisted plugins for an adapter and return a resolved plugin
    bundle snapshot.

    Applies the same whitelist resolution as load_plugins (explicit
    enabled_names, else plugins.yaml in plugins_dir, else load nothing),
    while exposing an explicit run-scoped bundle for callers that want to
    stop reading the global registry directly on the hot path.
    """
    if not plugins_dir.exists():
        logger.info(f"Plugins directory does not exist: {plugins_dir}")
        return build_plugin_bundle(adapter)

    if not plugins_dir.is_dir():
        logger.warning(f"Plugins path is not a directory: {plugins_dir}")
        return build_plugin_bundle(adapter)

    _resolve_and_import(adapter, plugins_dir, enabled_names)

    return build_plugin_bundle(adapter)
