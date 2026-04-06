# SPDX-FileCopyrightText: 2026 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""Runtime-neutral NationBuilder token exchange and refresh client."""

import logging
from typing import Optional, Tuple

import requests

from .errors import AuthConfigurationError, TokenExchangeError, TokenRefreshError
from .models import OAuthConfig, TokenSet

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 30.0)


class NationBuilderTokenClient:
    """Perform NationBuilder OAuth token exchange and refresh operations."""

    def __init__(
        self,
        oauth_config: OAuthConfig,
        timeout: Tuple[float, float] = DEFAULT_TIMEOUT,
        session: Optional[requests.sessions.Session] = None,
    ):
        self.oauth_config = oauth_config
        self.timeout = timeout
        self.session = session or requests.Session()
        self._validate_config()

    def exchange_code(self, authorization_code: str) -> TokenSet:
        """Exchange an authorization code for a token set."""
        if not authorization_code:
            raise TokenExchangeError("Authorization code is required")

        data = {
            "grant_type": "authorization_code",
            "client_id": self.oauth_config.client_id,
            "client_secret": self.oauth_config.client_secret,
            "redirect_uri": self.oauth_config.redirect_uri,
            "code": authorization_code,
        }
        return self._post_for_tokens(data, TokenExchangeError, "authorization code exchange")

    def refresh_token(self, refresh_token: str) -> TokenSet:
        """Refresh an access token using a refresh token."""
        if not refresh_token:
            raise TokenRefreshError("Refresh token is required")

        data = {
            "grant_type": "refresh_token",
            "client_id": self.oauth_config.client_id,
            "client_secret": self.oauth_config.client_secret,
            "refresh_token": refresh_token,
        }
        return self._post_for_tokens(data, TokenRefreshError, "token refresh")

    @property
    def token_url(self) -> str:
        """NationBuilder OAuth token endpoint."""
        return f"https://{self.oauth_config.slug}.nationbuilder.com/oauth/token"

    def _validate_config(self) -> None:
        missing = [
            field_name
            for field_name, value in (
                ("slug", self.oauth_config.slug),
                ("client_id", self.oauth_config.client_id),
                ("client_secret", self.oauth_config.client_secret),
                ("redirect_uri", self.oauth_config.redirect_uri),
            )
            if not value
        ]
        if missing:
            raise AuthConfigurationError(
                f"Missing required OAuth configuration fields: {', '.join(missing)}"
            )

    def _post_for_tokens(self, data, error_type, operation_name: str) -> TokenSet:
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = self.session.post(
                self.token_url,
                headers=headers,
                data=data,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.exceptions.Timeout as exc:
            raise error_type(f"NationBuilder {operation_name} timed out") from exc
        except requests.exceptions.RequestException as exc:
            message = f"NationBuilder {operation_name} failed"
            if hasattr(exc, "response") and exc.response is not None and exc.response.text:
                message = f"{message}: {exc.response.text}"
            raise error_type(message) from exc

        token_data = response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise error_type(f"NationBuilder {operation_name} returned no access token")

        logger.debug("NationBuilder %s succeeded", operation_name)
        return TokenSet(
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
            created_at=token_data.get("created_at"),
        )
