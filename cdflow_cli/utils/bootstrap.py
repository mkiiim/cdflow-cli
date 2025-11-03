# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import datetime
import os
import sys
from typing import Optional, Tuple
from pathlib import Path

from .config import ConfigProvider
from .logging import get_logging_provider
from .paths import initialize_paths


def initialize_components_simplified(
    config_path: Optional[str] = None, console_log_level: Optional[str] = "INFO"
) -> Tuple[ConfigProvider, object, object, str]:
    """
    Simplified initialization that eliminates bootstrap logging by using paths system directly.

    This approach:
    1. Loads configuration immediately
    2. Initializes paths system to get logs directory
    3. Starts logging directly to correct location (no bootstrap phase)
    4. Uses direct file operations for reliable logging

    Returns:
        Tuple of (config, logging_provider, app_log_path)
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

    # Step 3: Start logging directly to the correct location
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    app_log_filename = f"APP_{timestamp}.log"
    app_log_path = logs_directory / app_log_filename

    # Step 4: Initialize logging provider directly with paths (no storage provider needed)
    # Override logging config to use console level from CLI argument
    logging_config = config.get_logging_config()
    if logging_config:
        # Handle modern format (nested under 'logging' key)
        if "logging" in logging_config and "console_level" in logging_config["logging"]:
            logging_config["logging"]["console_level"] = console_log_level
        # Handle direct format (file_level/console_level at root)
        elif "console_level" in logging_config:
            logging_config["console_level"] = console_log_level
        # Handle legacy format (settings.console_level)
        elif "settings" in logging_config:
            logging_config["settings"]["console_level"] = console_log_level

    logging_provider = get_logging_provider(logging_config)  # No storage provider needed

    # Configure logging to use the paths-based log file directly
    # Get log level from new logging config structure
    logging_config = config.get_logging_config()
    file_level = logging_config.get("file_level", "DEBUG") if logging_config else "DEBUG"

    logging_provider.configure_logging(
        log_filename=app_log_filename, log_level=file_level, early_init=True
    )

    # Log successful initialization
    logger = logging_provider.get_logger(__name__)
    logger.info(f"Simplified bootstrap completed - direct logging to: {app_log_path}")
    logger.debug(f"Paths system available: {paths is not None}")

    return config, logging_provider, str(app_log_path)
