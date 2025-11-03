# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import requests
import inspect
import logging

from .oauth import NationBuilderOAuth
from .client import NBClient, encode_uri

logger = logging.getLogger(__name__)


class NBPeople(NBClient):
    """Client for interacting with the NationBuilder People API."""

    def __init__(self, oauth: NationBuilderOAuth):
        """
        Initialize the People API client.

        Args:
            oauth: NationBuilderOAuth instance with valid credentials
        """
        super().__init__(oauth)
        self.base_url = f"{self.base_url}/people"

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_personid_by_email(self, email):

        url = f"{self.base_url}/match?email={encode_uri(email)}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return person_id and response_success_get_person
        try:
            if response.status_code == 200:
                data = response.json()
                if data and data.get("person", {}).get("id"):
                    return data["person"]["id"], True, message
                else:
                    return None, False, "Person not found"
            else:
                return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_personid_by_phone(self, phone):

        url = f"{self.base_url}/match?phone={phone}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return person_id and response_success_get_person
        try:
            if response.status_code == 200:
                data = response.json()
                if data and data.get("person", {}).get("id"):
                    return data["person"]["id"], True, message
                else:
                    return None, False, "Person not found"
            else:
                return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_persons_by_params(self, param_value_pairs, return_field):

        param_value_pairs_str = "&".join(
            [f"{param_name}={param_value}" for param_name, param_value in param_value_pairs.items()]
        )
        url = f"{self.base_url}/search?{param_value_pairs_str}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return person_id and response_success_get_person
        try:
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                return results, True, message
            else:
                return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_personid_by_extid(self, ext_id):

        url = f"{self.base_url}/search?external_id={ext_id}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])

                # if no records are returned, return None
                if not results:
                    message += " :: No records found."
                    logger.debug(f"{message}")
                    return None, None, False, message

                # should only be one record else error
                if len(results) > 1:
                    message += " :: Multiple records found."
                    logger.debug(f"{message}")
                    return None, None, False, message

                # return person_id and response_success_get_person
                person = results[0]
                person_id = person.get("id")
                email = person.get("email")
                message += f" :: {person_id}"
                logger.debug(f"{message}")
                return person_id, email, True, message
            else:
                return None, None, False, message
        except (ValueError, KeyError) as e:
            return None, None, False, f"JSON parsing error: {str(e)}"

    # Get a person by ID
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_person_by_id(self, person_id):
        """
        Get a person's first name, last name, and email by their ID.

        Args:
            person_id: The ID of the person to retrieve

        Returns:
            tuple: (first_name, last_name, email, success_bool, message)
                If successful, returns the person's first name, last name, email, True, and a log message
                If unsuccessful, returns None, None, None, False, and a log message
        """
        url = f"{self.base_url}/{person_id}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code == 200:
                data = response.json()
                person_data = data.get("person", {})
                first_name = person_data.get("first_name")
                last_name = person_data.get("last_name")
                email = person_data.get("email")
                return first_name, last_name, email, True, message
            else:
                return None, None, None, False, message
        except (ValueError, KeyError) as e:
            return None, None, None, False, f"JSON parsing error: {str(e)}"

    # Create a person
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def create_person(self, person_data):

        url = f"{self.base_url}"
        self._update_headers()  # Make sure we have the latest token
        json = {"person": person_data}

        response = requests.post(url=url, headers=self.headers, json=json)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return person_id and response_success_get_person
        try:
            if response.status_code in [200, 201]:  # Accept creation codes
                data = response.json()
                person_id = data.get("person", {}).get("id")
                if person_id:
                    return person_id, True, message
                else:
                    return None, False, "Missing person ID in response"
            else:
                return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    # Update a person
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def update_person(self, person_id, person_data):

        url = f"{self.base_url}/{person_id}"
        self._update_headers()  # Make sure we have the latest token
        json = {"person": person_data}

        response = requests.put(url=url, headers=self.headers, json=json)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return person_id and response_success_update_person
        try:
            if response.status_code in [200, 201]:  # Accept update codes
                data = response.json()
                person_id = data.get("person", {}).get("id")
                if person_id:
                    return person_id, True, message
                else:
                    return None, False, "Missing person ID in response"
            else:
                return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    # Delete a person
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def delete_person(self, person_id):

        url = f"{self.base_url}/{person_id}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.delete(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return person_id and response_success_delete_person
        try:
            if response.status_code in [200, 204]:  # Accept success/no-content codes
                return True, message
            else:
                return False, message
        except Exception as e:
            return False, f"Response handling error: {str(e)}"
