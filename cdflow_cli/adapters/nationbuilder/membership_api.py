# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import inspect
import json
import logging

import requests

from .client import NBClient

logger = logging.getLogger(__name__)


class NBMembership(NBClient):
    """Client for interacting with the NationBuilder Membership API."""

    def __init__(self, token_provider):
        """
        Initialize the Membership API client.

        Args:
            token_provider: Runtime-neutral token provider
        """
        super().__init__(token_provider=token_provider)
        self.base_url = f"{self.base_url}/people"

    def get_membershipinfo_by_signup_nationbuilder_id(self, signup_nationbuilder_id):
        url = f"{self.base_url}/{signup_nationbuilder_id}/memberships"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code == 200 and response.json()["results"]:
            return (
                [
                    (
                        membership["name"],
                        membership["status"],
                        membership["started_at"],
                        membership["expires_on"],
                    )
                    for membership in response.json()["results"]
                ],
                True,
                message,
            )
        return None, False, message

    def set_active_monthly_membership(self, person_id):
        url = f"{self.base_url}"
        self._update_headers()
        json_payload = {"membership": {"person_id": person_id, "status": "active", "payment_plan_id": 1}}

        response = requests.post(url=url, headers=self.headers, json=json_payload, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code == 200:
            return response.json()["membership"]["id"], True, message
        return None, False, message

    def get_membershipid_by_params(self, param_value_pairs, check_number):
        param_value_pairs_str = "&".join(
            [f"{param_name}={param_value}" for param_name, param_value in param_value_pairs.items()]
        )
        url = f"{self.base_url}/search?{param_value_pairs_str}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code == 200:
            memberships = json.loads(response.content)
            for membership in memberships["results"]:
                if membership["check_number"] == check_number:
                    membership_id = membership["id"]
                    logger.debug(f"{message} :: {membership_id}")
                    return membership_id, True, message

        logger.debug(f"{message} :: None.")
        return None, False, message

    def create_membership(self, membership_data):
        url = f"{self.base_url}"
        self._update_headers()
        json_payload = {"membership": membership_data}

        response = requests.post(url=url, headers=self.headers, json=json_payload, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code == 200:
            return response.json()["membership"]["id"], True, message
        return None, False, message
