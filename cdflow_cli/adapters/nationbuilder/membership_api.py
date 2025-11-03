# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import requests
import inspect
import json
import logging

from .oauth import NationBuilderOAuth
from .client import NBClient

logger = logging.getLogger(__name__)


class NBMembership(NBClient):
    """Client for interacting with the NationBuilder Membership API."""

    def __init__(self, oauth: NationBuilderOAuth):
        """
        Initialize the Membership API client.

        Args:
            oauth: NationBuilderOAuth instance with valid credentials
        """
        super().__init__(oauth)
        self.base_url = f"{self.base_url}/people"

    # Check if a membership exists by checking signup_nationbuilder_id
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_membershipinfo_by_signup_nationbuilder_id(self, signup_nationbuilder_id):

        url = f"{self.base_url}/{signup_nationbuilder_id}/memberships"
        self._update_headers()  # Make sure we have the latest token

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return membership_id and response_success_get_membershipid_by_signup_nationbuilder_id
        if response.status_code == 200:
            if response.json()["results"]:
                # return list of membership names, True, message
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
                # return response.json()['results'][0]['name'], True, message
        return None, False, message

    # override membership and set to active monthly membership given a person_id
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def set_active_monthly_membership(self, person_id):

        url = f"{self.base_url}"
        self._update_headers()  # Make sure we have the latest token
        json = {"membership": {"person_id": person_id, "status": "active", "payment_plan_id": 1}}

        response = requests.post(url=url, headers=self.headers, json=json)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return membership_id and response_success_set_active_monthly_membership
        if response.status_code == 200:
            return response.json()["membership"]["id"], True, message
        return None, False, message

    # Check if a membership exists by checking succeeded_at date and check_number field
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_membershipid_by_params(self, param_value_pairs, check_number):

        param_value_pairs_str = "&".join(
            [f"{param_name}={param_value}" for param_name, param_value in param_value_pairs.items()]
        )
        url = f"{self.base_url}/search?{param_value_pairs_str}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # Check if the request was successful
        # May return multiple matches based on succeeded_at, so loop through memberships and check if check_number matches
        # return membership_id and response_success_get_membershipid_by_params
        if response.status_code == 200:
            memberships = json.loads(response.content)
            # print(json.dumps(memberships, indent=4, sort_keys=True))

            # Find the membership id by check number
            membership_id = None
            for membership in memberships["results"]:
                if membership["check_number"] == check_number:
                    membership_id = membership["id"]
                    logger.debug(f"{message} :: {membership_id}")
                    return membership_id, True, message

        # Return None if no matching membership is found or if the request failed
        logger.debug(f"{message} :: None.")
        return None, False, message

    # Create a membership in NationBuilder
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def create_membership(self, membership_data):

        url = f"{self.base_url}"
        self._update_headers()  # Make sure we have the latest token
        json = {"membership": membership_data}

        response = requests.post(url=url, headers=self.headers, json=json)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return membership_id and response_sccess_get_person_id_by_email
        if response.status_code == 200:
            return response.json()["membership"]["id"], True, message
        return None, False, message
