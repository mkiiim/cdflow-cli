#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""Shared bootstrap helpers for CLI command entrypoints."""

from pathlib import Path
from typing import Tuple

from ..utils.bootstrap import initialize_components_simplified
from ..utils.config_paths import resolve_config_path


STANDARD_LOG_LEVEL_CHOICES = ["DEBUG", "INFO", "WARNING", "NOTICE", "ERROR", "CRITICAL"]


def initialize_cli_components(
    config_path: str,
    log_level: str,
    *,
    require_existing_config: bool = False,
    os_log: bool = False,
) -> Tuple[object, None, str]:
    """
    Resolve config path and initialize shared CLI runtime components.

    Args:
        config_path: User-provided config path argument
        log_level: Requested console log level
        require_existing_config: Whether to fail fast if the resolved config file is missing
        os_log: Whether to also send records to macOS unified logging

    Returns:
        Tuple of (config, None, app_log_path)

    Raises:
        FileNotFoundError: If require_existing_config is True and the resolved config file is missing
    """
    resolved_config_path = resolve_config_path(config_path)

    if require_existing_config and not resolved_config_path.exists():
        raise FileNotFoundError(str(resolved_config_path))

    return initialize_components_simplified(
        config_path=str(resolved_config_path),
        console_log_level=log_level,
        os_log=os_log,
    )
