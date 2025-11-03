# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import requests
import logging

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

    def __init__(self, oauth):
        """
        Initialize the client with NationBuilder OAuth credentials.

        Args:
            oauth: NationBuilderOAuth instance with valid credentials
        """
        self.oauth = oauth
        # Get token from instance variable
        self.access_token = oauth.nb_jwt_token
        self.nation_slug = oauth.slug
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
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

    def _update_headers(self):
        """
        Update the headers with the latest token from OAuth instance.
        This method should be called before each API request to ensure
        the token is current.
        """
        # Debug logging: show header update details
        old_token_suffix = self.access_token[-5:] if self.access_token else "None"
        new_token_suffix = self.oauth.nb_jwt_token[-5:] if self.oauth.nb_jwt_token else "None"

        if old_token_suffix != new_token_suffix:
            logger.info(
                f"DEBUG - Headers updated: token changed from ...{old_token_suffix} to ...{new_token_suffix}"
            )
        else:
            logger.debug(f"DEBUG - Headers updated: same token ...{new_token_suffix}")

        # Get token from instance variable
        self.access_token = self.oauth.nb_jwt_token
        self.headers = {"Authorization": f"Bearer {self.access_token}"}
