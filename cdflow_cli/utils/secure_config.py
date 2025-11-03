# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Secure configuration utilities for handling sensitive OAuth credentials.
"""

import os
import sys
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class SecureConfigValidator:
    """Validates and secures OAuth configuration at runtime."""

    REQUIRED_VARS = ["NB_SLUG", "NB_CLIENT_ID", "NB_CLIENT_SECRET"]
    PLACEHOLDER_PATTERNS = ["your-", "example-", "placeholder-", "change-this"]

    @classmethod
    def validate_environment(cls) -> bool:
        """
        Validate that all required OAuth environment variables are present
        and don't contain placeholder values.
        """
        missing_vars = []
        placeholder_vars = []

        for var in cls.REQUIRED_VARS:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
                continue

            # Check for placeholder values
            if any(pattern in value.lower() for pattern in cls.PLACEHOLDER_PATTERNS):
                placeholder_vars.append(var)

        if missing_vars:
            logger.error(f"Missing required environment variables: {missing_vars}")
            return False

        if placeholder_vars:
            logger.error(f"Environment variables contain placeholder values: {placeholder_vars}")
            return False

        # Validate secret format
        client_secret = os.getenv("NB_CLIENT_SECRET")
        if len(client_secret) < 16:
            logger.warning("Client secret appears to be too short (< 16 characters)")

        logger.info("OAuth environment validation passed")
        return True

    @classmethod
    def get_oauth_config(cls) -> Dict[str, Any]:
        """
        Get OAuth configuration from environment variables with validation.
        """
        if not cls.validate_environment():
            raise ValueError("OAuth configuration validation failed")

        config = {
            "slug": os.getenv("NB_SLUG"),
            "client_id": os.getenv("NB_CLIENT_ID"),
            "client_secret": os.getenv("NB_CLIENT_SECRET"),
            "config_name": os.getenv("NB_CONFIG_NAME", "not_configured"),
        }
        
        # Only add redirect_uri if explicitly set via environment variable
        # Let CLI use its own redirect URI construction logic
        redirect_uri = os.getenv("NB_REDIRECT_URI")
        if redirect_uri:
            config["redirect_uri"] = redirect_uri
            
        return config


class SecretManager:
    """
    Manages secrets using environment variables only.
    """

    def get_oauth_config(self) -> Dict[str, Any]:
        """Get OAuth configuration from environment variables."""
        return SecureConfigValidator.get_oauth_config()


def secure_startup_check():
    """
    Perform security checks at application startup.
    Call this early in your application initialization.
    """
    logger.info("Performing security startup checks...")

    # Check if secrets are exposed in command line
    import psutil

    try:
        current_process = psutil.Process()
        cmdline = " ".join(current_process.cmdline())

        sensitive_patterns = ["client_secret", "password", "token"]
        for pattern in sensitive_patterns:
            if pattern.lower() in cmdline.lower():
                logger.warning(f"Potential secret exposure in command line: {pattern}")
    except (psutil.AccessDenied, psutil.NoSuchProcess) as exc:
        logger.warning(f"Unable to inspect process command line (psutil error: {exc})")

    # Check environment variables
    if not SecureConfigValidator.validate_environment():
        logger.error("Security validation failed - exiting")
        sys.exit(1)

    # OAuth configuration is now environment-based only

    logger.info("Security startup checks completed")


if __name__ == "__main__":
    # Test the security validation
    logging.basicConfig(level=logging.INFO)
    secure_startup_check()

    try:
        config = SecureConfigValidator.get_oauth_config()
        print("✅ OAuth configuration valid")
        print(f"Nation: {config['slug']}")
        print(f"Client ID: {config['client_id'][:8]}...")
        print(f"Redirect URI: {config['redirect_uri']}")
    except Exception as e:
        print(f"❌ OAuth configuration error: {e}")
        sys.exit(1)
