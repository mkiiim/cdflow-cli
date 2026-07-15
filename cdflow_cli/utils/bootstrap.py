# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import logging
import os
import sys
from typing import Optional, Tuple
from pathlib import Path

from .config import ConfigProvider
from .logging import configure_logging, get_current_log_file
from .paths import initialize_paths


def initialize_components_simplified(
    config_path: Optional[str] = None,
    console_log_level: Optional[str] = "INFO",
    os_log: bool = False,
) -> Tuple[ConfigProvider, None, str]:
    """
    Initialize configuration, paths, and CLI-mode logging in one step.

    Loads configuration, initializes the paths system to locate the logs
    directory, then configures structlog-based CLI logging with a single
    rotating log file (no bootstrap phase, no per-session log files).

    Returns:
        Tuple of (config, None, app_log_path). The second element is kept
        for backwards compatibility with callers that unpack a logging
        provider; providers were removed in favour of configure_logging().
    """

    # Step 1: Load configuration first
    default_config = os.environ.get("CONFIG_PATH", "config/config_app.yaml")
    config = ConfigProvider(config_path or default_config)

    # Step 2: Initialize paths system to get logs directory immediately
    paths = None
    try:
        paths = initialize_paths(config)
        logs_directory = paths.logs

        # Ensure logs directory exists
        logs_directory.mkdir(parents=True, exist_ok=True)

    except Exception as e:
        # Fallback to local logs directory if paths system fails
        entrypoint_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        logs_directory = Path(os.path.join(entrypoint_dir, "logs"))
        logs_directory.mkdir(parents=True, exist_ok=True)

        # Basic logging to show the fallback
        print(f"WARNING: Paths system failed ({e}), using default logs directory: {logs_directory}")

    # Step 3: Resolve file logging settings from configuration
    logging_config = config.get_logging_config() or {}
    if isinstance(logging_config.get("logging"), dict):
        logging_config = logging_config["logging"]
    file_level = str(logging_config.get("file_level", "DEBUG"))
    log_file_enabled = file_level.upper() != "NONE"

    # Step 4: Configure logging once for the whole process
    configure_logging(
        mode="cli",
        level=console_log_level or "INFO",
        log_file=log_file_enabled,
        log_file_path=logs_directory / "cdflow.log",
        file_level=file_level if log_file_enabled else "DEBUG",
        os_log=os_log or bool(logging_config.get("os_log", False)),
    )

    app_log_path = str(get_current_log_file() or "")

    logger = logging.getLogger(__name__)
    logger.info(f"Bootstrap completed - logging to: {app_log_path or 'console only'}")
    logger.debug(f"Paths system available: {paths is not None}")

    return config, None, app_log_path
