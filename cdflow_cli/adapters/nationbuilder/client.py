# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import requests
import logging

from cdflow_cli.nationbuilder_auth_core.session import NationBuilderAuthorizedSession
from cdflow_cli.nationbuilder_auth_core.token_client import DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)


def encode_uri(input_uri):
    # requote_uri does not replace '+' with '%2B' so we need to do it manually
    input_uri = input_uri.replace("+", "%2B")
    return requests.utils.requote_uri(input_uri)


class NBClient:
    """
    Base client for interacting with the NationBuilder API.
    Provides common functionality for all API client classes.
    """

    def __init__(self, oauth=None, token_provider=None, request_timeout=DEFAULT_TIMEOUT):
        """
        Initialize the client with NationBuilder auth credentials.

        Args:
            oauth: Legacy NationBuilderOAuth instance with valid credentials
            token_provider: New runtime-neutral token provider
            request_timeout: Shared request timeout for NationBuilder API calls
        """
        if oauth is None and token_provider is None:
            raise ValueError("NBClient requires either oauth or token_provider")

        # Transitional compatibility seam.
        # Remove legacy oauth= support after all NationBuilder adapters are rewired to token_provider.
        self.oauth = oauth
        self.token_provider = token_provider
        self.request_timeout = request_timeout
        self.authorized_session = (
            NationBuilderAuthorizedSession(token_provider) if token_provider is not None else None
        )

        identity_source = oauth if oauth is not None else token_provider.token_client.oauth_config
        self.nation_slug = identity_source.slug

        self.access_token = self._resolve_access_token()
        self.headers = self._build_headers(self.access_token)
        self.base_url = f"https://{self.nation_slug}.nationbuilder.com/api/v1"

    def _log_response(self, method_name, response):
        """
        Log API response with appropriate detail based on status code.

        Args:
            method_name: Name of the calling method
            response: Response object from requests

        Returns:
            Formatted message string
        """
        message = f"{method_name}:{response.status_code}"
        if response.status_code >= 400:
            message += f" :: {response.reason} :: {response.text}"
        logger.debug(f"{message}")
        return message

    def _resolve_access_token(self):
        """Resolve an access token from the available auth source."""
        if self.token_provider is not None:
            return self.token_provider.get_access_token()
        if self.oauth is not None:
            return self.oauth.nb_jwt_token
        return None

    @staticmethod
    def _build_headers(access_token):
        """Build authorization headers for the given token."""
        if not access_token:
            return {}
        return {"Authorization": f"Bearer {access_token}"}

    def _update_headers(self):
        """
        Update the headers with the latest available token.
        This method should be called before each API request to ensure
        the token is current.
        """
        self.access_token = self._resolve_access_token()
        self.headers = self._build_headers(self.access_token)
        logger.debug("NationBuilder client auth headers refreshed")
