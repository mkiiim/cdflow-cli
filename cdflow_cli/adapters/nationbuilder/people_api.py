# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import inspect
import logging

import requests

from .client import NBClient, encode_uri

logger = logging.getLogger(__name__)


class NBPeople(NBClient):
    """Client for interacting with the NationBuilder People API."""

    def __init__(self, oauth=None, token_provider=None):
        """
        Initialize the People API client.

        Args:
            oauth: Legacy NationBuilderOAuth instance with valid credentials
            token_provider: New runtime-neutral token provider
        """
        # Transitional compatibility seam.
        # Remove oauth= support after callers are migrated to token_provider.
        super().__init__(oauth=oauth, token_provider=token_provider)
        self.base_url = f"{self.base_url}/people"

    def get_personid_by_email(self, email):
        url = f"{self.base_url}/match?email={encode_uri(email)}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code == 200:
                data = response.json()
                if data and data.get("person", {}).get("id"):
                    return data["person"]["id"], True, message
                return None, False, "Person not found"
            return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    def get_personid_by_phone(self, phone):
        url = f"{self.base_url}/match?phone={phone}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code == 200:
                data = response.json()
                if data and data.get("person", {}).get("id"):
                    return data["person"]["id"], True, message
                return None, False, "Person not found"
            return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    def get_persons_by_params(self, param_value_pairs, return_field):
        param_value_pairs_str = "&".join(
            [f"{param_name}={param_value}" for param_name, param_value in param_value_pairs.items()]
        )
        url = f"{self.base_url}/search?{param_value_pairs_str}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                return results, True, message
            return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    def get_personid_by_extid(self, ext_id):
        url = f"{self.base_url}/search?external_id={ext_id}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                if not results:
                    message += " :: No records found."
                    logger.debug(f"{message}")
                    return None, None, False, message

                if len(results) > 1:
                    message += " :: Multiple records found."
                    logger.debug(f"{message}")
                    return None, None, False, message

                person = results[0]
                person_id = person.get("id")
                email = person.get("email")
                message += f" :: {person_id}"
                logger.debug(f"{message}")
                return person_id, email, True, message
            return None, None, False, message
        except (ValueError, KeyError) as e:
            return None, None, False, f"JSON parsing error: {str(e)}"

    def get_person_by_id(self, person_id):
        url = f"{self.base_url}/{person_id}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code == 200:
                data = response.json()
                person_data = data.get("person", {})
                first_name = person_data.get("first_name")
                last_name = person_data.get("last_name")
                email = person_data.get("email")
                return first_name, last_name, email, True, message
            return None, None, None, False, message
        except (ValueError, KeyError) as e:
            return None, None, None, False, f"JSON parsing error: {str(e)}"

    def create_person(self, person_data):
        url = f"{self.base_url}"
        self._update_headers()
        json = {"person": person_data}

        response = requests.post(url=url, headers=self.headers, json=json, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code in [200, 201]:
                data = response.json()
                person_id = data.get("person", {}).get("id")
                if person_id:
                    return person_id, True, message
                return None, False, "Missing person ID in response"
            return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    def update_person(self, person_id, person_data):
        url = f"{self.base_url}/{person_id}"
        self._update_headers()
        json = {"person": person_data}

        response = requests.put(url=url, headers=self.headers, json=json, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code in [200, 201]:
                data = response.json()
                person_id = data.get("person", {}).get("id")
                if person_id:
                    return person_id, True, message
                return None, False, "Missing person ID in response"
            return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    def delete_person(self, person_id):
        url = f"{self.base_url}/{person_id}"
        self._update_headers()

        response = requests.delete(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code in [200, 204]:
                return True, message
            return False, message
        except Exception as e:
            return False, f"Response handling error: {str(e)}"
