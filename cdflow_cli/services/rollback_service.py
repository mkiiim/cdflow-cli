# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Donation rollback service for removing donations from NationBuilder.

This service handles the business logic for deleting donations and associated
people records that were previously imported through the donation import process.
"""

import json
import logging
from typing import Dict, Any, Tuple

from ..adapters.nationbuilder import NationBuilderOAuth, NBPeople, NBDonation
from ..adapters.canadahelps import CHDonationMapper
from ..adapters.paypal import PPDonationMapper
from ..utils.config import ConfigProvider
from ..utils.logging import LoggingProvider

logger = logging.getLogger(__name__)


class DonationRollbackService:
    """Service for rolling back (deleting) previously imported donations."""

    def __init__(self, config_provider: ConfigProvider, logging_provider: LoggingProvider):
        """
        Initialize the rollback service.

        Args:
            config_provider: Configuration provider
            logging_provider: Logging provider
        """
        self.config_provider = config_provider
        self.logging_provider = logging_provider
        self.logger = logging_provider.get_logger(__name__)

        # API client instances (initialized later)
        self.nboauth = None
        self.people = None
        self.donation = None
        self.nation_slug = None

    def initialize_api_clients(self) -> bool:
        """
        Initialize NationBuilder API clients.

        Returns:
            bool: True if initialization successful, False otherwise
        """
        try:
            # Get OAuth configuration from environment variables
            oauth_config = self.config_provider.get_oauth_config()

            if not oauth_config:
                self.logger.error("OAuth configuration not found in environment variables")
                return False

            # Ensure redirect_uri and callback_port are present for CLI context
            deployment_hostname = self.config_provider.get_app_setting(
                ["deployment", "hostname"], "localhost"
            )
            deployment_api_port = self.config_provider.get_app_setting(
                ["deployment", "api_port"], 8000
            )

            cli_redirect_uri = f"http://{deployment_hostname}:{deployment_api_port}/callback"

            if "redirect_uri" not in oauth_config:
                oauth_config["redirect_uri"] = cli_redirect_uri
                self.logger.debug(f"Added default redirect_uri for CLI context: {cli_redirect_uri}")
            if "callback_port" not in oauth_config:
                oauth_config["callback_port"] = deployment_api_port
                self.logger.debug(
                    f"Added default callback_port for CLI context: {deployment_api_port}"
                )

            # Create OAuth instance
            self.nboauth = NationBuilderOAuth(oauth_config, auto_initialize=False)

            # Initialize OAuth to get tokens
            self.logger.debug("Initializing OAuth token for rollback service")
            if not self.nboauth.initialize():
                self.logger.error("Failed to initialize OAuth token")
                return False

            # Create API client instances
            self.people = NBPeople(self.nboauth)
            self.donation = NBDonation(self.nboauth)

            # Store nation slug for display
            self.nation_slug = self.nboauth.slug
            self.logger.debug(f"API clients initialized successfully. Nation: {self.nation_slug}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize API clients: {str(e)}", exc_info=True)
            return False

    def process_rollback_row(self, row: Dict[str, Any], import_type: str) -> Tuple[bool, str]:
        """
        Process a single row for rollback (deletion).

        Args:
            row: CSV row data
            import_type: Import type ('CanadaHelps' or 'PayPal')

        Returns:
            Tuple of (success, message)
        """
        try:
            # Create donation mapper object for logging (no job context needed for rollback)
            donation_data_row = (
                CHDonationMapper(row) if import_type == "CanadaHelps" else PPDonationMapper(row)
            )
            donation_data = json.loads(donation_data_row.to_json_donation_data())

            # Log the donation being processed (matching donationflow style)
            donation_amount = donation_data.get("amount_in_cents", 0) / 100
            self.logger.info(
                f"🗑️  CLEANUP: {donation_data.get('check_number', 'N/A')} | ${donation_amount:.2f} | {donation_data.get('email', 'N/A')}"
            )

            row_message = ""

            # Check if we have a donation ID to delete
            donation_id = row.get("NB Donation ID")
            if not donation_id:
                message = f"WARNING: No donation ID found for {donation_data.get('check_number')}. Skipping."
                self.logger.warning(message)
                return False, message

            # Delete the donation
            _, success_delete_donation, message = self.donation.delete_donation(donation_id)

            if not success_delete_donation:
                error_msg = f"FAILURE delete_donation :: {donation_id} :: {message}"
                self.logger.error(error_msg)
                return False, error_msg

            self.logger.info(f"✅ SUCCESS delete_donation :: {donation_id}")
            row_message = f"SUCCESS delete_donation :: {donation_id}"

            # Check if we need to delete associated people record
            people_create_date = row.get("NB People Create Date")
            people_id = row.get("NB People ID")

            if people_create_date and people_id:
                self.logger.info(
                    f"👤 Donation triggered creation of People record with ID {people_id} on: {people_create_date}"
                )

                # Delete the people record
                success_delete_person, delete_message = self.people.delete_person(people_id)

                if not success_delete_person:
                    error_msg = f"FAILURE delete_person :: {people_id} :: {delete_message}"
                    self.logger.error(error_msg)
                    row_message += f" :: {error_msg}"
                    return False, row_message

                self.logger.info(f"✅ SUCCESS delete_person :: {people_id}")
                row_message += f" :: SUCCESS delete_person :: {people_id}"
            else:
                self.logger.info("ℹ️  No associated People record creation found")

            return True, row_message

        except Exception as e:
            error_msg = f"ERROR processing row: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg
