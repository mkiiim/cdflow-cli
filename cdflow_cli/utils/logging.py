# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Logging provider abstraction for managing log configuration and output.

This module provides an abstract interface for logging operations,
allowing the application to work with different logging backends
(file system, console, etc.) in a consistent way while avoiding
circular dependencies with the storage subsystem.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# Add custom NOTICE log level between WARNING(30) and ERROR(40)
NOTICE_LEVEL = 35
logging.addLevelName(NOTICE_LEVEL, "NOTICE")


def notice(self, message, *args, **kwargs):
    """Log at NOTICE level - important user-facing information"""
    if self.isEnabledFor(NOTICE_LEVEL):
        self._log(NOTICE_LEVEL, message, args, **kwargs)


# Add the method to Logger class
logging.Logger.notice = notice


class ImportLoggingContext:
    """
    Context manager for isolated import operation logging.

    Creates a completely separate logger hierarchy for import operations
    to avoid interfering with existing API loggers.
    """

    def __init__(self, logging_provider, import_log_filename: str):
        """
        Initialize the import logging context.

        Args:
            logging_provider: The logging provider instance
            import_log_filename: Filename for the import-specific log
        """
        self.logging_provider = logging_provider
        self.import_log_filename = import_log_filename
        self.import_handler = None
        self.import_root_logger = None
        self.redirected_loggers = {}  # Store original handlers for import-only loggers

    def __enter__(self):
        """
        Enter the import logging context.

        Creates a separate logger hierarchy for import operations and redirects
        only import-specific loggers to use the isolated handler.
        """
        # Create import-specific handler using paths system
        try:
            # Try to get paths system for direct path operations
            from .paths import get_paths, is_initialized

            if is_initialized():
                paths = get_paths()
                import_log_path = paths.logs / self.import_log_filename

                # Create import-specific handler using PathsFileHandler
                file_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                self.import_handler = PathsFileHandler(import_log_path)
                self.import_handler.setLevel(logging.DEBUG)
                self.import_handler.setFormatter(file_formatter)
            else:
                # Fallback to direct file operations in logs directory
                import os

                logs_dir = os.path.join(".", "storage_server", "logs")
                os.makedirs(logs_dir, exist_ok=True)
                import_log_path = os.path.join(logs_dir, self.import_log_filename)

                # Create import-specific handler using standard FileHandler
                file_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                self.import_handler = logging.FileHandler(import_log_path, mode="a")
                self.import_handler.setLevel(logging.DEBUG)
                self.import_handler.setFormatter(file_formatter)

            # Create a separate root logger for import operations
            self.import_root_logger = logging.getLogger("IMPORT_OPERATION")
            self.import_root_logger.setLevel(logging.DEBUG)
            self.import_root_logger.propagate = False  # Don't propagate to main loggers

            # Remove any existing handlers and add only our import handler
            for handler in self.import_root_logger.handlers[:]:
                self.import_root_logger.removeHandler(handler)
            self.import_root_logger.addHandler(self.import_handler)

            # List of loggers that should be redirected to import logs (import-only modules)
            import_only_loggers = [
                "cdflow_cli.models.donation",
                "cdflow_cli.adapters.canadahelps",
                "cdflow_cli.adapters.paypal",
            ]

            # Redirect only import-specific loggers to our import handler
            for logger_name in import_only_loggers:
                target_logger = logging.getLogger(logger_name)

                # Store original configuration
                self.redirected_loggers[logger_name] = {
                    "handlers": target_logger.handlers[:],
                    "propagate": target_logger.propagate,
                }

                # Redirect to import handler
                for handler in target_logger.handlers[:]:
                    target_logger.removeHandler(handler)
                target_logger.addHandler(self.import_handler)
                target_logger.propagate = False  # Don't propagate to avoid dual logging

            # Log start message
            self.import_root_logger.info(f"Import logging isolated to: {self.import_log_filename}")

        except Exception as e:
            root_logger = logging.getLogger()
            root_logger.error(f"Failed to create import logging context: {str(e)}")
            raise

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the import logging context.

        Cleans up the import-specific logger hierarchy and restores original handlers.
        """
        # Log completion message
        if self.import_root_logger:
            self.import_root_logger.info("Import logging context completed")

        # Restore original handlers for redirected loggers
        for logger_name, original_config in self.redirected_loggers.items():
            target_logger = logging.getLogger(logger_name)

            # Remove our import handler
            for handler in target_logger.handlers[:]:
                target_logger.removeHandler(handler)

            # Restore original handlers
            for handler in original_config["handlers"]:
                target_logger.addHandler(handler)

            # Restore original propagation setting
            target_logger.propagate = original_config["propagate"]

        # Clean up import logger
        if self.import_root_logger:
            for handler in self.import_root_logger.handlers[:]:
                self.import_root_logger.removeHandler(handler)

        # Close the import handler
        if self.import_handler:
            self.import_handler.close()

        # Log restoration message to main logger
        root_logger = logging.getLogger()
        root_logger.info("Import logging context restored, back to API logging")

    def get_logger(self, name: str):
        """
        Get a logger within the import context.

        Args:
            name: Logger name

        Returns:
            Logger configured for import operations
        """
        if self.import_root_logger:
            # Create child logger under the import root
            import_logger = logging.getLogger(f"IMPORT_OPERATION.{name}")
            import_logger.setLevel(logging.DEBUG)
            import_logger.propagate = True  # Propagate to import root logger
            return import_logger
        else:
            # Fallback to regular logger if import context not set up
            return logging.getLogger(name)


class LoggingProvider(ABC):
    """
    Abstract base class for logging providers.

    This class defines the interface that all logging providers must implement,
    providing a consistent way to configure and manage logging across the application.
    """

    @abstractmethod
    def configure_logging(
        self, log_filename: Optional[str] = None, log_level: str = "DEBUG", early_init: bool = False
    ) -> Optional[str]:
        """
        Configure logging for the application.

        Args:
            log_filename (str, optional): Name of the log file (if file logging is enabled)
            log_level (str): Logging level (DEBUG, INFO, etc.)
            early_init (bool): Whether this is an early initialization call

        Returns:
            str or None: Path to the created log file if early_init is True, None otherwise
        """
        pass

    @abstractmethod
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger with the specified name.

        Args:
            name (str): Logger name

        Returns:
            logging.Logger: Configured logger instance
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """
        Perform cleanup operations (close handlers, etc.)
        """
        pass

    @abstractmethod
    def initialize_bootstrap_logging(self) -> str:
        """
        Initialize bootstrap logging before configuration is available.

        Returns:
            str: Path to the bootstrap log file
        """
        pass

    @abstractmethod
    def transition_to_application_logging(self, bootstrap_log_path: str, app_log_path: str) -> str:
        """
        Transition from bootstrap to application logging, copying content.

        Args:
            bootstrap_log_path (str): Path to the bootstrap log file
            app_log_path (str): Path to the application log file

        Returns:
            str: Path to the application log file
        """
        pass

    @abstractmethod
    def create_operation_log(self, operation_name: str) -> str:
        """
        Create an operation-specific log while maintaining the application log.

        Args:
            operation_name (str): Name of the operation for the log file

        Returns:
            str: Path to the operation log file
        """
        pass

    @abstractmethod
    def get_current_log_filename(self) -> Optional[str]:
        """
        Get the filename (not path) of the current log file being written to.

        Returns:
            str or None: Filename of the current log file, or None if not available
        """
        pass


class UnifiedLoggingProvider(LoggingProvider):
    """
    Unified logging provider that handles both file and console logging.

    Supports flexible configuration with file_level and console_level settings.
    Use "NONE" to disable either file or console logging.
    """

    def __init__(
        self, file_level: str = "DEBUG", console_level: str = "INFO", base_path: str = "./logs"
    ):
        """
        Initialize the unified logging provider.

        Args:
            file_level (str): File logging level or "NONE" to disable file logging
            console_level (str): Console logging level or "NONE" to disable console logging
            base_path (str): Base path for log files
        """
        self.file_level = file_level.upper() if file_level else "NONE"
        self.console_level = console_level.upper() if console_level else "NONE"
        self.base_path = base_path

        self.log_file_path = None
        self.root_logger = logging.getLogger()
        self.loggers = {}

        # Initialize paths system for modern path handling
        self.paths = None
        try:
            from .paths import get_paths, is_initialized

            if is_initialized():
                self.paths = get_paths()
                # Use paths system for logs directory
                self.base_path = str(self.paths.logs)
                module_logger = logging.getLogger(__name__)
                module_logger.debug(f"Using paths system for logs: {self.base_path}")
        except (ImportError, RuntimeError):
            # Paths system not available, use provided base_path
            module_logger = logging.getLogger(__name__)
            module_logger.debug(f"Paths system not available, using base_path: {self.base_path}")

        # Only create log directory if file logging is enabled
        if self.file_level != "NONE":
            self._ensure_log_directory()

    def _ensure_log_directory(self) -> None:
        """Ensure the log directory exists using direct path operations."""
        try:
            os.makedirs(self.base_path, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create log directory: {str(e)}")

    def configure_logging(
        self, log_filename: Optional[str] = None, log_level: str = "DEBUG", early_init: bool = False
    ) -> Optional[str]:
        """
        Configure logging with optional console and file handlers based on levels.
        """

        # Set up formatters
        console_formatter = logging.Formatter("%(levelname)s - %(message)s")
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Configure root logger to most permissive level
        effective_level = logging.DEBUG
        if self.file_level != "NONE":
            effective_level = min(effective_level, getattr(logging, self.file_level, logging.DEBUG))
        if self.console_level != "NONE":
            # Handle custom NOTICE level
            console_level_value = (
                NOTICE_LEVEL
                if self.console_level == "NOTICE"
                else getattr(logging, self.console_level, logging.INFO)
            )
            effective_level = min(effective_level, console_level_value)

        self.root_logger.setLevel(effective_level)

        # Clear existing handlers
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)

        # Add console handler if enabled
        if self.console_level != "NONE":
            console_handler = logging.StreamHandler()
            # Handle custom NOTICE level
            if self.console_level == "NOTICE":
                console_handler.setLevel(NOTICE_LEVEL)
            else:
                console_handler.setLevel(getattr(logging, self.console_level, logging.INFO))
            console_handler.setFormatter(console_formatter)
            self.root_logger.addHandler(console_handler)

        # Add file handler if enabled and filename provided
        if self.file_level != "NONE" and log_filename:
            return self._add_file_handler(log_filename, file_formatter, early_init)

        return None

    def _add_file_handler(
        self, log_filename: str, file_formatter, early_init: bool
    ) -> Optional[str]:
        """Add file handler using paths system or storage provider."""
        # Try paths system first
        if self.paths:
            log_path = self.paths.logs / log_filename
            file_handler = PathsFileHandler(log_path)
            file_handler.setLevel(getattr(logging, self.file_level, logging.DEBUG))
            file_handler.setFormatter(file_formatter)
            self.root_logger.addHandler(file_handler)

            self.log_file_path = str(log_path)

            return str(log_path) if early_init else None

        # Use direct file operations
        log_path = os.path.join(self.base_path, os.path.basename(log_filename))
        os.makedirs(
            os.path.dirname(log_path) if os.path.dirname(log_path) else self.base_path,
            exist_ok=True,
        )

        file_handler = logging.FileHandler(log_path, mode="a")
        file_handler.setLevel(getattr(logging, self.file_level, logging.DEBUG))
        file_handler.setFormatter(file_formatter)
        self.root_logger.addHandler(file_handler)

        self.log_file_path = log_path

        return log_path if early_init else None

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger with the specified name."""
        if name not in self.loggers:
            self.loggers[name] = logging.getLogger(name)
        return self.loggers[name]

    def shutdown(self) -> None:
        """Perform cleanup operations."""
        for handler in self.root_logger.handlers[:]:
            handler.close()
            self.root_logger.removeHandler(handler)

    def initialize_bootstrap_logging(self) -> str:
        """Initialize bootstrap logging."""
        if self.file_level == "NONE":
            return ""

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bootstrap_log_filename = f"BOOTSTRAP_{timestamp}.log"
        self._ensure_log_directory()

        bootstrap_log_path = os.path.join(self.base_path, bootstrap_log_filename)

        # Configure with both console and file (if enabled)
        self.configure_logging(log_filename=bootstrap_log_filename, early_init=True)

        return bootstrap_log_path

    def transition_to_application_logging(self, bootstrap_log_path: str, app_log_path: str) -> str:
        """Transition from bootstrap to application logging."""
        if self.file_level == "NONE":
            return app_log_path

        # Read bootstrap content if it exists
        bootstrap_content = ""
        if os.path.exists(bootstrap_log_path):
            with open(bootstrap_log_path, "r", encoding="utf-8") as f:
                bootstrap_content = f.read()

        # Create transition content
        if bootstrap_content:
            transition_content = bootstrap_content + "\n\n" + "-" * 80 + "\n"
            transition_content += "TRANSITION FROM BOOTSTRAP TO APPLICATION LOGGING\n"
            transition_content += "-" * 80 + "\n\n"
        else:
            transition_content = ""

        # Write to application log using direct file operations
        try:
            with open(app_log_path, "w", encoding="utf-8") as f:
                f.write(transition_content)
        except Exception as e:
            print(f"Error writing transition log: {e}")

        # Reconfigure logging
        self.shutdown()
        app_log_filename = os.path.basename(app_log_path)
        self.configure_logging(log_filename=app_log_filename)

        return app_log_path

    def create_operation_log(self, operation_name: str, prefix: str = "OP") -> str:
        """Create operation-specific log using paths system or direct operations."""
        if self.file_level == "NONE":
            return ""

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        operation_log_filename = f"{prefix}_{timestamp}_{operation_name}.log"

        try:
            # Use paths system if available
            if self.paths:
                operation_log_path = self.paths.logs / operation_log_filename
                operation_log_path.write_text("--- OPERATION LOG START ---\n", encoding="utf-8")

                # Add operation handler using PathsFileHandler
                file_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                operation_handler = PathsFileHandler(operation_log_path)
                operation_handler.setLevel(getattr(logging, self.file_level, logging.DEBUG))
                operation_handler.setFormatter(file_formatter)
                self.root_logger.addHandler(operation_handler)

                return str(operation_log_path)
            else:
                # Use direct file operations
                operation_log_path = os.path.join(self.base_path, operation_log_filename)
                with open(operation_log_path, "w", encoding="utf-8") as f:
                    f.write("--- OPERATION LOG START ---\n")

                # Add operation handler using standard FileHandler
                file_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                operation_handler = logging.FileHandler(operation_log_path, mode="a")
                operation_handler.setLevel(getattr(logging, self.file_level, logging.DEBUG))
                operation_handler.setFormatter(file_formatter)
                self.root_logger.addHandler(operation_handler)

                return operation_log_path
        except Exception as e:
            print(f"Error creating operation log: {e}")
            return ""

    def get_current_log_filename(self) -> Optional[str]:
        """Get current log filename."""
        if self.log_file_path:
            from pathlib import Path

            return Path(self.log_file_path).name
        return None


