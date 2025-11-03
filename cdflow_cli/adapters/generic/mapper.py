# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Parser for generic donation data.

This parser handles CSV files with minimal required fields, making it suitable
for importing from any source that provides basic donation information.

Required CSV columns:
- email: Donor email address
- amount: Donation amount in dollars (will be converted to cents)
- donation_date: Date of donation (YYYY-MM-DD format preferred)
- first_name: Donor first name
- last_name: Donor last name

Optional CSV columns:
- transaction_id: Unique transaction identifier (used as check_number)
- payment_method: Payment method (credit, paypal, bank_transfer, etc.)
- middle_name: Donor middle name
- phone: Donor phone number
- address1: Billing address line 1
- address2: Billing address line 2
- city: Billing city
- state: Billing state/province
- zip: Billing postal code
- country: Billing country
"""

from datetime import datetime
import pytz
import logging
from decimal import Decimal, InvalidOperation

from ...models.donation import DonationMapper

logger = logging.getLogger(__name__)


class GenericDonationMapper(DonationMapper):
    """
    Maps generic donation data with minimal required fields to NationBuilder format.
    """

    @classmethod
    def validate_row(cls, row):
        """
        Validate that a row has all required fields for generic donation data.

        Args:
            row (dict): Raw donation data from the source

        Returns:
            tuple: (is_valid, error_message)
        """
        required_fields = ["email", "amount", "donation_date", "first_name", "last_name"]

        return cls.validate_row_case_insensitive(row, required_fields)

    def __init__(self, data, job_context=None, custom_fields_available=None):
        """
        Initialize a GenericDonationData instance.

        Args:
            data (dict): Raw donation data from the source
            job_context (dict, optional): Job context containing job_id and machine_info for tracking
            custom_fields_available (dict, optional): Dict indicating which custom fields exist in NB
        """
        super().__init__(data, job_context=job_context, custom_fields_available=custom_fields_available)

        # Map basic fields
        self.NBfirst_name = self._clean_string(self.get_value("first_name"))
        self.NBlast_name = self._clean_string(self.get_value("last_name"))
        self.NBmiddle_name = self._clean_string(self.get_value("middle_name") or "")
        self.NBemail = self._clean_string(self.get_value("email"))
        self.NBphone = self._clean_string(self.get_value("phone") or "")

        # Map transaction identifier
        transaction_id = self.get_value("transaction_id")
        self.NBcheck_number = self._clean_string(
            transaction_id or f"GENERIC_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        # Map payment method
        payment_method = self.get_value("payment_method")
        self.NBpayment_type_name = self._map_payment_method(payment_method or "online")

        # Convert amount from dollars to cents
        amount_str = self.get_value("amount")
        self.NBamount_in_cents = self._convert_amount_to_cents(amount_str)

        # Parse donation date
        date_str = self.get_value("donation_date")
        self.NBsucceeded_at = self._parse_donation_date(date_str)

        # Map address fields
        self.NBbilling_address_address1 = self._clean_string(self.get_value("address1") or "")
        self.NBbilling_address_address2 = self._clean_string(self.get_value("address2") or "")
        self.NBbilling_address_city = self._clean_string(self.get_value("city") or "")
        self.NBbilling_address_state = self._clean_string(self.get_value("state") or "")
        self.NBbilling_address_zip = self._clean_string(self.get_value("zip") or "")
        self.NBbilling_address_country = self._clean_string(self.get_value("country") or "CA")

        # Default values
        self.NBemail_opt_in = False
        self.NBemployer = ""
        self.NBlanguage = "en"
        self.NBrecurring_donation_id = ""
        self.NBtracking_code_slug = "generic_import"

    def _clean_string(self, value):
        """Clean and validate string values."""
        if value is None:
            return ""
        return str(value).strip()

    def _map_payment_method(self, payment_method):
        """
        Map generic payment method to NationBuilder payment type.

        Args:
            payment_method: Payment method string

        Returns:
            str: Mapped payment type name
        """
        if not payment_method:
            return "Online"

        # Normalize to lowercase for comparison
        method = str(payment_method).lower().strip()

        # Payment method mapping
        payment_mapping = {
            "credit": "Credit Card",
            "credit_card": "Credit Card", 
            "creditcard": "Credit Card",
            "visa": "Credit Card",
            "mastercard": "Credit Card",
            "amex": "Credit Card",
            "discover": "Credit Card",
            "paypal": "PayPal",
            "bank": "Bank Transfer",
            "bank_transfer": "Bank Transfer",
            "wire": "Bank Transfer",
            "ach": "Bank Transfer",
            "check": "Check",
            "cheque": "Check",
            "cash": "Cash",
            "online": "Online",
            "web": "Online",
            "other": "Other"
        }

        return payment_mapping.get(method, "Online")

    def _convert_amount_to_cents(self, amount_str):
        """
        Convert amount from dollars to cents.

        Args:
            amount_str: Amount as string (e.g., "25.50", "$25.50", "25")

        Returns:
            int: Amount in cents
        """
        if not amount_str:
            logger.warning("Empty amount value, defaulting to 0")
            return 0

        try:
            # Remove common currency symbols and whitespace
            cleaned = str(amount_str).replace("$", "").replace(",", "").strip()

            # Convert to decimal for precision
            amount_decimal = Decimal(cleaned)

            # Convert to cents (multiply by 100)
            cents = int(amount_decimal * 100)

            return cents

        except (InvalidOperation, ValueError) as e:
            logger.error(f"Failed to convert amount '{amount_str}' to cents: {e}")
            return 0

    def _parse_donation_date(self, date_str):
        """
        Parse donation date from various formats.

        Args:
            date_str: Date string in various formats

        Returns:
            str: ISO format datetime string
        """
        if not date_str:
            logger.warning("Empty donation date, using current date")
            now = datetime.now()
            return now.isoformat()

        # Try common date formats
        date_formats = [
            "%Y-%m-%d",  # 2023-12-25
            "%Y/%m/%d",  # 2023/12/25
            "%m/%d/%Y",  # 12/25/2023
            "%d/%m/%Y",  # 25/12/2023
            "%Y-%m-%d %H:%M:%S",  # 2023-12-25 14:30:00
            "%m/%d/%Y %H:%M:%S",  # 12/25/2023 14:30:00
        ]

        for fmt in date_formats:
            try:
                # Use base class timezone-aware parser
                return self._parse_datetime(str(date_str).strip(), fmt)
            except ValueError:
                continue

        # If no format worked, log warning and use current date
        logger.warning(f"Could not parse donation date '{date_str}', using current date")
        now = datetime.now()
        return now.isoformat()
