# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Logo deployment utility that copies correct logos to static locations.

This module implements a cleaner architecture where the logo system proactively
copies the appropriate logos (custom or placeholder) to predictable static
locations that the code can always reference.
"""

import shutil
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class LogoDeployer:
    """
    Logo deployment service that copies logos to static locations based on configuration.

    This eliminates the need for dynamic path resolution throughout the codebase.
    All code can simply reference static paths like 'assets/static/platform-logo-horizontal.png'
    """

    # Default logo filenames
    LOGO_FILENAMES = {
        "org_logo_square": "org-logo-square.png",
        "poweredby_logo_square": "poweredby-logo-square.png",
        "platform_logo_square": "platform-logo-square.png",
        "platform_logo_horizontal": "platform-logo-horizontal.png",
    }

    def __init__(self, config_provider=None, static_dir: Optional[str] = None):
        """
        Initialize logo deployer.

        Args:
            config_provider: ConfigProvider instance for accessing logo settings
            static_dir: Directory where static logos will be deployed (defaults to package static dir)
        """
        self.config_provider = config_provider
        self.static_dir = self._get_static_dir(static_dir)
        self.logo_config = self._load_logo_config()

    def _get_static_dir(self, static_dir: Optional[str]) -> Path:
        """Get the static directory path, defaulting to package static directory."""
        if static_dir:
            return Path(static_dir)

        try:
            # Use package static directory by default
            import cdflow_cli

            package_dir = Path(cdflow_cli.__file__).parent
            return package_dir / "assets" / "static"
        except Exception:
            # Fallback to relative path
            return Path("assets/static")

    def _load_logo_config(self) -> Dict[str, Any]:
        """Load logo configuration from config provider."""
        if not self.config_provider:
            return self._get_default_config()

        try:
            logo_config = self.config_provider.get_app_setting(["logos"])
            if not logo_config:
                logger.warning("No logo configuration found, using defaults")
                return self._get_default_config()
            return logo_config
        except Exception as e:
            logger.warning(f"Failed to load logo configuration: {e}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default logo configuration."""
        return {"use_custom": False, "custom_path": "assets/logos/custom", "overrides": {}}

    def _get_package_default_logos_path(self) -> Path:
        """Get the path to package's embedded default logos."""
        try:
            import cdflow_cli

            package_dir = Path(cdflow_cli.__file__).parent
            return package_dir / "assets" / "logos" / "default"
        except Exception as e:
            logger.warning(f"Failed to locate package directory: {e}")
            # Fallback to relative path for development
            return Path("assets/logos/default")

    def deploy_all_logos(self) -> bool:
        """
        Deploy all logos to static locations using two-phase deployment:
        1. Deploy all internal defaults to static directory
        2. Deploy any custom logos to static directory (overwriting defaults)

        Returns:
            bool: True if deployment successful, False otherwise
        """
        logger.debug("Starting two-phase logo deployment to static locations")
        logger.debug(
            f"Logo configuration: use_custom={self.logo_config.get('use_custom')}, custom_path={self.logo_config.get('custom_path')}"
        )

        # Ensure static directory exists
        try:
            self.static_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Static directory ready: {self.static_dir}")
        except Exception as e:
            logger.error(f"Failed to create static directory {self.static_dir}: {e}")
            return False

        # Phase 1: Deploy all internal defaults
        logger.debug("Phase 1: Deploying internal default logos")
        if not self._deploy_default_logos():
            return False

        # Phase 2: Deploy custom logos (if enabled)
        if self.logo_config.get("use_custom", False):
            logger.debug("Phase 2: Deploying custom logos")
            self._deploy_custom_logos()
        else:
            logger.debug("Phase 2: Custom logos disabled, skipping")

        logger.debug("Logo deployment complete")
        return True

    def _deploy_default_logos(self) -> bool:
        """Deploy all internal default logos to static directory."""
        package_defaults_path = self._get_package_default_logos_path()
        success_count = 0
        total_logos = len(self.LOGO_FILENAMES)

        for logo_type, filename in self.LOGO_FILENAMES.items():
            source_path = package_defaults_path / filename
            static_path = self.static_dir / filename

            if source_path.exists():
                try:
                    shutil.copy2(source_path, static_path)
                    logger.debug(f"Deployed default {logo_type}: {source_path} → {static_path}")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to copy default {logo_type}: {e}")
            else:
                logger.warning(f"Default logo not found: {source_path}")
                # Continue without failing - some logos might be missing

        logger.debug(f"Default logo deployment: {success_count}/{total_logos} successful")
        return success_count > 0  # Allow partial success

    def _deploy_custom_logos(self):
        """Deploy any custom logos to static directory (overwriting defaults)."""
        relative_path = self.logo_config.get("custom_path", "assets/logos/custom")
        custom_path = Path(relative_path)

        # Build list of directories to check
        paths_to_check = []

        if custom_path.is_absolute():
            paths_to_check.append(custom_path)
        else:
            # Check both cwd + relative and config_dir + relative
            paths_to_check.append(Path.cwd() / custom_path)

            if self.config_provider and hasattr(self.config_provider, "get_config_directory"):
                config_dir = self.config_provider.get_config_directory()
                if config_dir:
                    paths_to_check.append(config_dir / custom_path)

        deployed_count = 0
        for check_path in paths_to_check:
            if not check_path.exists():
                logger.debug(f"Custom logos directory not found: {check_path}")
                continue

            logger.debug(f"Checking for custom logos in: {check_path}")

            for logo_type, filename in self.LOGO_FILENAMES.items():
                # Check for custom filename override
                actual_filename = self._get_logo_filename(logo_type, filename)
                source_path = check_path / actual_filename
                static_path = self.static_dir / filename  # Always use standard filename in static

                if source_path.exists():
                    try:
                        shutil.copy2(source_path, static_path)
                        logger.debug(f"Deployed custom {logo_type}: {source_path} → {static_path}")
                        deployed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to copy custom {logo_type}: {e}")

        if deployed_count > 0:
            logger.debug(f"Custom logo deployment: {deployed_count} logos deployed")
        else:
            logger.debug("No custom logos found to deploy")

    def _get_logo_filename(self, logo_type: str, default_filename: str) -> str:
        """Get the filename for a logo type, checking overrides first."""
        overrides = self.logo_config.get("overrides", {})
        return overrides.get(logo_type, default_filename)

    def get_static_logo_path(self, logo_type: str) -> Optional[Path]:
        """
        Get the static path where a logo should be deployed.

        Args:
            logo_type: Type of logo

        Returns:
            Path to static logo location
        """
        filename = self.LOGO_FILENAMES.get(logo_type)
        if not filename:
            return None
        return self.static_dir / filename

    def is_deployed(self, logo_type: str) -> bool:
        """Check if a logo is deployed to static location."""
        static_path = self.get_static_logo_path(logo_type)
        return bool(static_path and static_path.exists())

    def redeploy_if_needed(self) -> bool:
        """Redeploy logos if any are missing from static locations."""
        missing_logos = []
        for logo_type in self.LOGO_FILENAMES:
            if not self.is_deployed(logo_type):
                missing_logos.append(logo_type)

        if missing_logos:
            logger.debug(f"Missing logos detected: {missing_logos}, redeploying all")
            return self.deploy_all_logos()

        logger.debug("All logos already deployed")
        return True


# Global deployer instance
_global_deployer = None


def get_logo_deployer(config_provider=None) -> LogoDeployer:
    """
    Get a logo deployer instance.

    Args:
        config_provider: ConfigProvider instance

    Returns:
        LogoDeployer instance
    """
    global _global_deployer
    if _global_deployer is None or config_provider is not None:
        _global_deployer = LogoDeployer(config_provider)
    return _global_deployer


def deploy_logos(config_provider=None) -> bool:
    """Convenience function to deploy all logos."""
    deployer = get_logo_deployer(config_provider)
    return deployer.deploy_all_logos()


def ensure_logos_deployed(config_provider=None) -> bool:
    """Convenience function to ensure logos are deployed (redeploy if missing)."""
    deployer = get_logo_deployer(config_provider)
    return deployer.redeploy_if_needed()
