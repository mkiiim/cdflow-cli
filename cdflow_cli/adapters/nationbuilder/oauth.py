# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
NationBuilder OAuth authentication module.

This module handles the OAuth flow for authenticating with the NationBuilder API.
It manages token acquisition, refresh, and validation.
"""

import yaml
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import time
import logging
import secrets
from typing import Any, Dict, Optional, Union
from urllib.parse import parse_qs, urlparse

from ...nationbuilder_auth_core.errors import TokenExchangeError, TokenRefreshError
from ...nationbuilder_auth_core.models import OAuthConfig, TokenSet
from ...nationbuilder_auth_core.token_client import NationBuilderTokenClient
from ...nationbuilder_auth_core.token_provider import NationBuilderTokenProvider
from ...nationbuilder_auth_core.token_state import InMemoryTokenState

logger = logging.getLogger(__name__)


def get_logo_base64(config_provider=None) -> str:
    """Get the platform horizontal logo as base64 data URL from static location"""
    logger.debug("Loading platform logo from static location")
    try:
        import base64
        from pathlib import Path

        # Load from package static location - logo deployer handles the complexity
        try:
            import cdflow_cli

            package_dir = Path(cdflow_cli.__file__).parent
            static_logo_path = package_dir / "assets/static/platform-logo-horizontal.png"
        except Exception:
            static_logo_path = Path("assets/static/platform-logo-horizontal.png")

        logger.debug(f"Loading logo from static path: {static_logo_path}")
        logger.debug(f"Static logo exists: {static_logo_path.exists()}")

        if static_logo_path.exists():
            with open(static_logo_path, "rb") as img_file:
                logger.debug("Successfully loaded static logo")
                return f"data:image/png;base64,{base64.b64encode(img_file.read()).decode('utf-8')}"
        else:
            logger.warning(f"Static logo not found at {static_logo_path}")
    except Exception as e:
        logger.error(f"Error loading static logo: {e}")
        import traceback

        logger.debug(f"Static logo error traceback: {traceback.format_exc()}")

    # Ultimate fallback - transparent pixel
    logger.debug("Returning transparent fallback")
    return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="


class CallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback requests on the local server."""

    def __init__(self, *args, config_provider=None, **kwargs):
        self.config_provider = config_provider
        super().__init__(*args, **kwargs)

    def get_processing_html(self):
        """Generate neutral processing HTML for the OAuth callback window."""
        logo_base64 = get_logo_base64(self.config_provider)
        return f"""
         <html>
             <head>
                 <title>Auth Complete</title>
                 <script>
                     // Close the window after 1.5 seconds
                     setTimeout(function() {{
                         window.close();
                     }}, 1500);
                 </script>
                 <style>
                     body {{
                         font-family: 'Poppins Light', sans-serif;
                         background-color: #f2f2f2;
                         display: flex;
                         justify-content: center;
                         align-items: center;
                         height: 100vh;
                         margin: 0;
                     }}
                     .message-box {{
                         background: white;
                         padding: 2em;
                         border-radius: 10px;
                         box-shadow: 0 0 20px rgba(0,0,0,0.1);
                         text-align: center;
                     }}
                 </style>
             </head>
             <body>
                 <div class="message-box">
                     <img src="{logo_base64}" alt="Platform Logo" style="height: 80px; width: auto; margin-bottom: 20px;">
                     <h2>Processing Authentication</h2>
                     <p>Please wait while the CLI validates the callback. This window should close automatically.</p>
                 </div>
             </body>
         </html>
     """

    def do_GET(self) -> None:
        """Process GET requests and extract the authorization code."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        processing_html = self.get_processing_html()
        self.wfile.write(processing_html.encode("utf-8"))

        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        self.server.callback_code = query.get("code", [None])[0]
        self.server.callback_state = query.get("state", [None])[0]

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging of HTTP requests."""
        pass


