# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Simple path management for file operations.
Replaces the complex storage provider system with direct Path operations.
Works alongside existing storage provider during transition.
"""

from pathlib import Path
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class StoragePaths:
    """
    Simple path manager for different file types.

    Provides direct access to Path objects for file operations,
    replacing the complex storage provider abstraction.
    """

    def __init__(self, config_provider):
        """
        Initialize paths from configuration.

        Args:
            config_provider: ConfigProvider instance with storage settings
        """
        self.config_provider = config_provider
        self._paths = {}
        self._initialize_paths()

    def _initialize_paths(self):
        """Initialize all paths from configuration."""
        try:
            storage_config = self.config_provider.get_storage_config()
            logger.debug(f"Initializing storage paths from config: {list(storage_config.keys())}")

            # Use simple paths format only
            if "paths" in storage_config:
                self._initialize_from_simple_paths(storage_config)
            else:
                self._initialize_default_paths(storage_config)

            # Ensure all required directories exist
            self._create_directories()

            logger.debug(f"Storage paths initialized: {list(self._paths.keys())}")

        except Exception as e:
            logger.error(f"Failed to initialize storage paths: {e}")
            # Use safe defaults as fallback
            self._initialize_default_paths({})

    def _initialize_from_simple_paths(self, storage_config: Dict[str, str]):
        """Initialize from new simple paths configuration format."""
        logger.debug("Using new simple paths configuration format")

        # Get base path if provided
        base_path_str = storage_config.get("base_path")
        base_path = None
        if base_path_str:
            base_path = Path(base_path_str).expanduser()
            logger.debug(f"Using base path: {base_path}")

        # Get the paths section
        paths_config = storage_config.get("paths", {})

        # Map each file type to its path
        file_type_mappings = {
            "jobs": "jobs",
            "logs": "logs",
            "output": "output",
            "cli_source": "cli_source",
            "app_upload": "app_upload",
            "app_processing": "app_processing",
        }

        for file_type, config_key in file_type_mappings.items():
            path_str = paths_config.get(config_key)

            if path_str:
                # Use provided path - resolve against base_path if relative
                path_obj = Path(path_str)
                if base_path and not path_obj.is_absolute():
                    # Relative path: resolve against base_path
                    self._paths[file_type] = base_path / path_obj
                    logger.debug(
                        f"Resolved relative path {path_str} against base_path: {self._paths[file_type]}"
                    )
                else:
                    # Absolute path or no base_path: use as-is
                    self._paths[file_type] = path_obj
                    logger.debug(f"Using path as-is: {self._paths[file_type]}")
            elif base_path:
                # No specific path provided: use base_path + file_type
                self._paths[file_type] = base_path / file_type
                logger.debug(f"Using base_path + file_type: {self._paths[file_type]}")
            else:
                # No path provided and no base_path: use default
                self._paths[file_type] = Path("/tmp/nbimport") / file_type
                logger.debug(f"Using default path: {self._paths[file_type]}")

            logger.debug(f"Final mapping {file_type} -> {self._paths[file_type]}")

    def _initialize_default_paths(self, storage_config: Dict[str, Any]):
        """Initialize with safe default paths."""
        logger.warning("Using default storage paths configuration")

        # Try to get base path from provider defaults
        provider_defaults = storage_config.get("provider_defaults", {})
        base_path = Path(provider_defaults.get("base_path", "/tmp/nbimport"))

        # Set default paths for all file types
        file_types = [
            "jobs",
            "logs",
            "output",
            "cli_source",
            "app_upload",
            "app_processing",
            "tokens",
            "assets",
        ]
        for file_type in file_types:
            self._paths[file_type] = base_path / file_type
            logger.debug(f"Default mapping {file_type} -> {self._paths[file_type]}")

    def _create_directories(self):
        """Ensure all configured directories exist."""
        for file_type, path in self._paths.items():
            try:
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Ensured directory exists: {path}")
            except Exception as e:
                logger.error(f"Failed to create directory {path} for {file_type}: {e}")

    # Property access for each file type
    @property
    def jobs(self) -> Path:
        """Job files directory."""
        return self._paths["jobs"]

    @property
    def logs(self) -> Path:
        """Log files directory."""
        return self._paths["logs"]

    @property
    def output(self) -> Path:
        """Output files directory (success/fail CSVs)."""
        return self._paths["output"]

    @property
    def cli_source(self) -> Path:
        """CLI source files directory."""
        return self._paths["cli_source"]

    @property
    def app_upload(self) -> Path:
        """API upload files directory."""
        return self._paths["app_upload"]

    @property
    def app_processing(self) -> Path:
        """API processing files directory."""
        return self._paths["app_processing"]


    def get_path(self, file_type: str) -> Path:
        """
        Get path for any file type.

        Args:
            file_type: File type identifier

        Returns:
            Path: The path for the file type

        Raises:
            ValueError: If the file type is not configured
        """
        if file_type not in self._paths:
            raise ValueError(
                f"Unknown file type: {file_type}. Available: {list(self._paths.keys())}"
            )
        return self._paths[file_type]

    def get_all_paths(self) -> Dict[str, Path]:
        """Get all configured paths."""
        return self._paths.copy()

    def __str__(self) -> str:
        """String representation for debugging."""
        paths_str = ", ".join(f"{ft}={path}" for ft, path in self._paths.items())
        return f"StoragePaths({paths_str})"


# Global instance - initialized by bootstrap
_PATHS: Optional[StoragePaths] = None


def initialize_paths(config_provider) -> StoragePaths:
    """
    Initialize global paths instance.

    Args:
        config_provider: ConfigProvider instance

    Returns:
        StoragePaths: The initialized paths instance
    """
    global _PATHS
    try:
        _PATHS = StoragePaths(config_provider)
        logger.debug("Storage paths system initialized successfully")
        return _PATHS
    except Exception as e:
        logger.error(f"Failed to initialize storage paths: {e}")
        raise


def get_paths() -> StoragePaths:
    """
    Get the global paths instance.

    Returns:
        StoragePaths: The global paths instance

    Raises:
        RuntimeError: If paths not initialized
    """
    if _PATHS is None:
        raise RuntimeError(
            "Storage paths not initialized. Call initialize_paths(config_provider) first."
        )
    return _PATHS


def is_initialized() -> bool:
    """Check if paths system is initialized."""
    return _PATHS is not None


# Convenience functions for common operations
def ensure_file_parent_exists(file_path: Path) -> None:
    """Ensure the parent directory of a file exists."""
    file_path.parent.mkdir(parents=True, exist_ok=True)


def safe_read_text(file_path: Path, encoding: str = "utf-8", default: str = "") -> str:
    """
    Safely read text from a file with fallback.

    Args:
        file_path: Path to the file
        encoding: Text encoding
        default: Default value if file doesn't exist or can't be read

    Returns:
        str: File content or default value
    """
    try:
        return file_path.read_text(encoding=encoding)
    except FileNotFoundError:
        logger.debug(f"File not found: {file_path}")
        return default
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return default


def safe_write_text(file_path: Path, content: str, encoding: str = "utf-8") -> bool:
    """
    Safely write text to a file.

    Args:
        file_path: Path to the file
        content: Content to write
        encoding: Text encoding

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        ensure_file_parent_exists(file_path)
        file_path.write_text(content, encoding=encoding)
        logger.debug(f"Successfully wrote file: {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error writing file {file_path}: {e}")
        return False
