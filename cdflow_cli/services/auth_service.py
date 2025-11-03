# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Unified Authentication Service for NationBuilder OAuth.

This service provides a consistent authentication interface for both CLI and API contexts
while preserving backward compatibility with existing CLI implementations.
"""

import logging
import time
from typing import Dict, Any, Optional, Union, Callable
from enum import Enum
from dataclasses import dataclass

from ..adapters.nationbuilder.oauth import NationBuilderOAuth
from ..utils.config import ConfigProvider

logger = logging.getLogger(__name__)


class AuthContext(Enum):
    """Authentication context types."""

    CLI = "cli"
    API = "api"
    TEST = "test"


@dataclass
class AuthState:
    """Represents the current authentication state."""

    is_authenticated: bool = False
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None
    user_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """Check if the token is expired."""
        if not self.expires_at:
            return False
        return time.time() >= self.expires_at

    @property
    def expires_in_seconds(self) -> Optional[int]:
        """Get seconds until token expires."""
        if not self.expires_at:
            return None
        return max(0, int(self.expires_at - time.time()))


class UnifiedAuthService:
    """
    Unified authentication service that provides consistent OAuth handling
    across CLI and API contexts while maintaining backward compatibility.
    """

    def __init__(
        self,
        config: Union[str, Dict[str, Any], ConfigProvider],
        context: AuthContext = AuthContext.CLI,
        progress_callback: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the unified authentication service.

        Args:
            config: Configuration (file path, dict, or ConfigProvider)
            context: Authentication context (CLI, API, or TEST)
            progress_callback: Optional callback for progress updates
        """
        self.context = context
        self.progress_callback = progress_callback or (lambda msg: None)

        # Initialize configuration
        if isinstance(config, ConfigProvider):
            self.config_provider = config
            oauth_config = config.get_oauth_config()
        elif isinstance(config, str):
            self.config_provider = ConfigProvider(config)
            oauth_config = self.config_provider.get_oauth_config()
        else:
            # Direct config dict
            self.config_provider = None
            oauth_config = config

        # Initialize the underlying OAuth handler
        # Skip auto-initialization for API context to prevent startup deadlock
        # CLI context uses on-demand authentication as needed
        auto_init = False  # Never auto-initialize to prevent deadlock
        self.oauth = NationBuilderOAuth(oauth_config, auto_initialize=auto_init)

        # Track authentication state
        self._auth_state = AuthState()

        # Context-specific initialization
        if context == AuthContext.CLI:
            self._initialize_cli_context()
        elif context == AuthContext.API:
            self._initialize_api_context()

        logger.debug(f"UnifiedAuthService initialized for {context.value} context")

    def _initialize_cli_context(self) -> None:
        """Initialize CLI-specific authentication behavior."""
        # CLI doesn't pre-authenticate - it authenticates on-demand
        # This preserves the existing CLI workflow
        logger.debug("Initialized CLI authentication context")

    def _initialize_api_context(self) -> None:
        """Initialize API-specific authentication behavior."""
        # API context defers OAuth initialization to prevent startup deadlock
        # OAuth will be initialized on-demand when authentication is needed
        logger.debug("Initialized API authentication context - OAuth deferred to login requests")

    def _update_auth_state_from_oauth(self) -> None:
        """Update internal auth state from OAuth instance."""
        if self.oauth.nb_jwt_token:
            self._auth_state.is_authenticated = True
            self._auth_state.access_token = self.oauth.nb_jwt_token
            self._auth_state.refresh_token = self.oauth.nb_refresh_token

            # Calculate expiration time
            if self.oauth.nb_token_created_at and self.oauth.nb_token_expires_in:
                self._auth_state.expires_at = (
                    self.oauth.nb_token_created_at + self.oauth.nb_token_expires_in
                )

            self._auth_state.error = None
            logger.debug("Updated auth state from OAuth instance")
        else:
            self._auth_state.is_authenticated = False
            self._auth_state.access_token = None
            self._auth_state.refresh_token = None
            self._auth_state.expires_at = None

    def authenticate(self, force_refresh: bool = False) -> bool:
        """
        Authenticate with NationBuilder.

        Args:
            force_refresh: Force a new authentication even if token exists

        Returns:
            bool: True if authentication successful
        """
        try:
            # Check if we already have a valid token and don't need to refresh
            if (
                not force_refresh
                and self._auth_state.is_authenticated
                and not self._auth_state.is_expired
            ):
                logger.debug("Already authenticated with valid token")
                return True

            # Try to refresh existing token if available
            if not force_refresh and self._auth_state.refresh_token and self._auth_state.is_expired:
                logger.debug("Token expired, attempting refresh")
                self.progress_callback("Refreshing authentication token...")

                if self.oauth.refresh_access_token():
                    self._update_auth_state_from_oauth()
                    self.progress_callback("Token refreshed successfully")
                    return True
                else:
                    logger.warning("Token refresh failed, falling back to full authentication")

            # Perform full authentication
            logger.debug("Performing full OAuth authentication")
            self.progress_callback("Starting NationBuilder authentication...")

            # CLI context uses the existing robust flow
            if self.context == AuthContext.CLI:
                access_token = self.oauth.get_access_token()
            else:
                # API context uses initialize method
                success = self.oauth.initialize()
                access_token = self.oauth.nb_jwt_token if success else None

            if access_token:
                self._update_auth_state_from_oauth()
                self.progress_callback("Authentication completed successfully")
                logger.info("Authentication successful")
                return True
            else:
                self._auth_state.error = "Failed to obtain access token"
                self.progress_callback("Authentication failed")
                logger.error("Authentication failed: could not obtain access token")
                return False

        except Exception as e:
            error_msg = f"Authentication error: {str(e)}"
            self._auth_state.error = error_msg
            self.progress_callback(f"Authentication failed: {error_msg}")
            logger.error(error_msg, exc_info=True)
            return False

    def get_auth_state(self) -> AuthState:
        """Get the current authentication state."""
        # Ensure state is up-to-date
        if self.oauth.nb_jwt_token and not self._auth_state.is_authenticated:
            self._update_auth_state_from_oauth()
        return self._auth_state

    def get_access_token(self) -> Optional[str]:
        """
        Get a valid access token, authenticating if necessary.

        Returns:
            str or None: Valid access token or None if authentication fails
        """
        # Check if we need to authenticate
        if not self._auth_state.is_authenticated or self._auth_state.is_expired:
            if not self.authenticate():
                return None

        return self._auth_state.access_token

    def invalidate(self) -> None:
        """Invalidate the current authentication state."""
        logger.debug("Invalidating authentication state")

        # Clear OAuth tokens
        self.oauth.nb_jwt_token = None
        self.oauth.nb_refresh_token = None
        self.oauth.nb_token_created_at = None
        self.oauth.nb_token_expires_in = None

        # Clear class variables for backward compatibility
        NationBuilderOAuth.nb_jwt_token = None
        NationBuilderOAuth.nb_refresh_token = None
        NationBuilderOAuth.nb_token_created_at = None
        NationBuilderOAuth.nb_token_expires_in = None

        # Reset auth state
        self._auth_state = AuthState()

    def is_authenticated(self) -> bool:
        """Check if currently authenticated with a valid token."""
        state = self.get_auth_state()
        return state.is_authenticated and not state.is_expired

    def get_oauth_instance(self) -> NationBuilderOAuth:
        """
        Get the underlying OAuth instance for backward compatibility.

        Returns:
            NationBuilderOAuth: The OAuth instance
        """
        return self.oauth

    def ensure_valid_token(self) -> bool:
        """
        Ensure we have a valid token, refreshing or re-authenticating as needed.

        Returns:
            bool: True if we have a valid token
        """
        return self.get_access_token() is not None


