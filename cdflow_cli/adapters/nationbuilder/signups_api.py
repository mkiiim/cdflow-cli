# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import inspect
import logging

import requests

from .client import NBClient, encode_uri

logger = logging.getLogger(__name__)


class NBSignups(NBClient):
    """Client for interacting with the NationBuilder Signups API (v2 replacement for People API)."""

    def __init__(self, oauth=None, token_provider=None, api_version="v2"):
        """
        Initialize the Signups API client.

        Args:
            oauth: Legacy NationBuilderOAuth instance with valid credentials
            token_provider: New runtime-neutral token provider
            api_version: API version retained for constructor compatibility
        """
        # Transitional compatibility seam.
        # Remove oauth= support after callers are migrated to token_provider.
        # api_version retained for compatibility with existing constructor signature.
        super().__init__(oauth=oauth, token_provider=token_provider)
        self.base_url = f"{self.base_url}/signups"

    def get_personid_by_email(self, email):
        url = f"{self.base_url}?filter[with_email_address]=eq:{encode_uri(email)}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code == 200:
            data = response.json()
            signups = data.get("data", [])
            if signups:
                person_id = signups[0]["id"]
                logger.debug(f"{message} :: {person_id}")
                return person_id, True, message

        logger.debug(f"{message} :: None.")
        return None, False, message

    def get_personid_by_phone(self, phone):
        logger.debug("v2 signups API: No phone number filter available")
        return None, False, "v2 signups API: No phone number filter available"

    def get_person_by_id(self, person_id):
        url = f"{self.base_url}/{person_id}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code == 200:
            data = response.json()
            person_data = data.get("data", {}).get("attributes", {})
            logger.debug(f"{message} :: Found signup")
            return person_data, True, message

        logger.debug(f"{message} :: None.")
        return None, False, message

    def create_person(self, person_data):
        url = f"{self.base_url}/push"
        self._update_headers()

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

        attributes = {k: v for k, v in attributes.items() if v is not None and v != ""}
        signup_data = {"data": {"type": "signups", "attributes": attributes}}

        logger.info(f"DEBUG - v2 API POST URL: {url}")
        logger.info(f"DEBUG - v2 API POST headers: {self.headers}")
        logger.info(f"DEBUG - v2 API POST signup data: {signup_data}")

        response = requests.post(url=url, headers=self.headers, json=signup_data, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

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

    def update_person(self, person_id, person_data):
        url = f"{self.base_url}/{person_id}"
        self._update_headers()

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
                    "home_address_attributes": (
                        person_data.get("billing_address", {})
                        if person_data.get("billing_address")
                        else None
                    ),
                },
            }
        }

        if signup_data["data"]["attributes"]["home_address_attributes"] is None:
            del signup_data["data"]["attributes"]["home_address_attributes"]

        response = requests.put(url=url, headers=self.headers, json=signup_data, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        if response.status_code in [200, 201]:
            logger.debug(f"{message} :: Updated signup ID: {person_id}")
            return person_id, True, message

        logger.debug(f"{message} :: Failed to update signup")
        return None, False, message

    def get_persons_by_params(self, param_value_pairs, return_field):
        logger.debug("v2 signups API: get_persons_by_params not implemented")
        return None, False, "v2 signups API: get_persons_by_params not implemented"

    def get_personid_by_extid(self, ext_id):
        logger.debug("v2 signups API: get_personid_by_extid not implemented")
        return None, False, "v2 signups API: get_personid_by_extid not implemented"
