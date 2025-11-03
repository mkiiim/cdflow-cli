# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
This module defines the donation data models used across the application.
"""

import json
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


class DonationMapper:
    """
    Base class for donation data mapping.
    Provides common functionality for mapping source data to NationBuilder fields.
    """

    def __init__(self, data, job_context=None, custom_fields_available=None):
        """
        Initialize a DonationMapper instance.

        Args:
            data (dict): Raw donation data from the source
            job_context (dict, optional): Job context containing job_id and machine_info for tracking
            custom_fields_available (dict, optional): Dict indicating which custom fields exist in NB
        """
        # Determine adapter name from class name (e.g., CHDonationMapper -> canadahelps)
        class_name = self.__class__.__name__
        if class_name.startswith("CH"):
            adapter_name = "canadahelps"
        elif class_name.startswith("PP"):
            adapter_name = "paypal"
        else:
            adapter_name = class_name.replace("DonationMapper", "").lower()

        # Execute row transformer plugins BEFORE any data processing
        from ..plugins.registry import get_plugins

        # Track original CSV fields for immutability checking
        original_csv_keys = set(k for k in data.keys() if not k.startswith('_'))

        for plugin_name, transform_func in get_plugins(adapter_name, "row_transformer"):
            try:
                # Take snapshot BEFORE this plugin runs
                before_plugin_values = {k: data.get(k) for k in original_csv_keys if k in data}

                data = transform_func(data)
                logger.debug(f"Applied row transformer plugin: {plugin_name}")

                # Check for modifications THIS plugin made (compare before vs after)
                for key in original_csv_keys:
                    before_value = before_plugin_values.get(key)
                    after_value = data.get(key)
                    if before_value != after_value:
                        logger.warning(
                            f"Plugin '{plugin_name}' modified original CSV field '{key}'. "
                            f"Plugins should add underscore fields (_field_name) instead of "
                            f"modifying original data. Original: '{before_value}', "
                            f"Modified: '{after_value}'"
                        )
            except Exception as e:
                logger.error(f"Error in row transformer plugin {plugin_name}: {e}")

        self.data = data
        self.class_name = class_name

        # Store job context for donation tracking fields
        self.job_context = job_context

        # Store custom field availability for intelligent field inclusion
        self.custom_fields_available = custom_fields_available or {}
        
        # Create a case-insensitive and BOM-insensitive access dictionary for field values
        self.keys_map = {}
        for k in data.keys():
            # Remove BOM from key
            clean_key = k.replace("\ufeff", "").lower()
            self.keys_map[clean_key] = k

        # Initialize ALL NB fields from plugin underscore fields (Option B architecture)
        # None = not set by plugin, allows mappers to use map_field() for CSV fallback
        # Person fields
        self.NBfirst_name = data.get("_first_name", None)
        self.NBlast_name = data.get("_last_name", None)
        self.NBmiddle_name = data.get("_middle_name", None)
        self.NBemail = data.get("_email", None)
        self.NBemail_opt_in = data.get("_email_opt_in", None)
        self.NBemployer = data.get("_employer", None)
        self.NBphone = data.get("_phone", None)
        self.NBlanguage = data.get("_language", None)

        # Business logic fields - use plugin-provided values
        self.NBcheck_number = data.get("_check_number", None)
        self.NBpayment_type_name = data.get("_payment_type", None)
        self.NBtracking_code_slug = data.get("_tracking_code", None)

        # Donation-specific fields
        self.NBrecurring_donation_id = data.get("_recurring_donation_id", None)
        self.NBamount_in_cents = data.get("_amount_in_cents", None)
        self.NBsucceeded_at = data.get("_succeeded_at", None)

        # Billing address fields
        self.NBbilling_address_address1 = data.get("_billing_address_address1", None)
        self.NBbilling_address_address2 = data.get("_billing_address_address2", None)
        self.NBbilling_address_city = data.get("_billing_address_city", None)
        self.NBbilling_address_state = data.get("_billing_address_state", None)
        self.NBbilling_address_zip = data.get("_billing_address_zip", None)
        self.NBbilling_address_country = data.get("_billing_address_country", None)

    @classmethod
    def validate_row(cls, row):
        """
        Validate that a row has all required fields before attempting to create an instance.

        Args:
            row (dict): Raw donation data from the source

        Returns:
            tuple: (is_valid, error_message)
        """
        return True, None  # Base implementation assumes valid

    @classmethod
    def validate_row_case_insensitive(cls, row, required_fields):
        """
        Validate that a row has all required fields using case-insensitive comparison.
        Also handles BOM characters in keys.

        Args:
            row (dict): Raw donation data from the source
            required_fields (list): List of required field names

        Returns:
            tuple: (is_valid, error_message)
        """
        # Log the actual headers for debugging
        logger.debug(f"{cls.__name__} validation - row keys: {list(row.keys())}")

        # Create a clean key map (case-insensitive and BOM-free)
        row_keys_map = {}
        for k in row.keys():
            # Remove BOM character (U+FEFF) and convert to lowercase
            clean_key = k.replace("\ufeff", "").lower()
            row_keys_map[clean_key] = k

        # Check for missing fields using clean keys
        missing_fields = []
        for field in required_fields:
            clean_field = field.replace("\ufeff", "").lower()
            if clean_field not in row_keys_map:
                missing_fields.append(field)

        if missing_fields:
            logger.warning(f"{cls.__name__} validation failed - missing fields: {missing_fields}")
            logger.warning(f"{cls.__name__} actual headers (case-sensitive): {list(row.keys())}")
            logger.warning(f"{cls.__name__} row_keys_map (clean lowercase keys): {row_keys_map}")
            return False, f"Missing required fields: {', '.join(missing_fields)}"

        return True, None

    def get_value_case_insensitive(self, field_name):
        """
        Get a value from the source data using case-insensitive field name.
        Also handles BOM characters in field names.

        Args:
            field_name (str): Field name to look up (case-insensitive)

        Returns:
            The value from the source data, or None if not found
        """
        # Create clean key (lowercase, no BOM)
        clean_key = field_name.replace("\ufeff", "").lower()

        # Look up the actual key using the clean version
        actual_key = self.keys_map.get(clean_key)
        if actual_key:
            return self.data.get(actual_key)
        return None

    def map_field(self, nb_field_name, csv_field_name, default=""):
        """
        Map CSV field to NB field with automatic plugin priority (Option B architecture).

        If plugin already set the field (non-None value), does nothing (plugin wins).
        Otherwise reads from CSV and assigns the value.

        This implements the immutability principle and plugin priority:
        1. Plugin sets _email → NBemail gets plugin value
        2. No plugin → NBemail gets CSV value
        3. No plugin, no CSV → NBemail gets default

        Args:
            nb_field_name: NB field name (e.g., "NBemail", "NBfirst_name")
            csv_field_name: CSV field to read from (e.g., "DONOR EMAIL ADDRESS")
            default: Default value if neither plugin nor CSV provides value

        Example:
            self.map_field("NBemail", "DONOR EMAIL ADDRESS")
            # If plugin set _email: uses plugin value
            # Else if CSV has DONOR EMAIL ADDRESS: uses CSV value
            # Else: uses "" (default)
        """
        # Check if plugin already set this field
        current_value = getattr(self, nb_field_name, None)
        if current_value is not None:
            return  # Plugin value wins, don't overwrite

        # Read from CSV
        value = self.get_value_case_insensitive(csv_field_name)
        if value is None:
            value = default

        # Assign the value
        setattr(self, nb_field_name, value)

    def get_value(self, file_field_name):
        """
        Get a value from the source data.

        Args:
            file_field_name (str): Source field name

        Returns:
            The value from the source data, or None if not found
        """
        # First try exact match
        value = self.data.get(file_field_name)

        # If not found, try case-insensitive match
        if value is None:
            value = self.get_value_case_insensitive(file_field_name)

        return value

    def get_datetime_fields(self, date_field, time_field, tz_field=None, id_field=None):
        """
        Extract and combine datetime fields from source data.

        Args:
            date_field: Name of the date field in source data
            time_field: Name of the time field in source data
            tz_field: Optional name of timezone field in source data
            id_field: Optional name of record ID field for logging

        Returns:
            tuple: (combined_datetime_str, timezone_str, record_id)
                   Returns (None, None, record_id) if date or time is missing
        """
        date_value = self.get_value_case_insensitive(date_field)
        time_value = self.get_value_case_insensitive(time_field)
        timezone_value = self.get_value_case_insensitive(tz_field) if tz_field else None
        record_id = self.get_value_case_insensitive(id_field) if id_field else None

        if not date_value or not time_value:
            logger.warning(f"Missing date or time for record: {record_id}")
            return None, None, record_id

        datetime_str = f"{date_value} {time_value}"
        return datetime_str, timezone_value, record_id

    def _parse_datetime(self, datetime_str, date_format, timezone_str=None, transaction_id=None):
        """
        Internal pure datetime parsing method.

        Parses a datetime string and applies timezone (explicit or system).
        This is a low-level method - use parse_datetime_with_fallback() from mappers.

        Args:
            datetime_str: Combined date/time string to parse (timezone-naive)
            date_format: Format string for strptime
            timezone_str: Optional timezone abbreviation (e.g., "EDT", "PST", "UTC")
                         If None, uses system timezone
            transaction_id: Optional transaction ID for logging

        Returns:
            str: ISO 8601 formatted datetime with timezone applied

        Raises:
            ValueError: If datetime_str cannot be parsed with date_format
        """
        # Parse the datetime string (raises ValueError if invalid format)
        datetime_obj = datetime.strptime(datetime_str, date_format)

        # Apply timezone
        if timezone_str:
            # Use explicit timezone from source data
            timezone_map = {
                'EDT': 'US/Eastern',     # Eastern Daylight Time
                'EST': 'US/Eastern',     # Eastern Standard Time
                'PDT': 'US/Pacific',     # Pacific Daylight Time
                'PST': 'US/Pacific',     # Pacific Standard Time
                'CDT': 'US/Central',     # Central Daylight Time
                'CST': 'US/Central',     # Central Standard Time
                'MDT': 'US/Mountain',    # Mountain Daylight Time
                'MST': 'US/Mountain',    # Mountain Standard Time
                'UTC': 'UTC',            # Coordinated Universal Time
                'GMT': 'GMT',            # Greenwich Mean Time
            }

            pytz_timezone_name = timezone_map.get(timezone_str.upper())
            if pytz_timezone_name:
                tz = pytz.timezone(pytz_timezone_name)

                # Handle DST appropriately
                if timezone_str.upper() in ['EDT', 'PDT', 'CDT', 'MDT']:
                    localized_dt = tz.localize(datetime_obj, is_dst=True)
                elif timezone_str.upper() in ['EST', 'PST', 'CST', 'MST']:
                    localized_dt = tz.localize(datetime_obj, is_dst=False)
                else:
                    localized_dt = tz.localize(datetime_obj)

                logger.debug(f"Timezone conversion: {datetime_str} {timezone_str} -> {localized_dt.isoformat()}")
            else:
                # Unknown timezone, fall back to system timezone
                logger.warning(f"Unknown timezone '{timezone_str}', using system timezone")
                localized_dt = datetime_obj.astimezone()
        else:
            # Use system timezone with DST rules for the parsed date
            localized_dt = datetime_obj.astimezone()

        return localized_dt.isoformat()

    def parse_datetime_with_fallback(self, datetime_str, date_format, tz_str=None, record_id=None, fallback='now'):
        """
        Parse datetime with configurable fallback behavior.

        This method provides flexible handling of missing or invalid datetime data,
        allowing different organizations to implement their own policies.

        Args:
            datetime_str: Combined date/time string to parse (or None if missing)
            date_format: Format string for strptime
            tz_str: Optional timezone string (e.g., "EDT", "PST") for explicit timezone parsing
            record_id: Optional record ID for logging
            fallback: Fallback behavior when datetime is missing or invalid:
                     'now' - Use current timestamp (default, backward compatible)
                     'none' - Return None (let plugins or downstream handle)
                     'raise' - Raise ValueError (fail fast)

        Returns:
            str: ISO 8601 formatted datetime, or None if fallback='none'

        Raises:
            ValueError: If fallback='raise' and datetime cannot be parsed
        """
        # Handle missing datetime
        # Note: Missing datetime warning already logged by get_datetime_fields() if applicable
        if not datetime_str:
            if fallback == 'raise':
                raise ValueError(f"Missing datetime for record {record_id}")
            elif fallback == 'none':
                return None
            else:  # fallback == 'now'
                return datetime.now().isoformat()

        # Parse datetime using internal method
        try:
            return self._parse_datetime(datetime_str, date_format, tz_str, record_id)
        except ValueError as e:
            # Handle parsing errors based on fallback strategy
            if fallback == 'raise':
                raise ValueError(f"Invalid datetime format for record {record_id}: {datetime_str} - {str(e)}")
            elif fallback == 'none':
                logger.error(f"Invalid datetime format for record {record_id}: {datetime_str} - {str(e)}")
                return None
            else:  # fallback == 'now'
                logger.error(f"Invalid datetime format for record {record_id}: {datetime_str} - {str(e)}, using current time as fallback")
                return datetime.now().isoformat()

    def convert_date_time(self, date_field, time_field, date_format, tz_field=None, id_field=None, fallback='now'):
        """
        Convert date and time from source format to NationBuilder ISO 8601 format.

        This is a generic method that can be used by all mappers. Subclasses can override
        to provide adapter-specific field names and formats.

        Args:
            date_field: Name of date field in source data
            time_field: Name of time field in source data
            date_format: strptime format string for parsing
            tz_field: Optional timezone field name
            id_field: Optional ID field name for logging
            fallback: Fallback strategy ('now', 'none', 'raise')

        Returns:
            str: ISO 8601 formatted datetime with timezone
        """
        # Extract datetime fields using base class helper
        datetime_str, timezone_value, record_id = self.get_datetime_fields(
            date_field, time_field, tz_field, id_field
        )

        # Parse with configurable fallback
        result = self.parse_datetime_with_fallback(
            datetime_str, date_format, tz_str=timezone_value, record_id=record_id, fallback=fallback
        )

        # Provide additional context for missing data fallback (backward compatibility with existing logs)
        if not datetime_str and result:
            logger.info(
                f"DEBUG - Record {record_id}: NationBuilder date='{result}' (MISSING DATA FALLBACK)"
            )

        return result

    def to_json_people_data(self):
        """
        Convert person data to a JSON-formatted string for NationBuilder API.

        Returns:
            str: JSON-formatted person data
        """
        people_data = {
            "email": self.NBemail,
            "first_name": self.NBfirst_name,
            "middle_name": self.NBmiddle_name,
            "last_name": self.NBlast_name,
            "email_opt_in": self.NBemail_opt_in,
            "employer": self.NBemployer,
            "phone": self.NBphone,
            "language": self.NBlanguage,
        }
        logger.debug(f"{self.class_name} people_data: {people_data}")
        return json.dumps(people_data)

    def to_json_donation_data(self):
        """
        Convert donation data to a JSON-formatted string for NationBuilder API.

        Returns:
            str: JSON-formatted donation data
        """
        donation_data = {
            "donor_id": "",
            "email": self.NBemail,
            "first_name": self.NBfirst_name,
            "middle_name": self.NBmiddle_name,
            "last_name": self.NBlast_name,
            "check_number": self.NBcheck_number,
            "amount_in_cents": self.NBamount_in_cents,
            "payment_type_name": self.NBpayment_type_name,
            "succeeded_at": self.NBsucceeded_at,
            "tracking_code_slug": self.NBtracking_code_slug,
            "billing_address": {
                "address1": self.NBbilling_address_address1,
                "address2": self.NBbilling_address_address2,
                "city": self.NBbilling_address_city,
                "state": self.NBbilling_address_state,
                "zip": self.NBbilling_address_zip,
                "country_code": self.NBbilling_address_country,
            },
        }
        
        # === JOB TRACKING FIELDS (Auto-detected) ===
        # Automatically include tracking fields if they exist in the NationBuilder nation
        if self.job_context and self.custom_fields_available:
            if self.custom_fields_available.get("import_job_id", False):
                donation_data["import_job_id"] = self.job_context.get("job_id", "")
                
            if self.custom_fields_available.get("import_job_source", False):
                donation_data["import_job_source"] = json.dumps(self.job_context.get("machine_info", {}))
        # === END JOB TRACKING FIELDS ===
        logger.debug(f"{self.class_name} donation_data: {donation_data}")
        return json.dumps(donation_data)

    def lookup_person(self, people_client):
        """
        Look up a person in NationBuilder using standard email lookup.
        This base implementation performs simple email-based person lookup.
        Override in subclasses for custom lookup logic.

        Args:
            people_client: NBPeople client instance

        Returns:
            Tuple of (person_id, success_flag, message)
        """
        return people_client.get_personid_by_email(self.NBemail)