class FileLoggingProvider(LoggingProvider):
    """
    Logging provider implementation using file-based logging.
    """

    def __init__(self, base_path: str = "./logs", console_level: str = "INFO"):
        """
        Initialize the file logging provider.

        Args:
            base_path (str): Base path for log files
            console_level (str): Logging level for console output
        """
        self.base_path = base_path

        self.console_level = console_level
        self.current_log_file = None
        self.log_file_path = None
        self.root_logger = logging.getLogger()

        # Initialize paths system for modern path handling
        self.paths = None
        try:
            from .paths import get_paths, is_initialized

            if is_initialized():
                self.paths = get_paths()
                # Use paths system for logs directory
                self.base_path = str(self.paths.logs)
                module_logger = logging.getLogger(__name__)
                module_logger.debug(f"Using paths system for logs: {self.base_path}")
        except (ImportError, RuntimeError):
            # Paths system not available, use provided base_path
            module_logger = logging.getLogger(__name__)
            module_logger.debug(f"Paths system not available, using base_path: {self.base_path}")

        self._ensure_log_directory()

    def _ensure_log_directory(self) -> None:
        """
        Ensure the log directory exists using direct path operations.
        """
        try:
            os.makedirs(self.base_path, exist_ok=True)
        except Exception as e:
            print(f"Warning: Could not create log directory: {str(e)}")

    def configure_logging(
        self, log_filename: Optional[str] = None, log_level: str = "DEBUG", early_init: bool = False
    ) -> Optional[str]:
        """
        Configure logging with both console and file handlers.

        Args:
            log_filename (str, optional): Name of the log file
            log_level (str): Logging level (DEBUG, INFO, etc.)
            early_init (bool): Whether this is an early initialization call

        Returns:
            str or None: Path to the created log file if early_init is True, None otherwise
        """


        # Set up formatters
        console_formatter = logging.Formatter("%(levelname)s - %(message)s")
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Configure root logger
        self.root_logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))

        # Clear existing handlers to avoid duplicates
        for handler in self.root_logger.handlers[:]:
            pass  # Remove handler without debug output
            self.root_logger.removeHandler(handler)

        # Console handler
        console_handler = logging.StreamHandler()
        # Handle custom NOTICE level
        console_level_value = (
            NOTICE_LEVEL
            if self.console_level.upper() == "NOTICE"
            else getattr(logging, self.console_level.upper(), logging.INFO)
        )
        console_handler.setLevel(console_level_value)
        console_handler.setFormatter(console_formatter)
        self.root_logger.addHandler(console_handler)

        # For early initialization, create a timestamp-based log file if none is provided
        if early_init and not log_filename:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            log_filename = f"IMPORTDONATIONS_{timestamp}_early_init.log"
            self.root_logger.debug(f"Setting up early initialization logging to {log_filename}")

        # Add file handler if a filename is specified
        if log_filename:
            # Use paths system for file operations (storage provider eliminated)
            try:
                if self.paths:
                    log_path = self.paths.logs / log_filename

                    # Create and add the paths file handler
                    file_handler = PathsFileHandler(log_path)
                    file_handler.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
                    file_handler.setFormatter(file_formatter)
                    self.root_logger.addHandler(file_handler)

                    self.log_file_path = str(log_path)
                    self.root_logger.info(f"Logging to paths system: {log_path}")
                    return str(log_path)
                else:
                    # Use direct file operations
                    log_path = os.path.join(self.base_path, os.path.basename(log_filename))

                    # Create directory if needed
                    log_dir = os.path.dirname(log_path)
                    if log_dir and not os.path.exists(log_dir):
                        os.makedirs(log_dir, exist_ok=True)

                    file_handler = logging.FileHandler(log_path, mode="a")
                    file_handler.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
                    file_handler.setFormatter(file_formatter)
                    self.root_logger.addHandler(file_handler)

                    self.log_file_path = log_path
                    self.root_logger.info(f"Logging to: {log_path}")
                    return log_path

            except Exception as e:
                # Log error through existing console handler instead of print
                return None

        # Set up specific loggers for packages we want to monitor
        for logger_name in [
            "",  # Root logger
            "cdflow_cli",  # Main package
            "cdflow_cli.nboauth",  # OAuth module (old path)
            "cdflow_cli.adapters.nationbuilder.oauth",  # OAuth module (new path)
            "urllib3",  # HTTP client
            "urllib3.connectionpool",  # Connection pool
            "nbimportdonations",  # Main app
            "__main__",  # Main script
        ]:
            module_logger = logging.getLogger(logger_name)
            module_logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
            # Avoid propagation issues with urllib3
            if "urllib3" in logger_name:
                module_logger.propagate = True

        return None

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger with the specified name.

        Args:
            name (str): Logger name

        Returns:
            logging.Logger: Configured logger instance
        """
        return logging.getLogger(name)

    def shutdown(self) -> None:
        """
        Perform cleanup operations (close handlers, etc.)
        """
        for handler in self.root_logger.handlers[:]:
            handler.close()
            self.root_logger.removeHandler(handler)

    def initialize_bootstrap_logging(self) -> str:
        """
        Initialize bootstrap logging before configuration is available.

        Returns:
            str: Path to the bootstrap log file
        """
        # Generate a timestamp for the log file name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bootstrap_log_filename = f"BOOTSTRAP_{timestamp}.log"

        # Create the bootstrap log directory if it doesn't exist
        self._ensure_log_directory()

        # Create the full path
        bootstrap_log_path = (
            os.path.join(self.base_path, bootstrap_log_filename)
            if self.base_path
            else bootstrap_log_filename
        )

        # Set up formatters
        console_formatter = logging.Formatter("%(levelname)s - %(message)s")
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # Configure root logger
        self.root_logger.setLevel(logging.DEBUG)

        # Clear existing handlers to avoid duplicates
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)

        # Console handler
        console_handler = logging.StreamHandler()
        # Handle custom NOTICE level
        console_level_value = (
            NOTICE_LEVEL
            if self.console_level.upper() == "NOTICE"
            else getattr(logging, self.console_level.upper(), logging.INFO)
        )
        console_handler.setLevel(console_level_value)
        console_handler.setFormatter(console_formatter)
        self.root_logger.addHandler(console_handler)

        # File handler
        try:
            # Create bootstrap log file
            file_handler = logging.FileHandler(bootstrap_log_path, mode="a")
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(file_formatter)
            self.root_logger.addHandler(file_handler)

            self.log_file_path = bootstrap_log_path
            self.root_logger.info(f"Bootstrap logging initialized: {bootstrap_log_path}")

        except Exception as e:
            self.root_logger.error(f"Error setting up bootstrap logging: {str(e)}")
            self.root_logger.error("Continuing with console logging only")

        # Set up specific loggers for packages we want to monitor
        for logger_name in [
            "",  # Root logger
            "cdflow_cli",  # Main package
            "cdflow_cli.nboauth",  # OAuth module (old path)
            "cdflow_cli.adapters.nationbuilder.oauth",  # OAuth module (new path)
            "urllib3",  # HTTP client
            "urllib3.connectionpool",  # Connection pool
            "nbimportdonations",  # Main app
            "__main__",  # Main script
        ]:
            module_logger = logging.getLogger(logger_name)
            module_logger.setLevel(logging.DEBUG)
            # Avoid propagation issues with urllib3
            if "urllib3" in logger_name:
                module_logger.propagate = True

        return bootstrap_log_path

    def transition_to_application_logging(self, bootstrap_log_path: str, app_log_path: str) -> str:
        """
        Transition from bootstrap to application logging, copying content.

        This method handles the transition from the initial bootstrap logging to the
        fully configured application logging. It reads the bootstrap log content,
        adds a transition marker, and writes it to the application log using the
        configured storage provider if available. This is a critical step in the
        bootstrap process where we switch from direct file operations to using the
        storage provider architecture.

        Args:
            bootstrap_log_path (str): Path to the bootstrap log file
            app_log_path (str): Path to the application log file

        Returns:
            str: Path to the application log file, or the original path if creation failed
        """
        # Use self.root_logger instead of module-level logger
        self.root_logger.debug(
            f"Transitioning from bootstrap log ({bootstrap_log_path}) to application log ({app_log_path})"
        )

        # 1. Read bootstrap content (using direct file ops is acceptable since it's still bootstrap)
        bootstrap_content = ""
        if os.path.exists(bootstrap_log_path):
            with open(bootstrap_log_path, "r", encoding="utf-8") as bootstrap_file:
                bootstrap_content = bootstrap_file.read()

        # Create transition marker
        transition_content = bootstrap_content
        if bootstrap_content:
            transition_content += "\n\n" + "-" * 80 + "\n"
            transition_content += "TRANSITION FROM BOOTSTRAP TO APPLICATION LOGGING\n"
            transition_content += "-" * 80 + "\n\n"

        # 2. Write transition content to application log using direct file operations
        app_log_filename = os.path.basename(app_log_path)
        full_app_log_path = app_log_path

        try:
            with open(app_log_path, "w", encoding="utf-8") as app_file:
                app_file.write(transition_content)
            self.root_logger.debug(
                f"Wrote transition log using direct file operations: {app_log_path}"
            )
        except Exception as e:
            self.root_logger.error(f"Error writing transition log: {str(e)}")
            self.root_logger.warning(
                "Continuing without application log file due to file operation error"
            )
            full_app_log_path = None

        # 4. Close existing log handlers
        self.shutdown()

        # 5. Reconfigure logging to use the application log
        if full_app_log_path:
            self.configure_logging(log_filename=app_log_filename, log_level="DEBUG")
            self.root_logger.info(
                f"Successfully transitioned to application logging: {full_app_log_path}"
            )
        else:
            # Configure with just console logging
            self.configure_logging(log_level="DEBUG")
            self.root_logger.warning("Transitioned to console-only logging due to previous errors")

        return (
            full_app_log_path or app_log_path
        )  # Return the original path if full_app_log_path is None

    def create_operation_log(self, operation_name: str, prefix: str = "OP") -> str:
        """
        Create an operation-specific log while maintaining the application log.

        This method creates a separate log file for a specific operation, allowing
        detailed logging of that operation while still maintaining the main application
        log. The operation log is created using the configured storage provider to ensure
        all file operations go through the storage abstraction layer rather than directly
        accessing the file system.

        Args:
            operation_name (str): Name of the operation for the log file
            prefix (str): Prefix for the log file name (default: "OP")

        Returns:
            str: Path to the operation log file, or None if creation failed
        """
        # Generate a timestamp for the log file name
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        operation_log_filename = f"{prefix}_{timestamp}_{operation_name}.log"

        self.root_logger.debug(f"Creating operation log: {operation_log_filename}")

        # We want to maintain the current application logging while also
        # logging to an operation-specific file

        # Create operation log using paths system or direct operations
        try:
            # Use paths system if available
            if self.paths:
                operation_log_path = self.paths.logs / operation_log_filename
                operation_log_path.write_text("--- OPERATION LOG START ---\n", encoding="utf-8")

                # Add operation handler using PathsFileHandler
                file_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                operation_handler = PathsFileHandler(operation_log_path)
                operation_handler.setLevel(logging.DEBUG)
                operation_handler.setFormatter(file_formatter)
                self.root_logger.addHandler(operation_handler)

                self.root_logger.info(f"Operation logging initialized: {operation_log_filename}")
                return str(operation_log_path)
            else:
                # Use direct file operations
                operation_log_path = os.path.join(self.base_path, operation_log_filename)
                with open(operation_log_path, "w", encoding="utf-8") as f:
                    f.write("--- OPERATION LOG START ---\n")

                # Add operation handler using standard FileHandler
                file_formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                operation_handler = logging.FileHandler(operation_log_path, mode="a")
                operation_handler.setLevel(logging.DEBUG)
                operation_handler.setFormatter(file_formatter)
                self.root_logger.addHandler(operation_handler)

                self.root_logger.info(f"Operation logging initialized: {operation_log_filename}")
                return operation_log_path
        except Exception as e:
            self.root_logger.error(f"Error creating operation log: {str(e)}")
            self.root_logger.warning("Continuing with application logging only")
            return None

    def get_current_log_filename(self) -> Optional[str]:
        """
        Get the filename (not path) of the current log file being written to.

        Returns:
            str or None: Filename of the current log file, or None if not available
        """
        if self.log_file_path:
            from pathlib import Path

            return Path(self.log_file_path).name
        return None


class ConsoleLoggingProvider(LoggingProvider):
    """
    Logging provider implementation using console-only logging.
    """

    def __init__(self, console_level: str = "INFO"):
        """
        Initialize the console logging provider.

        Args:
            console_level (str): Logging level for console output
        """
        self.console_level = console_level
        self.root_logger = logging.getLogger()
        self.current_log_file = None

    def configure_logging(
        self, log_filename: Optional[str] = None, log_level: str = "DEBUG", early_init: bool = False
    ) -> None:
        """
        Configure logging with console handler only.

        Args:
            log_filename (str, optional): Ignored in console-only mode
            log_level (str): Logging level (DEBUG, INFO, etc.)
            early_init (bool): Whether this is an early initialization call

        Returns:
            None
        """
        # Set up formatter
        console_formatter = logging.Formatter("%(levelname)s - %(message)s")

        # Configure root logger
        self.root_logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))

        # Clear existing handlers to avoid duplicates
        for handler in self.root_logger.handlers[:]:
            self.root_logger.removeHandler(handler)

        # Console handler
        console_handler = logging.StreamHandler()
        # Handle custom NOTICE level
        console_level_value = (
            NOTICE_LEVEL
            if self.console_level.upper() == "NOTICE"
            else getattr(logging, self.console_level.upper(), logging.INFO)
        )
        console_handler.setLevel(console_level_value)
        console_handler.setFormatter(console_formatter)
        self.root_logger.addHandler(console_handler)

        # Set up specific loggers for packages we want to monitor
        for logger_name in [
            "",  # Root logger
            "cdflow_cli",  # Main package
            "cdflow_cli.nboauth",  # OAuth module (old path)
            "cdflow_cli.adapters.nationbuilder.oauth",  # OAuth module (new path)
            "urllib3",  # HTTP client
            "urllib3.connectionpool",  # Connection pool
            "nbimportdonations",  # Main app
            "__main__",  # Main script
        ]:
            module_logger = logging.getLogger(logger_name)
            module_logger.setLevel(getattr(logging, log_level.upper(), logging.DEBUG))
            # Avoid propagation issues with urllib3
            if "urllib3" in logger_name:
                module_logger.propagate = True

        return None

    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger with the specified name.

        Args:
            name (str): Logger name

        Returns:
            logging.Logger: Configured logger instance
        """
        return logging.getLogger(name)

    def shutdown(self) -> None:
        """
        Perform cleanup operations (close handlers, etc.)
        """
        for handler in self.root_logger.handlers[:]:
            handler.close()
            self.root_logger.removeHandler(handler)

    def initialize_bootstrap_logging(self) -> str:
        """
        Console logging doesn't need bootstrap - return empty string.
        """
        return ""

    def transition_to_application_logging(self, bootstrap_log_path: str, app_log_path: str) -> str:
        """
        Console logging doesn't transition - return the app log path.
        """
        return app_log_path

    def create_operation_log(self, operation_name: str) -> str:
        """
        Console logging doesn't create separate operation logs - return empty string.
        """
        return ""

    def get_current_log_filename(self) -> Optional[str]:
        """
        Console logging doesn't have a log file - return None.
        """
        return None


