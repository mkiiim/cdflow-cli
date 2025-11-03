# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

import requests
import inspect
import json
import logging

from .oauth import NationBuilderOAuth
from .client import NBClient

logger = logging.getLogger(__name__)


class NBDonation(NBClient):
    """Client for interacting with the NationBuilder Donation API."""

    def __init__(self, oauth: NationBuilderOAuth):
        """
        Initialize the Donation API client.

        Args:
            oauth: NationBuilderOAuth instance with valid credentials
        """
        super().__init__(oauth)
        self.base_url = f"{self.base_url}/donations"

    # Check if a donation exists by checking succeeded_at date and check_number field
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def get_donationid_by_params(self, param_value_pairs, check_number):

        param_value_pairs_str = "&".join(
            [f"{param_name}={param_value}" for param_name, param_value in param_value_pairs.items()]
        )
        url = f"{self.base_url}/search?{param_value_pairs_str}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.get(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # Check if the request was successful
        # May return multiple matches based on succeeded_at, so loop through donations and check if check_number matches
        # return donation_id and response_success_get_donationid_by_params
        try:
            if response.status_code == 200:
                donations = response.json()
                # print(json.dumps(donations, indent=4, sort_keys=True))

                # Find the donation id by check number
                donation_id = None
                for donation in donations.get("results", []):
                    if donation.get("check_number") == check_number:
                        donation_id = donation.get("id")
                        logger.debug(f"{message} :: {donation_id}")
                        return donation_id, True, message

            # Return None if no matching donation is found or if the request failed
            logger.debug(f"{message} :: None.")
            return None, False, message
        except (ValueError, KeyError) as e:
            logger.debug(f"{message} :: JSON parsing error: {str(e)}")
            return None, False, f"JSON parsing error: {str(e)}"

    # Create a donation in NationBuilder
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def create_donation(self, donation_data):

        url = f"{self.base_url}"
        self._update_headers()  # Make sure we have the latest token
        payload = {"donation": donation_data}

        # Debug logging: show exactly what's being sent to NationBuilder
        import logging

        logger = logging.getLogger(__name__)

        response = requests.post(url=url, headers=self.headers, json=payload)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return donation_id, success_boolean, message
        try:
            if response.status_code in [200, 201]:  # Accept creation codes
                response_data = response.json()
                donation_id = response_data.get("donation", {}).get("id")
                if donation_id:
                    return donation_id, True, message
                else:
                    return None, False, "Missing donation ID in response"
            else:
                return None, False, message
        except (ValueError, KeyError) as e:
            return None, False, f"JSON parsing error: {str(e)}"

    # Detect if custom donation tracking fields exist in the nation
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def detect_custom_donation_fields(self, fields_to_check=None):
        """
        Detect if custom donation fields exist by examining a recent donation.
        
        Args:
            fields_to_check (list): List of field names to check for. 
                                  Defaults to ['import_job_id', 'import_job_source']
        
        Returns:
            dict: {field_name: exists_boolean} mapping
        """
        if fields_to_check is None:
            fields_to_check = ['import_job_id', 'import_job_source']
            
        # Try to get a recent donation to examine its structure
        url = f"{self.base_url}?limit=1"
        self._update_headers()
        
        try:
            response = requests.get(url=url, headers=self.headers)
            message = self._log_response(inspect.currentframe().f_code.co_name, response)
            
            if response.status_code == 200:
                data = response.json()
                donations = data.get("results", [])
                
                if donations:
                    # Check first donation for custom fields
                    donation = donations[0]
                    field_status = {}
                    
                    for field in fields_to_check:
                        # Check if field exists (even if None/empty)
                        field_status[field] = field in donation
                        
                    logger.debug(f"Custom field detection: {field_status}")
                    return field_status
                else:
                    logger.warning("No donations found for field detection - assuming fields don't exist")
                    return {field: False for field in fields_to_check}
                    
            else:
                logger.warning(f"Failed to detect custom fields: {message}")
                return {field: False for field in fields_to_check}
                
        except Exception as e:
            logger.warning(f"Error detecting custom donation fields: {str(e)}")
            return {field: False for field in fields_to_check}

    # Delete a donation in NationBuilder
    @NationBuilderOAuth.ensure_valid_nb_jwt
    def delete_donation(self, donation_id):

        url = f"{self.base_url}/{donation_id}"
        self._update_headers()  # Make sure we have the latest token

        response = requests.delete(url=url, headers=self.headers)
        message = self._log_response(inspect.currentframe().f_code.co_name, response)

        # return response_success
        try:
            if response.status_code in [200, 204]:  # Accept success/no-content codes
                return donation_id, True, message
            else:
                return donation_id, False, message
        except Exception as e:
            return donation_id, False, f"Response handling error: {str(e)}"
