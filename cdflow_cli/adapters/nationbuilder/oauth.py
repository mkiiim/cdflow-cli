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
from functools import wraps
from typing import Any, Dict, Optional, Union

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

    def get_success_html(self):
        """Generate success HTML with dynamic logo loading."""
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
                     <h2>Authentication Complete</h2>
                     <p>This window should close automatically. It is safe to close manually.</p>
                 </div>
             </body>
         </html>
     """

    def do_GET(self) -> None:
        """Process GET requests and extract the authorization code."""
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()

        success_html = self.get_success_html()
        self.wfile.write(success_html.encode("utf-8"))

        if "?code=" in self.path:
            code_segment = self.path.split("?code=")[1]
            code = code_segment.split("&")[0] if "&" in code_segment else code_segment
            self.server.callback_code = code

            # Extract state parameter if present
            if "state=" in self.path:
                state_segment = self.path.split("state=")[1]
                state = state_segment.split("&")[0] if "&" in state_segment else state_segment
                self.server.callback_state = state
            else:
                self.server.callback_state = None
        else:
            self.server.callback_code = None
            self.server.callback_state = None

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default logging of HTTP requests."""
        pass


class NationBuilderOAuth:
    """
    Handles OAuth authentication for NationBuilder API.
    Manages token acquisition and validation.
    """

    # Class variables to maintain backward compatibility
    # These will be synchronized with instance variables
    nb_jwt_token = None
    nb_refresh_token = None
    nb_token_created_at = None
    nb_token_expires_in = None

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
        self.callback_port = self.config["callback_port"]

        # Initialize instance variables for token storage
        self.nb_jwt_token = None
        self.nb_refresh_token = None
        self.nb_token_created_at = None
        self.nb_token_expires_in = None

        # For state parameter validation
        self.current_state = None

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

        # Check if we already have valid tokens
        if self.nb_jwt_token is not None and self.token_is_valid():
            logger.debug("Already have valid tokens, skipping initialization")
            return True

        # Otherwise, get a new access token
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
            server = HTTPServer(("0.0.0.0", self.callback_port), CallbackHandler)
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

        token_url = f"https://{self.slug}.nationbuilder.com/oauth/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "code": authorization_code,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Get access token
        try:
            logger.debug(f"Requesting access token from {token_url}")
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()

            token_data = response.json()

            # Store tokens in instance variables
            self.nb_jwt_token = token_data.get("access_token")
            self.nb_refresh_token = token_data.get("refresh_token")
            self.nb_token_expires_in = token_data.get("expires_in")
            self.nb_token_created_at = token_data.get("created_at")

            # Also store in class variables for backward compatibility
            NationBuilderOAuth.nb_jwt_token = self.nb_jwt_token
            NationBuilderOAuth.nb_refresh_token = self.nb_refresh_token
            NationBuilderOAuth.nb_token_expires_in = self.nb_token_expires_in
            NationBuilderOAuth.nb_token_created_at = self.nb_token_created_at

            logger.debug(
                f"Successfully obtained NB JWT token ending in ...{self.nb_jwt_token[-5:]}"
            )
            logger.debug(f"Refresh token ending in ...{self.nb_refresh_token[-5:]}")
            logger.debug(f"Token expires in {self.nb_token_expires_in} seconds")

            return self.nb_jwt_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Error exchanging code for token: {e}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response: {e.response.text}")
            return None

    def refresh_access_token(self) -> Optional[str]:
        """
        Refresh the access token using the refresh token.

        Returns:
            str or None: Access token if successful, None otherwise
        """

        if not self.nb_refresh_token:
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

        token_url = f"https://{self.slug}.nationbuilder.com/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.nb_refresh_token,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Get access token
        try:
            logger.debug(f"Refreshing access token from {token_url}")
            response = requests.post(token_url, headers=headers, data=data)
            response.raise_for_status()

            token_data = response.json()
            
            # Store tokens in instance variables
            self.nb_jwt_token = token_data.get("access_token")
            self.nb_refresh_token = token_data.get("refresh_token")
            self.nb_token_expires_in = token_data.get("expires_in")
            self.nb_token_created_at = token_data.get("created_at")

            # Also store in class variables for backward compatibility
            NationBuilderOAuth.nb_jwt_token = self.nb_jwt_token
            NationBuilderOAuth.nb_refresh_token = self.nb_refresh_token
            NationBuilderOAuth.nb_token_expires_in = self.nb_token_expires_in
            NationBuilderOAuth.nb_token_created_at = self.nb_token_created_at

            logger.info(
                f"DEBUG - Token refresh successful: new token expires in {self.nb_token_expires_in} seconds"
            )
            logger.debug(
                f"Successfully refreshed NB JWT token ending in ...{self.nb_jwt_token[-5:]}"
            )
            logger.debug(f"Refresh token ending in ...{self.nb_refresh_token[-5:]}")

            return self.nb_jwt_token

        except requests.exceptions.RequestException as e:
            logger.error(f"Error refreshing token: {e}")
            if hasattr(e, "response") and e.response:
                logger.error(f"Response: {e.response.text}")
            return None

    def token_is_valid(self) -> bool:
        """
        Check if the NationBuilder JWT token is still valid.

        Returns:
            bool: True if the token exists and is decodable, False otherwise
        """
        if self.nb_jwt_token is None:
            logger.debug("DEBUG - Token validation: No token available")
            return False

        # Check expiration using stored token metadata (more reliable than JWT exp field)
        logger.debug(f"DEBUG - Token validation metadata: created_at={self.nb_token_created_at}, expires_in={self.nb_token_expires_in}")
        if self.nb_token_created_at and self.nb_token_expires_in:
            current_time = time.time()
            expires_at = self.nb_token_created_at + self.nb_token_expires_in
            time_until_expiry = expires_at - current_time

            # Refresh if token expires in less than 60 seconds
            if time_until_expiry <= 60:
                logger.info(
                    f"DEBUG - Token validation: Token expires soon ({time_until_expiry:.1f}s), needs refresh"
                )
                return False
            else:
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
                    "DEBUG - Token validation: No expiration data available, assuming valid (risky)"
                )
                return True

        except Exception as e:
            logger.debug(f"DEBUG - Token validation: Token invalid - {str(e)}")
            return False

    @staticmethod
    def ensure_valid_nb_jwt(func):
        """
        Decorator to ensure that the NationBuilder JWT token is valid before making a request.
        Works with both instance variables and class variables for backward compatibility.

        Args:
            func: Function to decorate

        Returns:
            callable: Decorated function
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            oauth_instance = getattr(self, "oauth", None)

            logger.debug(f"DEBUG - OAuth decorator called for {func.__name__}")

            if oauth_instance:
                # Use instance variables if available (preferred method)
                if oauth_instance.nb_jwt_token is None:
                    logger.info(
                        f"DEBUG - OAuth: Token not initialized for {func.__name__}, initializing now"
                    )
                    oauth_instance.initialize()
                elif not oauth_instance.token_is_valid():
                    logger.info(f"DEBUG - OAuth: Token expired for {func.__name__}, refreshing now")
                    oauth_instance.refresh_access_token()
                else:
                    logger.debug(f"DEBUG - OAuth: Token valid for {func.__name__}, proceeding")

                # Update headers with the latest token from the instance
                if hasattr(self, "_update_headers") and callable(self._update_headers):
                    self._update_headers()
                else:
                    # Fall back to direct header update
                    self.headers = {"Authorization": f"Bearer {oauth_instance.nb_jwt_token}"}

            else:
                # Fall back to class variables for backward compatibility (CLI tool)
                if NationBuilderOAuth.nb_jwt_token is None:
                    logger.info(
                        f"DEBUG - OAuth: Class token not initialized for {func.__name__}, but no oauth instance available"
                    )
                    # Without an instance, we can't initialize - this is a potential issue point
                    # For CLI, this would need to be handled elsewhere
                else:
                    # Use existing class token (already initialized by CLI)
                    logger.debug(f"DEBUG - OAuth: Using class token for {func.__name__}")
                    self.headers = {"Authorization": f"Bearer {NationBuilderOAuth.nb_jwt_token}"}

            return func(self, *args, **kwargs)

        return wrapper
