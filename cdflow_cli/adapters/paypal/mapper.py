# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Mapper for PayPal donation data.
"""

import logging

from ...models.donation import DonationMapper

logger = logging.getLogger(__name__)


class PPDonationMapper(DonationMapper):
    """
    Maps PayPal CSV fields to NationBuilder donation fields.
    """

    @classmethod
    def validate_row(cls, row):
        """
        Validate that a row has all required fields for PayPal data.

        Args:
            row (dict): Raw donation data from the source

        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = [
            "Name",
            "From Email Address",
            "Gross",
            "Date",
            "Time",
            "Transaction ID"
        ]

        missing_fields = [field for field in required_fields if field not in row]
        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"

        # Either Name or Email must have a value
        if not row.get("Name") and not row.get("From Email Address"):
            return False, "Either Name or Email must have a value"

        return True, None

    def __init__(self, data, job_context=None, custom_fields_available=None):
        """
        Initialize a PayPal donation data processor.

        Args:
            data (dict): Raw data from PayPal CSV
            job_context (dict, optional): Job context containing job_id and machine_info for tracking
            custom_fields_available (dict, optional): Dict indicating which custom fields exist in NB
        """
        super().__init__(data, job_context=job_context, custom_fields_available=custom_fields_available)

        # Map the data to the NationBuilder fields with rules and conversions
        # Use map_field() to respect plugin priority (Option B architecture)
        # Name parsing - only if plugin didn't set these fields
        if self.NBfirst_name is None and self.NBlast_name is None:
            name_value = self.get_value_case_insensitive("Name")
            if name_value and len(name_value) > 0:
                name_parts = name_value.split()
                self.NBfirst_name = name_parts[0]
                self.NBlast_name = name_parts[-1] if len(name_parts) > 1 else ""
                self.NBmiddle_name = " ".join(name_parts[1:-1]) if len(name_parts) > 2 else ""
            else:
                self.NBfirst_name = ""
                self.NBlast_name = ""
                self.NBmiddle_name = ""

        self.map_field("NBemail", "From Email Address")
        self.map_field("NBphone", "Contact Phone Number")

        gross_value = self.get_value_case_insensitive("Gross")
        if gross_value:
            self.NBamount_in_cents = int(float(str(gross_value).replace(",", "")) * 100)
        else:
            self.NBamount_in_cents = 0

        self.NBsucceeded_at = super().convert_date_time(
            date_field="Date",
            time_field="Time",
            date_format="%d/%m/%Y %H:%M:%S",
            tz_field="TimeZone",
            id_field="Transaction ID"
        )

        self.map_field("NBbilling_address_address1", "Address Line 1")
        self.map_field("NBbilling_address_address2", "Address Line 2/District/Neighborhood")
        self.map_field("NBbilling_address_city", "Town/City")
        self.map_field("NBbilling_address_state", "State/Province/Region/County/Territory/Prefecture/Republic")
        self.map_field("NBbilling_address_zip", "Zip/Postal Code")
        self.map_field("NBbilling_address_country", "Country")


