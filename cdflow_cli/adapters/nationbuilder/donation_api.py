# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import inspect
import logging

import requests

from .client import NBClient

logger = logging.getLogger(__name__)


class NBDonation(NBClient):
    """Client for interacting with the NationBuilder Donation API."""

    def __init__(self, token_provider):
        """
        Initialize the Donation API client.

        Args:
            token_provider: Runtime-neutral token provider
        """
        super().__init__(token_provider=token_provider)
        self.base_url = f"{self.base_url}/donations"

    def get_donationid_by_params(self, param_value_pairs, check_number):
        param_value_pairs_str = "&".join(
            [f"{param_name}={param_value}" for param_name, param_value in param_value_pairs.items()]
        )
        url = f"{self.base_url}/search?{param_value_pairs_str}"
        self._update_headers()

        response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code == 200:
                donations = response.json()
                for donation in donations.get("results", []):
                    if donation.get("check_number") == check_number:
                        donation_id = donation.get("id")
                        logger.debug(f"{message} :: {donation_id}")
                        return donation_id, True, message

            logger.debug(f"{message} :: None.")
            return None, False, message
        except (ValueError, KeyError) as e:
            logger.debug(f"{message} :: JSON parsing error: {str(e)}")
            return None, False, f"JSON parsing error: {str(e)}"

    def create_donation(self, donation_data):
        url = f"{self.base_url}"
        self._update_headers()
        payload = {"donation": donation_data}

        response = requests.post(url=url, headers=self.headers, json=payload, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code in [200, 201]:
                response_data = response.json()
                donation_id = response_data.get("donation", {}).get("id")
                if donation_id:
                    return donation_id, True, message
                return None, False, "Missing donation ID in response"
            return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    def detect_custom_donation_fields(self, fields_to_check=None):
        if fields_to_check is None:
            fields_to_check = ["import_job_id", "import_job_source"]

        url = f"{self.base_url}?limit=1"
        self._update_headers()

        try:
            response = requests.get(url=url, headers=self.headers, timeout=self.request_timeout)
            message = self._log_response(inspect.currentframe().f_code.co_name, response)

            if response.status_code == 200:
                data = response.json()
                donations = data.get("results", [])

                if donations:
                    donation = donations[0]
                    field_status = {field: field in donation for field in fields_to_check}
                    logger.debug(f"Custom field detection: {field_status}")
                    return field_status

                logger.warning("No donations found for field detection - assuming fields don't exist")
                return {field: False for field in fields_to_check}

            logger.warning(f"Failed to detect custom fields: {message}")
            return {field: False for field in fields_to_check}

        except Exception as e:
            logger.warning(f"Error detecting custom donation fields: {str(e)}")
            return {field: False for field in fields_to_check}

    def delete_donation(self, donation_id):
        url = f"{self.base_url}/{donation_id}"
        self._update_headers()

        response = requests.delete(url=url, headers=self.headers, timeout=self.request_timeout)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        try:
            if response.status_code in [200, 204]:
                return donation_id, True, message
            return donation_id, False, message
        except Exception as e:
            return donation_id, False, f"Response handling error: {str(e)}"
