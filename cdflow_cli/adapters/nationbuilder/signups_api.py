# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import requests
import inspect
import logging

from .oauth import NationBuilderOAuth
from .client import NBClient, encode_uri

logger = logging.getLogger(__name__)


class NBSignups(NBClient):
    """Client for interacting with the NationBuilder Signups API (v2 replacement for People API)."""

    def __init__(self, oauth: NationBuilderOAuth, api_version="v2"):
        """
        Initialize the Signups API client.

        Args:
            oauth: NationBuilderOAuth instance with valid credentials
            api_version: API version to use, defaults to 'v2' (signups only exist in v2)
        """
        super().__init__(oauth, api_version)
        self.base_url = f"{self.base_url}/signups"

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_personid_by_email(self, email):
        """
        Get signup ID by email address using v2 signups endpoint.

        Args:
            email: Email address to search for

        Returns:
            Tuple of (person_id, success, message)
        """
        # v2 signups API uses filter[with_email_address] with eq operator
        # The filter accepts operators: [eq, match, not_match, prefix, not_prefix, suffix, not_suffix]
        # Documentation is unclear on exact format - trying common patterns
        # Pattern 1: filter[with_email_address]=eq:{email}
        url = f"{self.base_url}?filter[with_email_address]=eq:{encode_uri(email)}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code == 200:
            data = response.json()
            signups = data.get("data", [])

            if signups:
                # Return the first matching signup ID
                person_id = signups[0]["id"]
                logger.debug(f"{message} :: {person_id}")
                return person_id, True, message

        logger.debug(f"{message} :: None.")
        return None, False, message

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_personid_by_phone(self, phone):
        """
        Get signup ID by phone number - v2 signups doesn't have phone filter, return None.

        Args:
            phone: Phone number to search for

        Returns:
            Tuple of (person_id, success, message)
        """
        # v2 signups API doesn't have phone number filtering capability shown in docs
        logger.debug("v2 signups API: No phone number filter available")
        return None, False, "v2 signups API: No phone number filter available"

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_person_by_id(self, person_id):
        """
        Get signup details by ID.

        Args:
            person_id: Signup ID to retrieve

        Returns:
            Tuple of (person_data, success, message)
        """
        url = f"{self.base_url}/{person_id}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code == 200:
            data = response.json()
            person_data = data.get("data", {}).get("attributes", {})
            logger.debug(f"{message} :: Found signup")
            return person_data, True, message

        logger.debug(f"{message} :: None.")
        return None, False, message

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def create_person(self, person_data):
        """
        Create or update a signup using v2 signups push API.
        This endpoint automatically handles find-or-create logic:
        - If signup exists (by email), updates it (200)
        - If signup doesn't exist, creates it (201)

        Args:
            person_data: Dictionary containing person data

        Returns:
            Tuple of (person_id, success, message)
        """
        url = f"{self.base_url}/push"
        self._update_headers()

        # Convert v1 person data format to v2 signups format
        attributes = {
            "email": person_data.get("email"),
            "first_name": person_data.get("first_name"),
            "middle_name": person_data.get("middle_name"),
            "last_name": person_data.get("last_name"),
            "employer": person_data.get("employer"),
            "phone_number": person_data.get("phone"),
            "email_opt_in": (
                person_data.get("email_opt_in", True)
                if person_data.get("email_opt_in") is not None
                else True
            ),
            "language": person_data.get("language") or "EN",
        }

        # Add billing address if present - v2 uses billing_address_attributes
        billing_address = person_data.get("billing_address")
        if billing_address and any(billing_address.values()):
            attributes["billing_address_attributes"] = {
                "address1": billing_address.get("address1"),
                "address2": billing_address.get("address2"),
                "city": billing_address.get("city"),
                "state": billing_address.get("state"),
                "zip": billing_address.get("zip"),
                "country_code": billing_address.get("country_code"),
            }

        # Remove None/empty values to clean up the payload
        attributes = {k: v for k, v in attributes.items() if v is not None and v != ""}

        signup_data = {"data": {"type": "signups", "attributes": attributes}}

        # Debug logging: show exactly what's being sent to v2 API
        logger.info(f"DEBUG - v2 API POST URL: {url}")
        logger.info(f"DEBUG - v2 API POST headers: {self.headers}")
        logger.info(f"DEBUG - v2 API POST signup data: {signup_data}")

        response = requests.post(url=url, headers=self.headers, json=signup_data)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # Debug logging: show response details
        logger.info(f"DEBUG - v2 API response status: {response.status_code}")
        if response.status_code >= 400:
            logger.info(f"DEBUG - v2 API response body: {response.text}")

        if response.status_code in [200, 201]:
            data = response.json()
            person_id = data.get("data", {}).get("id")
            logger.debug(f"{message} :: Created signup ID: {person_id}")
            return person_id, True, message

        logger.debug(f"{message} :: Failed to create signup")
        return None, False, message

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def update_person(self, person_id, person_data):
        """
        Update an existing signup using v2 signups API.

        Args:
            person_id: ID of the signup to update
            person_data: Dictionary containing updated person data

        Returns:
            Tuple of (person_id, success, message)
        """
        url = f"{self.base_url}/{person_id}"
        self._update_headers()

        # Convert v1 person data format to v2 signups format
        signup_data = {
            "data": {
                "type": "signups",
                "attributes": {
                    "email": person_data.get("email"),
                    "first_name": person_data.get("first_name"),
                    "middle_name": person_data.get("middle_name"),
                    "last_name": person_data.get("last_name"),
                    "employer": person_data.get("employer"),
                    "phone_number": person_data.get("phone"),
                    "email_opt_in": person_data.get("email_opt_in", True),
                    "language": person_data.get("language", "EN"),
                    # Add billing address if present
                    "home_address_attributes": (
                        person_data.get("billing_address", {})
                        if person_data.get("billing_address")
                        else None
                    ),
                },
            }
        }

        # Remove None values to clean up the payload
        if signup_data["data"]["attributes"]["home_address_attributes"] is None:
            del signup_data["data"]["attributes"]["home_address_attributes"]

        response = requests.put(url=url, headers=self.headers, json=signup_data)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code in [200, 201]:
            logger.debug(f"{message} :: Updated signup ID: {person_id}")
            return person_id, True, message

        logger.debug(f"{message} :: Failed to update signup")
        return None, False, message

    # Placeholder methods to maintain compatibility with v1 people API
    def get_persons_by_params(self, param_value_pairs, return_field):
        """Not implemented for v2 signups API"""
        logger.debug("v2 signups API: get_persons_by_params not implemented")
        return None, False, "v2 signups API: get_persons_by_params not implemented"

    def get_personid_by_extid(self, ext_id):
        """Not implemented for v2 signups API"""
        logger.debug("v2 signups API: get_personid_by_extid not implemented")
        return None, False, "v2 signups API: get_personid_by_extid not implemented"
