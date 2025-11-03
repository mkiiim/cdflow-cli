# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Smart configuration path resolution utilities.

Implements XDG Base Directory Specification for config file locations.
"""

import os
from pathlib import Path
from typing import Union


def get_default_config_dir() -> Path:
    """
    Get the default configuration directory following XDG Base Directory spec.

    Returns:
        Path: ~/.config/cdflow on Unix, %APPDATA%/cdflow on Windows
    """
    if os.name == "nt":  # Windows
        config_home = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
        return Path(config_home) / "cdflow"
    else:  # Unix-like (Linux, macOS)
        config_home = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")
        return Path(config_home) / "cdflow"


def resolve_config_path(config_path: Union[str, Path]) -> Path:
    """
    Smart config path resolution:
    - Bare filenames resolve to ~/.config/cdflow/
    - Paths with separators (/ or \) are used as-is

    Args:
        config_path: Config file path or filename

    Returns:
        Path: Resolved absolute path

    Examples:
        resolve_config_path("config.yaml") -> ~/.config/cdflow/config.yaml
        resolve_config_path("./config.yaml") -> ./config.yaml (as absolute)
        resolve_config_path("/etc/cdflow/config.yaml") -> /etc/cdflow/config.yaml
    """
    config_path = Path(config_path).expanduser()

    # If it's already absolute, use as-is
    if config_path.is_absolute():
        return config_path

    # Check if path contains separators (indicating explicit relative path)
    path_str = str(config_path)
    if "/" in path_str or (os.name == "nt" and "\\" in path_str):
        # Has explicit path separators, resolve relative to current directory
        return config_path.resolve()

    # Bare filename - resolve to default config directory
    default_dir = get_default_config_dir()
    return default_dir / config_path


def ensure_config_dir_exists(config_path: Path) -> None:
    """
    Ensure the parent directory of a config file exists.

    Args:
        config_path: Path to config file
    """
    config_path.parent.mkdir(parents=True, exist_ok=True)