class PathsFileHandler(logging.Handler):
    """
    A modern logging handler that writes log messages directly to filesystem paths.

    Provides optimal performance and reliability by using direct Path operations
    with built-in safety features and directory creation.
    """

    def __init__(self, log_path: Path, mode="a"):
        """
        Initialize the paths file handler.

        Args:
            log_path: Path object for the log file location
            mode: File open mode (default 'a' for append)
        """
        super().__init__()
        self.log_path = log_path
        self.mode = mode
        # Flag to prevent recursive logging
        self.is_handling = False

        # Ensure parent directory exists
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, record):
        """Emit a log record by writing to the file path."""
        # Skip logging from storage module to prevent infinite loops
        if "cdflow_cli.utils.storage" in record.name:
            return

        # Skip logging from log extraction module to prevent recursive issues
        if "cdflow_cli.utils.log_extraction" in record.name:
            return

        # Prevent recursive emission
        if self.is_handling:
            return

        try:
            self.is_handling = True
            msg = self.format(record)

            # Use direct Path operations
            # Ensure parent directory exists
            self.log_path.parent.mkdir(parents=True, exist_ok=True)

            if self.log_path.exists():
                # Append to existing file
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(msg + "\n")
            else:
                # Create new file
                self.log_path.write_text(msg + "\n", encoding="utf-8")

        except Exception:
            self.handleError(record)
        finally:
            self.is_handling = False