def create_auth_service(
    config: Union[str, Dict[str, Any], ConfigProvider],
    context: AuthContext = AuthContext.CLI,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> UnifiedAuthService:
    """
    Factory function to create authentication service instances.

    Args:
        config: Configuration (file path, dict, or ConfigProvider)
        context: Authentication context
        progress_callback: Optional progress callback

    Returns:
        UnifiedAuthService: Configured authentication service
    """
    return UnifiedAuthService(config, context, progress_callback)


def create_cli_auth_service(
    config: Union[str, Dict[str, Any], ConfigProvider],
) -> UnifiedAuthService:
    """
    Create an authentication service configured for CLI use.

    Args:
        config: Configuration (file path, dict, or ConfigProvider)

    Returns:
        UnifiedAuthService: CLI-configured authentication service
    """
    return create_auth_service(config, AuthContext.CLI)


def create_api_auth_service(
    config: Union[str, Dict[str, Any], ConfigProvider],
    progress_callback: Optional[Callable[[str], None]] = None,
) -> UnifiedAuthService:
    """
    Create an authentication service configured for API use.

    Args:
        config: Configuration (file path, dict, or ConfigProvider)
        progress_callback: Optional progress callback for long operations

    Returns:
        UnifiedAuthService: API-configured authentication service
    """
    return create_auth_service(config, AuthContext.API, progress_callback)