class NationBuilderOAuth:
    """
    Handles OAuth authentication for NationBuilder API.
    Manages token acquisition and validation.
    """

    def __init__(self, config: Dict, auto_initialize: bool = False):
        """
        Initialize the NationBuilder OAuth client.

        Args:
            config: OAuth configuration dictionary
            auto_initialize: Whether to automatically initialize the OAuth token
        """
        logger.debug("Loading OAuth configuration from provided dictionary")
        if not config.get("slug"):
            logger.warning("Config dictionary does not contain 'slug' key")
        self.config = config

        self.slug = self.config["slug"]
        self.client_id = self.config["client_id"]
        self.client_secret = self.config["client_secret"]
        self.redirect_uri = self.config["redirect_uri"]
        self.callback_bind_host = self.config["callback_bind_host"]
        self.callback_port = self.config["callback_port"]

        # Initialize instance variables for token storage
        self.nb_jwt_token = None
        self.nb_refresh_token = None
        self.nb_token_created_at = None
        self.nb_token_expires_in = None

        # For state parameter validation
        self.current_state = None
        self._core_oauth_config = OAuthConfig(
            slug=self.slug,
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
        )
        self.token_state = InMemoryTokenState()
        self.token_client = NationBuilderTokenClient(self._core_oauth_config, session=requests)
        self.token_provider = NationBuilderTokenProvider(self.token_state, self.token_client)

        logger.debug(f"OAuth configuration loaded successfully. Nation slug: {self.slug}")

        if auto_initialize:
            logger.debug("Auto-initialization requested")
            self.initialize()

    def initialize(self) -> bool:
        """
        Explicitly initialize the OAuth token.
        This triggers the API calls to get an access token.

        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        logger.debug("Explicitly initializing OAuth token")
        self._sync_token_state_from_legacy_attrs()

        if self.token_state.has_tokens():
            access_token = self.token_provider.get_access_token()
            if access_token:
                self._sync_legacy_attrs_from_token_state()
                logger.debug("Already have valid tokens, skipping initialization")
                return True

        access_token = self.get_access_token()

        return access_token is not None


    def generate_state(self) -> str:
        """
        Generate a secure random state parameter for OAuth flow.

        Returns:
            str: Random state parameter
        """
        state = secrets.token_urlsafe(32)
        self.current_state = state
        return state

    def get_auth_code(self, timeout: int = 10) -> Optional[str]:
        """
        Start local server and get authorization code through OAuth flow.

        Args:
            timeout (int): Number of seconds to wait for callback

        Returns:
            str or None: Authorization code if successful, None otherwise
        """
        try:
            server = HTTPServer((self.callback_bind_host, self.callback_port), CallbackHandler)
            server.callback_code = None
            server.callback_state = None
        except Exception as e:
            logger.error(
                f"Error: Failed to create HTTP server on port {self.callback_port}. {str(e)}"
            )
            return None

        # Generate state parameter for CSRF protection
        state = self.generate_state()
        logger.debug(f"Generated state parameter: {state[:5]}...")

        auth_url = (
            f"https://{self.slug}.nationbuilder.com/oauth/authorize"
            f"?response_type=code"
            f"&client_id={self.client_id}"
            f"&redirect_uri={self.redirect_uri}"
            f"&state={state}"
        )

        # Try to open the web browser to the NationBuilder authorization URL
        try:
            webbrowser.open(auth_url)
        except Exception as e:
            logger.error(f"Error: Failed to open web browser. {str(e)}")
            return None

        # Wait for the callback request with the authorization code or timeout
        start_time = time.time()
        try:
            while server.callback_code is None:
                if time.time() - start_time > timeout:
                    raise TimeoutError("Error: Timeout waiting for OAuth callback")
                server.handle_request()

            # Validate state parameter to prevent CSRF attacks
            if server.callback_state != self.current_state:
                logger.error("Error: State parameter mismatch in callback")
                return None

        except TimeoutError as e:
            logger.error(str(e))
            return None
        except Exception as e:
            logger.error(f"Unexpected error occurred: {e}")
            return None
        finally:
            server.server_close()

        # Check if the callback request contained an authorization code
        if server.callback_code is None:
            logger.error("Error: Did not receive authorization code in callback request.")
            return None

        logger.debug("Successfully received authorization code")
        return server.callback_code

    def get_access_token(self) -> Optional[str]:
        """
        Exchange authorization code for access token.

        Returns:
            str or None: Access token if successful, None otherwise
        """
        # Get authorization code
        authorization_code = self.get_auth_code()
        if authorization_code is None:
            logger.error("Error: Failed to get authorization code.")
            return None

        try:
            logger.debug("Requesting access token from NationBuilder token endpoint")
            token_set = self.token_client.exchange_code(authorization_code)
            self._set_token_set(token_set)
            logger.debug("Successfully obtained NationBuilder access token")
            return self.nb_jwt_token

        except TokenExchangeError as e:
            logger.error(f"Error exchanging code for token: {e}")
            return None

    def refresh_access_token(self) -> Optional[str]:
        """
        Refresh the access token using the refresh token.

        Returns:
            str or None: Access token if successful, None otherwise
        """

        refresh_token = self.nb_refresh_token or self.token_state.refresh_token
        if not refresh_token:
            logger.error("No refresh token available")
            return None

        # Debug logging: show current token state before refresh
        current_time = time.time()
        if self.nb_token_created_at and self.nb_token_expires_in:
            token_age = current_time - self.nb_token_created_at
            expires_at = self.nb_token_created_at + self.nb_token_expires_in
            time_until_expiry = expires_at - current_time
            logger.info(
                f"DEBUG - Token refresh triggered: current token age={token_age:.1f}s, expires in={time_until_expiry:.1f}s"
            )
        else:
            logger.info(f"DEBUG - Token refresh triggered: missing token metadata")

        try:
            logger.debug("Refreshing access token from NationBuilder token endpoint")
            token_set = self.token_client.refresh_token(refresh_token)
            self._set_token_set(token_set)
            logger.info(
                f"DEBUG - Token refresh successful: new token expires in {self.nb_token_expires_in} seconds"
            )
            logger.debug("Successfully refreshed NationBuilder access token")
            return self.nb_jwt_token

        except TokenRefreshError as e:
            logger.error(f"Error refreshing token: {e}")
            return None

    def token_is_valid(self) -> bool:
        """
        Check if the NationBuilder JWT token is still valid.

        Returns:
            bool: True if the token exists and is decodable, False otherwise
        """
        self._sync_token_state_from_legacy_attrs()
        if self.nb_jwt_token is None:
            logger.debug("DEBUG - Token validation: No token available")
            return False

        logger.debug(f"DEBUG - Token validation metadata: created_at={self.nb_token_created_at}, expires_in={self.nb_token_expires_in}")
        if self.token_state.expires_at is not None:
            time_until_expiry = self.token_state.expires_at - time.time()
            if time_until_expiry <= 60:
                logger.info(
                    f"DEBUG - Token validation: Token expires soon ({time_until_expiry:.1f}s), needs refresh"
                )
                return False
            logger.debug(
                f"DEBUG - Token validation: Token valid, expires in {time_until_expiry:.1f} seconds"
            )
            return True

        try:
            # Fallback: check if token can be decoded (for tokens without metadata)
            import jose.jwt

            decoded = jose.jwt.decode(
                self.nb_jwt_token, options={"verify_signature": False}, key=None
            )

            # Check JWT exp field if available
            exp = decoded.get("exp")
            current_time = time.time()

            if exp:
                time_until_expiry = exp - current_time
                if time_until_expiry <= 60:
                    logger.info(
                        f"DEBUG - Token validation: JWT token expires soon ({time_until_expiry:.1f}s), needs refresh"
                    )
                    return False
                else:
                    logger.debug(
                        f"DEBUG - Token validation: JWT token valid, expires in {time_until_expiry:.1f} seconds"
                    )
                    return True
            else:
                logger.warning(
                    "DEBUG - Token validation: No expiration data available, treating token as invalid"
                )
                return False

        except Exception as e:
            logger.debug(f"DEBUG - Token validation: Token invalid - {str(e)}")
            return False

    def _sync_token_state_from_legacy_attrs(self) -> None:
        """Keep the new token state aligned with legacy mutable attributes."""
        self.token_state.now_fn = time.time
        if not self.nb_jwt_token:
            if self.token_state.has_tokens():
                self.token_state.clear()
            return

        token_set = TokenSet(
            access_token=self.nb_jwt_token,
            refresh_token=self.nb_refresh_token,
            expires_in=self.nb_token_expires_in,
            created_at=self.nb_token_created_at,
        )
        if self.token_state.token_set != token_set:
            self.token_state.set_tokens(token_set)

    def _sync_legacy_attrs_from_token_state(self) -> None:
        """Keep legacy instance attributes aligned with token state."""
        token_set = self.token_state.token_set
        if token_set is None:
            self.nb_jwt_token = None
            self.nb_refresh_token = None
            self.nb_token_expires_in = None
            self.nb_token_created_at = None
        else:
            self.nb_jwt_token = token_set.access_token
            self.nb_refresh_token = token_set.refresh_token
            self.nb_token_expires_in = token_set.expires_in
            self.nb_token_created_at = token_set.created_at

    def _set_token_set(self, token_set: TokenSet) -> None:
        """Replace current token state and synchronize legacy compatibility fields."""
        self.token_state.set_tokens(token_set)
        self._sync_legacy_attrs_from_token_state()
