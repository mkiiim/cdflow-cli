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

    def __init__(self, token_provider, request_timeout=DEFAULT_TIMEOUT):
        """
        Initialize the client with NationBuilder auth credentials.

        Args:
            token_provider: Runtime-neutral token provider
            request_timeout: Shared request timeout for NationBuilder API calls
        """
        if token_provider is None:
            raise ValueError("NBClient requires token_provider")

        self.token_provider = token_provider
        self.request_timeout = request_timeout
        self.authorized_session = NationBuilderAuthorizedSession(token_provider)

        self.nation_slug = token_provider.token_client.oauth_config.slug

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
        return self.token_provider.get_access_token()

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
