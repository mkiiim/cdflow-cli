# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Mapper for CanadaHelps donation data.
"""

import langcodes
import logging

from ...models.donation import DonationMapper

logger = logging.getLogger(__name__)


class CHDonationMapper(DonationMapper):
    """
    Maps CanadaHelps CSV fields to NationBuilder donation fields.
    """

    @classmethod
    def validate_row(cls, row):
        """
        Validate that a row has all required fields for CanadaHelps data.

        Args:
            row (dict): Raw donation data from the source

        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = [
            "DONOR FIRST NAME",
            "DONOR LAST NAME",
            "DONOR EMAIL ADDRESS",
            "AMOUNT",
            "DONATION DATE",
            "DONATION TIME",
            "TRANSACTION NUMBER",
        ]

        missing_fields = [field for field in required_fields if field not in row]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"

        # Check for empty values in critical fields
        empty_fields = [field for field in required_fields if field in row and not row[field]]
        if empty_fields:
            logger.warning(f"Empty values in fields: {', '.join(empty_fields)}")
            # We'll allow this but log a warning

        return True, None

    def __init__(
        self,
        data,
        job_context=None,
        custom_fields_available=None,
    ):
        """
        Initialize a CanadaHelps donation data processor.

        Args:
            data (dict): Raw data from CanadaHelps CSV
            job_context (dict, optional): Job context containing job_id and machine_info for tracking
            custom_fields_available (dict, optional): Dict indicating which custom fields exist in NB
        """
        super().__init__(data, job_context=job_context, custom_fields_available=custom_fields_available)

        # Map the data to the NationBuilder fields with rules and conversions
        # Use map_field() to respect plugin priority (Option B architecture)
        self.map_field("NBfirst_name", "DONOR FIRST NAME")
        self.map_field("NBlast_name", "DONOR LAST NAME")
        self.map_field("NBmiddle_name", "")
        self.map_field("NBemail", "DONOR EMAIL ADDRESS")
        self.map_field("NBemail_opt_in", "DONOR EMAIL OPT IN")
        self.map_field("NBemployer", "DONOR COMPANY NAME")
        self.map_field("NBphone", "DONOR PHONE NUMBER")
        self.map_field("NBbilling_address_address1", "DONOR ADDRESS 1")
        self.map_field("NBbilling_address_address2", "DONOR ADDRESS 2")
        self.map_field("NBbilling_address_city", "DONOR CITY")
        self.map_field("NBbilling_address_state", "DONOR PROVINCE/STATE")

        # Postal code needs special handling for truncation
        if self.NBbilling_address_zip is None:
            zip_value = self.get_value_case_insensitive("DONOR POSTAL/ZIP CODE") or ""
            self.NBbilling_address_zip = zip_value.strip()[:10] if zip_value else ""

        self.map_field("NBbilling_address_country", "DONOR COUNTRY")

        self.NBsucceeded_at = super().convert_date_time(
            date_field="DONATION DATE",
            time_field="DONATION TIME",
            date_format="%Y-%m-%d %I:%M %p",
            id_field="TRANSACTION NUMBER"
        )

        amount_value = self.get_value_case_insensitive("AMOUNT")
        if amount_value:
            self.NBamount_in_cents = int(float(amount_value) * 100)
        else:
            self.NBamount_in_cents = 0


        # Alternative method for language code conversion
        try:
            donor_language = self.get_value_case_insensitive("DONOR LANGUAGE")
            self.NBlanguage = str(langcodes.find(donor_language)) if donor_language else ""
        except Exception:
            self.NBlanguage = ""