def get_logging_provider(config: Dict[str, Any]) -> LoggingProvider:
    """
    Factory function to create a logging provider based on configuration.

    Args:
        config (Dict[str, Any]): Logging configuration with file_level and console_level

    Returns:
        LoggingProvider: Configured logging provider instance
    """
    import warnings

    # Extract file and console levels from new structure
    file_level = config.get("file_level")
    console_level = config.get("console_level")

    # Handle nested logging config (modern format with 'logging' wrapper)
    if file_level is None or console_level is None:
        if "logging" in config and isinstance(config["logging"], dict):
            logging_section = config["logging"]
            file_level = logging_section.get("file_level", file_level)
            console_level = logging_section.get("console_level", console_level)

    # Handle legacy format with deprecation warning
    if file_level is None or console_level is None:
        if "provider" in config and "settings" in config:
            warnings.warn(
                "DEPRECATED: Legacy logging config format detected. "
                "Please update your config to use 'file_level' and 'console_level' instead of 'provider' and 'settings'. "
                "Legacy support will be removed in a future version.",
                DeprecationWarning,
                stacklevel=2,
            )
            print(
                "WARNING: Legacy logging configuration detected - please update your config file!"
            )
            print("  Old format: logging.provider + logging.settings")
            print("  New format: logging.file_level + logging.console_level")

            # Extract from legacy format
            settings = config["settings"]
            if config.get("provider") == "console":
                file_level = "NONE"
                console_level = settings.get("console_level", "INFO")
            else:
                file_level = settings.get("level", "DEBUG")
                console_level = settings.get("console_level", "INFO")
        else:
            # No valid config found, use defaults
            file_level = "DEBUG"
            console_level = "INFO"

    # Return appropriate provider based on configuration
    if file_level == "NONE" and console_level != "NONE":
        return ConsoleLoggingProvider(console_level=console_level)
    elif file_level != "NONE" and console_level == "NONE":
        return FileLoggingProvider(base_path="./logs")
    else:
        return UnifiedLoggingProvider(file_level=file_level, console_level=console_level)
