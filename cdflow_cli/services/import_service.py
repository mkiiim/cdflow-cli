# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
Service layer for donation import business logic with updated configuration management.
"""

import os
import csv
import json
import logging
import datetime
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple, Callable
from io import StringIO

from ..adapters.nationbuilder import NBPeople, NBDonation, NationBuilderOAuth
from ..utils.config import ConfigProvider
from ..utils.logging import LoggingProvider, get_logging_provider
from ..utils.paths import get_paths
from ..utils.file_cleanup import clean_csv_content_with_uneff
from ..utils.file_utils import safe_read_text_file

logger = logging.getLogger(__name__)


class DonationImportService:
    """Service for importing donations from various sources into NationBuilder."""

    def __init__(
        self,
        config_path: str = None,
        config_provider: ConfigProvider = None,
        logging_provider: LoggingProvider = None,
        job_context: Dict[str, Any] = None,
    ):
        """
        Initialize the donation import service.

        Args:
            config_path (str, optional): Path to configuration file
            config_provider (ConfigProvider, optional): Existing ConfigProvider instance
            logging_provider (LoggingProvider, optional): Existing LoggingProvider instance
            job_context (Dict[str, Any], optional): Job context containing job_id and machine_info for tracking
        """
        # Initialize with either a provided ConfigProvider or create a new one
        self.config = config_provider if config_provider else ConfigProvider(config_path)

        # Initialize API client attributes
        self.nation_slug = None
        self.oauth = None
        self.oauth_initialized = False
        self.people = None
        self.donation = None
        self.now_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # Store job context for donation tracking (job_id, machine_info, etc.)
        self.job_context = job_context
        
        # Custom field detection cache (will be populated during API initialization)
        self.custom_fields_available = None

        # Initialize paths system for direct Path operations
        from ..utils.paths import initialize_paths

        try:
            self.paths = get_paths()
            logger.debug("Using existing paths system for import operations")
        except RuntimeError:
            # Paths not initialized, initialize them
            self.paths = initialize_paths(self.config)
            logger.debug("Initialized paths system for import operations")

        # Use the provided logging provider or initialize a new one
        self.logging_provider = logging_provider
        if not self.logging_provider:
            logging_config = self.config.get_logging_config()
            if not logging_config:
                logging_config = {
                    "provider": "file",
                    "settings": {"directory": "./logs", "level": "DEBUG", "console_level": "INFO"},
                }
            self.logging_provider = get_logging_provider(logging_config)

        # Configure logging level if specified in runtime settings
        # Get log level from new logging config structure
        logging_config = self.config.get_logging_config()
        file_level = logging_config.get("file_level", "DEBUG") if logging_config else "DEBUG"
        log_level = file_level if file_level != "NONE" else "DEBUG"
        if log_level:
            self._configure_log_level(log_level)

    def _configure_log_level(self, log_level: str):
        """
        Configure logging level based on runtime setting.

        Args:
            log_level (str): Log level name (DEBUG, INFO, etc.)
        """
        # Only set the log level, don't reconfigure the entire logging system
        # to avoid clearing existing handlers (e.g., API handlers)
        try:
            log_level_enum = getattr(logging, log_level.upper(), logging.DEBUG)
            logging.getLogger().setLevel(log_level_enum)
            logger.debug(f"Set log level to {log_level}")
        except AttributeError:
            logger.warning(f"Invalid log level: {log_level}, using DEBUG")
            logging.getLogger().setLevel(logging.DEBUG)

    def initialize_api_clients(self) -> bool:
        """
        Initialize NationBuilder API clients.

        Returns:
            bool: True if initialization was successful, False otherwise
        """
        # Skip initialization if already done
        if self.oauth_initialized:
            logger.debug("API clients already initialized, skipping")
            return True

        try:
            # Get OAuth config from our ConfigProvider
            oauth_config = self.config.get_oauth_config()
            if not oauth_config:
                logger.error("No OAuth configuration found")
                return False

            # Log the configuration we're using (with sensitive data redacted)
            redacted_config = {
                k: ("*****" if k in ["client_secret"] else v) for k, v in oauth_config.items()
            }
            logger.debug(f"Initializing OAuth with config: {redacted_config}")

            # Create NationBuilderOAuth instance
            self.oauth = NationBuilderOAuth(oauth_config, auto_initialize=False)

            # Store the nation slug from the OAuth instance
            self.nation_slug = self.oauth.slug
            logger.debug(f"Using nation slug: {self.nation_slug}")

            # Create API client instances with the OAuth instance
            # This ensures each client has access to the same OAuth instance
            self.people = NBPeople(self.oauth)
            self.donation = NBDonation(self.oauth)

            # Now explicitly initialize the OAuth token - this is where API calls happen
            logger.debug("Explicitly initializing OAuth token")
            if not self.oauth.initialize():
                logger.error("Failed to initialize OAuth token")
                return False

            logger.debug(
                f"Successfully obtained access token ending in ...{self.oauth.nb_jwt_token[-5:] if self.oauth.nb_jwt_token else 'None'}"
            )

            # Detect if custom donation tracking fields exist in this nation
            logger.debug("Detecting custom donation tracking fields")
            try:
                self.custom_fields_available = self.donation.detect_custom_donation_fields()
                logger.info(f"Custom field detection completed: {self.custom_fields_available}")
            except Exception as e:
                logger.warning(f"Failed to detect custom fields, assuming none available: {str(e)}")
                self.custom_fields_available = {"import_job_id": False, "import_job_source": False}

            self.oauth_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize API clients: {str(e)}")
            return False

    def initialize_api_clients_with_tokens(self, oauth_tokens: Dict[str, Any]) -> bool:
        """
        Initialize API clients using pre-existing OAuth tokens from user session.

        This method avoids the interactive OAuth flow by using tokens already
        obtained through the web API authentication process.

        Args:
            oauth_tokens: Dictionary containing OAuth tokens from authenticated user

        Returns:
            bool: True if initialization successful, False otherwise
        """
        # Skip initialization if already done
        if self.oauth_initialized:
            logger.debug("API clients already initialized, skipping")
            return True

        try:
            # Get OAuth config from our ConfigProvider
            oauth_config = self.config.get_oauth_config()
            if not oauth_config:
                logger.error("No OAuth configuration found")
                return False

            # Log the configuration we're using (with sensitive data redacted)
            redacted_config = {
                k: ("*****" if k in ["client_secret"] else v) for k, v in oauth_config.items()
            }
            logger.debug(
                f"Initializing OAuth with config and pre-existing tokens: {redacted_config}"
            )

            # Create NationBuilderOAuth instance without auto-initialization
            self.oauth = NationBuilderOAuth(oauth_config, auto_initialize=False)

            # Set the pre-existing tokens directly
            self.oauth.nb_jwt_token = oauth_tokens.get("access_token")
            self.oauth.nb_refresh_token = oauth_tokens.get("refresh_token")
            self.oauth.nb_token_expires_in = oauth_tokens.get("expires_in")
            
            # Only update created_at if it exists in oauth_tokens, to prevent overwriting valid metadata with None
            if "created_at" in oauth_tokens and oauth_tokens["created_at"] is not None:
                self.oauth.nb_token_created_at = oauth_tokens.get("created_at")

            # Store the nation slug from the OAuth instance
            self.nation_slug = self.oauth.slug
            logger.debug(f"Using nation slug: {self.nation_slug}")

            # Create API client instances with the OAuth instance
            self.people = NBPeople(self.oauth)
            self.donation = NBDonation(self.oauth)

            # Verify the token is valid by making a simple API call
            logger.debug("Verifying OAuth token with test API call")
            try:
                # Test the token with a simple API call - try to get person by ID 1
                # This will either work (token valid) or fail with 404/401 (but at least we know the token works)
                self.people.get_person_by_id(1)
                logger.debug("OAuth token verification successful")
            except Exception as e:
                # If it's a 404, that's actually good - means token is valid but person doesn't exist
                if "404" in str(e) or "Not Found" in str(e):
                    logger.debug("OAuth token verification successful (404 is expected for test)")
                else:
                    logger.error(f"OAuth token verification failed: {str(e)}")
                    return False

            # Detect if custom donation tracking fields exist in this nation
            logger.debug("Detecting custom donation tracking fields")
            try:
                self.custom_fields_available = self.donation.detect_custom_donation_fields()
                logger.info(f"Custom field detection completed: {self.custom_fields_available}")
            except Exception as e:
                logger.warning(f"Failed to detect custom fields, assuming none available: {str(e)}")
                self.custom_fields_available = {"import_job_id": False, "import_job_source": False}

            logger.debug(
                f"Successfully initialized with access token ending in ...{self.oauth.nb_jwt_token[-5:] if self.oauth.nb_jwt_token else 'None'}"
            )

            self.oauth_initialized = True
            return True
        except Exception as e:
            logger.error(f"Failed to initialize API clients with tokens: {str(e)}")
            return False

    def determine_input_file(self) -> Tuple[Optional[str], Optional[str], Optional[Path]]:
        """
        Determine the input file and source from config.

        Returns:
            Tuple containing:
                - Input filename (str or None)
                - Source type ('CanadaHelps' or 'PayPal' or None)
                - Output directory (Path or None)
        """
        # Get import settings from the config provider
        source_type = self.config.get_import_setting("type")
        input_file = self.config.get_import_setting("file")

        if not source_type or not input_file:
            logger.error("Missing required import settings: type and file")
            return None, None, None

        # Map internal source type to expected values
        source_type_map = {"canadahelps": "CanadaHelps", "paypal": "PayPal"}

        normalized_source_type = source_type_map.get(source_type.lower())
        if not normalized_source_type:
            logger.error(f"Invalid source type: {source_type}")
            return None, None, None

        # Use just the filename part for output directory determination
        # The storage provider will handle the full path resolution
        output_dir = Path(os.path.dirname(input_file) if os.path.dirname(input_file) else ".")

        # The full path as specified in config - this will be resolved by the storage provider
        full_input_path = input_file

        logger.debug(f"Determined input file: {full_input_path}, type: {normalized_source_type}")
        return full_input_path, normalized_source_type, output_dir

    def validate_input_file(
        self, input_filename: str, expected_source_type: str, encoding: str
    ) -> bool:
        """
        Validate that the input file exists and matches the expected format.

        Args:
            input_filename (str): Path to the input file
            expected_source_type (str): Expected file format ('CanadaHelps' or 'PayPal')
            encoding (str): Detected file encoding

        Returns:
            bool: True if validation passed, False otherwise
        """
        # Check file existence using paths system
        file_path = self.paths.cli_source / input_filename
        if not file_path.exists():
            logger.error(f"Input file {input_filename} does not exist / not found")
            return False

        # Check if the input file type format matches the expected file type
        try:
            # Read file using paths system
            file_path = self.paths.cli_source / input_filename
            file_content = safe_read_text_file(file_path)
            first_line = file_content.split("\n")[0]
            detected_type = self._determine_import_type_from_header(first_line)

            if detected_type != expected_source_type:
                logger.error(f"Input file {input_filename} is not a {expected_source_type} file")
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating input file: {str(e)}")
            return False

    def _determine_import_type_from_header(self, header: str) -> Optional[str]:
        """
        Determine the type of import file based on its header.

        Args:
            header (str): First line of the file containing headers

        Returns:
            str: 'CanadaHelps', 'PayPal', or None if unrecognized
        """
        if (
            "DONOR FIRST NAME" in header
            and "DONOR LAST NAME" in header
            and "DONOR EMAIL ADDRESS" in header
        ):
            return "CanadaHelps"
        elif "Name" in header and "From Email Address" in header and "Gross" in header:
            return "PayPal"
        else:
            return None

    def generate_output_filenames(
        self, input_filename: str, output_dir: Path
    ) -> Tuple[str, str, str]:
        """
        Generate output file names for logs and results.

        Args:
            input_filename (str): Path to the input file
            output_dir (Path): Directory for output files

        Returns:
            Tuple containing paths for log file, success file, and fail file
        """
        # Extract just the filename part without path
        input_basename = os.path.basename(input_filename)
        input_stem = Path(input_basename).stem
        base_name = f"IMPORTDONATIONS_{self.now_str}_{input_stem}"

        # Build paths for the output files
        log_filename = f"{base_name}.log"
        success_filename = f"{base_name}_success.csv"
        fail_filename = f"{base_name}_fail.csv"

        logger.debug(
            f"Generated output filenames: log={log_filename}, success={success_filename}, fail={fail_filename}"
        )

        return log_filename, success_filename, fail_filename

    def get_output_filenames(self, input_filename: str, output_dir: Path) -> Tuple[str, str, str]:
        """
        Get the output filenames without running the import.

        Args:
            input_filename: Path to the input file
            output_dir: Directory for output files

        Returns:
            Tuple containing log filename, success filename, and fail filename
        """
        return self.generate_output_filenames(input_filename, output_dir)

    def _initialize_output_file(self, filename: str, fieldnames: List[str], encoding: str) -> None:
        """
        Initialize an output file with headers.

        Args:
            filename (str): Path to the output file
            fieldnames (List[str]): CSV column names
            encoding (str): File encoding
        """
        csv_output = StringIO()
        writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
        writer.writeheader()
        # Write file using paths system
        file_path = self.paths.output / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(csv_output.getvalue(), encoding=encoding)
        logger.debug(f"Initialized output file: {filename}")

    def _append_row_to_file(
        self, filename: str, row: Dict[str, Any], fieldnames: List[str], encoding: str
    ) -> None:
        """
        Append a row to an output file.

        Args:
            filename (str): Path to the output file
            row (Dict[str, Any]): Row data to append
            fieldnames (List[str]): CSV column names
            encoding (str): File encoding
        """
        # Filter out plugin-added fields (those starting with _)
        filtered_row = {k: v for k, v in row.items() if not k.startswith('_')}

        csv_output = StringIO()
        writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
        writer.writerow(filtered_row)

        # Append to file using paths system
        file_path = self.paths.output / filename
        # Append content to existing file
        with file_path.open("a", encoding=encoding) as f:
            f.write(csv_output.getvalue())
        logger.debug(f"Appended row to file: {filename}")

    def process_donations(
        self,
        input_filename: str,
        source_type: str,
        success_filename: str,
        fail_filename: str,
        encoding: str,
        progress_callback: Optional[
            Callable[[float, Optional[str], Optional[int], Optional[int], Optional[int]], None]
        ] = None,
    ) -> Tuple[int, int]:
        """
        Process donations from the input file.

        Args:
            input_filename (str): Path to the input file
            source_type (str): Source type ('CanadaHelps' or 'PayPal')
            success_filename (str): Path to success output file
            fail_filename (str): Path to fail output file
            encoding (str): File encoding
            progress_callback: Optional callback function for reporting progress

        Returns:
            Tuple containing count of successful and failed imports
        """
        # Get logger that respects CLI console log level
        processing_logger = (
            self.logging_provider.get_logger(__name__) if self.logging_provider else logger
        )

        try:
            # Read input file content using paths system
            processing_logger.debug(f"Reading input file: {input_filename}")
            # Both CLI and API now use relative paths and read from app_processing directory
            file_path = self.paths.app_processing / input_filename
            raw_content = safe_read_text_file(file_path)

            # Apply file cleanup if enabled (affects both CLI and Web App)
            if self.config.is_cleanup_enabled():
                processing_logger.debug(f"Applying file cleanup to {input_filename}")
                input_content, was_modified = clean_csv_content_with_uneff(
                    raw_content, input_filename
                )

                if was_modified:
                    processing_logger.info(
                        f"🧹 File cleanup applied to {input_filename}: problematic characters removed"
                    )
                else:
                    processing_logger.debug(
                        f"🧹 File cleanup checked {input_filename}: no changes needed"
                    )
            else:
                processing_logger.debug(
                    f"File cleanup disabled, processing original content for {input_filename}"
                )
                input_content = raw_content

            # Create CSV reader from input content
            csv_input = StringIO(input_content)
            reader = csv.DictReader(csv_input)

            # Log the field names for debugging
            if reader.fieldnames:
                processing_logger.debug(f"CSV field names: {reader.fieldnames}")
                # Add detailed logging of field names to diagnose case sensitivity issues
                processing_logger.debug(
                    f"CSV field names with case preserved: {[field for field in reader.fieldnames]}"
                )
            else:
                processing_logger.error(f"No field names found in CSV file: {input_filename}")
                if progress_callback:
                    progress_callback(0, "Error: No field names found in CSV file")
                return 0, 0

            reader_rows = list(reader)
            reader_row_count = len(reader_rows)

            processing_logger.debug(f"Found {reader_row_count} rows in CSV file")

            if reader_row_count == 0:
                processing_logger.warning(f"No data rows found in file: {input_filename}")
                if progress_callback:
                    progress_callback(100, "No data rows found in file")
                return 0, 0

            # Get field names from reader
            fieldnames = reader.fieldnames
            extended_fieldnames = fieldnames + [
                "NB Donation ID",
                "NB People ID",
                "NB People Create Date",
                "NB Error Message",
            ]

            # Initialize output files with headers - use output file type for writing
            self._initialize_output_file(success_filename, extended_fieldnames, encoding)
            self._initialize_output_file(fail_filename, extended_fieldnames, encoding)

            # Set counters
            success_count = 0
            fail_count = 0
            row_counter = 0

            # Prepare adapter-specific options
            adapter_kwargs: Dict[str, Any] = {}
            donation_class = None
            source_type_lower = source_type.lower()

            if source_type_lower == "canadahelps":
                from ..adapters.canadahelps import CHDonationMapper

                donation_class = CHDonationMapper

                # Load plugins if configured
                self._load_plugins_if_configured("canadahelps")

            elif source_type_lower == "paypal":
                from ..adapters.paypal import PPDonationMapper

                donation_class = PPDonationMapper

                # Load plugins if configured
                self._load_plugins_if_configured("paypal")

            else:
                processing_logger.error(f"Unsupported source type: {source_type}")
                if progress_callback:
                    progress_callback(0, f"Error: Unsupported source type {source_type}")
                return 0, 0

            # Process each donation row
            for row in reader_rows:
                try:
                    # Log the current row being processed and the total number of rows
                    row_counter += 1
                    progress_percentage = ((row_counter - 1) / reader_row_count) * 100
                    processing_logger.info(f"\n{'─'*60}")
                    processing_logger.info(
                        f"PROCESSING RECORD {row_counter} of {reader_row_count}. {progress_percentage:.0f}% complete"
                    )
                    processing_logger.info(
                        f"Running totals: ✓ {success_count} success, ✗ {fail_count} failed"
                    )
                    processing_logger.info(f"{'─'*60}")

                    # Report progress if callback is provided
                    if progress_callback:
                        progress_callback(
                            progress_percentage,
                            f"Processing row {row_counter} of {reader_row_count}",
                            success_count,
                            fail_count,
                            reader_row_count,
                        )

                    # Add debug logging for the first row's keys
                    if row_counter == 1:
                        processing_logger.debug(
                            f"First row keys for {source_type}: {list(row.keys())}"
                        )

                    # Validate the row
                    is_valid, error_message = donation_class.validate_row(row)
                    if not is_valid:
                        processing_logger.error(f"Invalid row data: {error_message}")
                        row["NB Error Message"] = error_message
                        self._append_row_to_file(fail_filename, row, extended_fieldnames, encoding)
                        fail_count += 1
                        continue

                    # Create the donation data object with job context and custom field detection
                    try:
                        donation_data_row = donation_class(
                            row,
                            job_context=self.job_context,
                            custom_fields_available=self.custom_fields_available,
                            **adapter_kwargs,
                        )
                    except Exception as e:
                        processing_logger.error(
                            f"Error creating donation data object: {str(e)}", exc_info=True
                        )
                        row["NB Error Message"] = f"Error creating donation data: {str(e)}"
                        self._append_row_to_file(fail_filename, row, extended_fieldnames, encoding)
                        fail_count += 1
                        continue


                    # Initialize output fields
                    row["NB Donation ID"] = ""
                    row["NB People ID"] = ""
                    row["NB People Create Date"] = ""
                    row["NB Error Message"] = ""

                    # Set response flags to False
                    response_success_create_donation = False
                    response_success_create_person = False
                    message = ""


                    # Check eligibility - plugins set _skip_row flag for ineligible donations
                    if donation_data_row.data.get("_skip_row"):
                        skip_reason = donation_data_row.data.get("_skip_reason", "Marked ineligible by plugin")
                        processing_logger.warning(
                            f"Donation not eligible: {skip_reason}"
                        )
                        row["NB Error Message"] = f"Not eligible: {skip_reason}"
                        self._append_row_to_file(fail_filename, row, extended_fieldnames, encoding)
                        fail_count += 1
                        continue

                    # Check if API clients are initialized
                    if not self.oauth_initialized:
                        if not self.initialize_api_clients():
                            processing_logger.error("Failed to initialize API clients")
                            raise ValueError("Failed to initialize API clients")

                    # Try to find the person using plugin or parser-specific lookup logic
                    person_id, response_success_get_personid_by_email, message = (
                        self._lookup_person_with_plugins(donation_data_row, source_type_lower)
                    )
                    
                    # Get updated data after lookup (captures any parser internal updates)
                    try:
                        people_data = json.loads(donation_data_row.to_json_people_data())
                        donation_data = json.loads(donation_data_row.to_json_donation_data())
                    except Exception as e:
                        processing_logger.error(
                            f"Error parsing donation data JSON after lookup: {str(e)}", exc_info=True
                        )
                        row["NB Error Message"] = f"Error parsing donation data: {str(e)}"
                        self._append_row_to_file(fail_filename, row, extended_fieldnames, encoding)
                        fail_count += 1
                        continue

                    # Start processing the donation
                    processing_logger.info(
                        f"📥 DONATION: {donation_data.get('check_number', 'N/A')} | ${donation_data.get('amount_in_cents', 0)/100:.2f} | {donation_data.get('email', 'N/A')}"
                    )

                    # If person not found, create a new person record
                    if not response_success_get_personid_by_email:
                        # Handle phone number issue: NB is using it as a unique identifier during create
                        temp_phone = people_data["phone"]
                        people_data["phone"] = ""  # do not overwrite what is already in NB

                        # Create person
                        person_id, response_success_create_person, message = (
                            self.people.create_person(people_data)
                        )
                        if not response_success_create_person:
                            raise ValueError(f"Failed to create person: {people_data}")

                        # Update with phone number
                        people_data["phone"] = temp_phone
                        person_id, response_success_update_person, message = (
                            self.people.update_person(person_id, people_data)
                        )
                        if not response_success_update_person:
                            raise ValueError(
                                f"FAILURE update_person :: problem with FIX for phone number issue :: {people_data}"
                            )

                    # Log person status
                    if response_success_get_personid_by_email:
                        processing_logger.info(f"👤 PERSON: Found existing donor (ID: {person_id})")
                    else:
                        processing_logger.info(f"🫥 PERSON: ✓ Created new donor (ID: {person_id})")
                        # Record creation date
                        row["NB People Create Date"] = self.now_str

                    # Check if donation already exists
                    response_success_create_donation = False
                    search_params = {
                        "donor_id": person_id,
                        "succeeded_since": donation_data["succeeded_at"],
                    }
                    donation_id, response_success_get_donationid_by_params, message = (
                        self.donation.get_donationid_by_params(
                            search_params, donation_data["check_number"]
                        )
                    )

                    # Create donation if it doesn't exist
                    if not response_success_get_donationid_by_params:
                        if person_id:
                            donation_data["donor_id"] = person_id
                            donation_data["first_name"] = (
                                ""  # do not overwrite what is already in NB
                            )
                            donation_data["last_name"] = (
                                ""  # do not overwrite what is already in NB
                            )

                        donation_id, response_success_create_donation, message = (
                            self.donation.create_donation(donation_data)
                        )
                        if not response_success_create_donation:
                            raise ValueError(f"Failed to create donation: {donation_data}")

                    # Log donation status
                    if response_success_get_donationid_by_params:
                        processing_logger.info(
                            f"💰 DONATION: Found existing donation (ID: {donation_id})"
                        )
                        message = "Donation already existed"
                    else:
                        processing_logger.info(
                            f"💰 DONATION: ✓ Created new donation (ID: {donation_id})"
                        )

                    # Record IDs in the output row
                    row["NB Donation ID"] = donation_id
                    row["NB People ID"] = person_id
                    row["NB Error Message"] = (
                        message if response_success_get_donationid_by_params else ""
                    )

                    # Write the row to success file - using output file type
                    self._append_row_to_file(success_filename, row, extended_fieldnames, encoding)
                    success_count += 1
                    processing_logger.info(f"✅ RECORD {row_counter} COMPLETED SUCCESSFULLY")
                    processing_logger.info(f"{'═'*60}")

                except (ValueError, KeyError, TypeError) as e:
                    fail_count += 1
                    processing_logger.error(f"❌ RECORD {row_counter} FAILED: {str(e)}")
                    processing_logger.info(f"{'═'*60}")

                    # Ineligible records are added to the fail rows - using output file type
                    if (
                        "donation_data_row" in locals()
                        and donation_data_row.data.get("_skip_row")
                    ):
                        skip_reason = donation_data_row.data.get("_skip_reason", "Ineligible record")
                        row["NB Error Message"] = f"Not eligible: {skip_reason}"
                        self._append_row_to_file(fail_filename, row, extended_fieldnames, encoding)
                        continue

                    # If the donation was not created, but a person was, remove the person
                    if response_success_create_person and not response_success_create_donation:
                        row["NB Error Message"] = (
                            message  # Capture the error message from donation creation
                        )
                        response_success_delete_person, message = self.people.delete_person(
                            person_id
                        )
                        if response_success_delete_person:
                            processing_logger.info(
                                "👤 CLEANUP: ✓ Deleted person created by this donation"
                            )
                            self._append_row_to_file(
                                fail_filename, row, extended_fieldnames, encoding
                            )
                        else:
                            processing_logger.error(
                                f"👤 CLEANUP: ✗ FAILED to delete person (ID: {person_id})"
                            )
                            processing_logger.debug(f"{response_success_delete_person}")

                            # Halt further processing, escape the loop
                            row["NB Error Message"] = f"{row['NB Error Message']} :: {message}"
                            self._append_row_to_file(
                                fail_filename, row, extended_fieldnames, encoding
                            )
                            break

                    # Handle other failures - using output file type
                    if not response_success_create_person:
                        row["NB Error Message"] = message
                        self._append_row_to_file(fail_filename, row, extended_fieldnames, encoding)

                except Exception as e:
                    # Catch broader exceptions
                    fail_count += 1
                    processing_logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                    row["NB Error Message"] = f"Unexpected error: {str(e)}"
                    self._append_row_to_file(fail_filename, row, extended_fieldnames, encoding)

            # Final progress update
            if progress_callback:
                progress_callback(
                    100, "Import complete", success_count, fail_count, reader_row_count
                )

            return success_count, fail_count

        except Exception as e:
            processing_logger.error(f"File operation error: {str(e)}", exc_info=True)
            if progress_callback:
                progress_callback(0, f"Error: {str(e)}")
            return 0, 0

    def _load_plugins_if_configured(self, adapter: str) -> int:
        """
        Load plugins for an adapter if configured.

        Args:
            adapter: Adapter name (canadahelps, paypal)

        Returns:
            int: Number of plugins loaded
        """
        from pathlib import Path
        from ..plugins.loader import load_plugins

        # Get plugin configuration from top-level 'plugins' section
        plugins_config = self.config.yaml_config.get("plugins", {})
        if not isinstance(plugins_config, dict):
            logger.info(f"No plugins configured for {adapter} (plugins section not found in config)")
            return 0

        adapter_plugins = plugins_config.get(adapter, {})
        if not isinstance(adapter_plugins, dict):
            logger.info(f"No plugins configured for {adapter} (adapter not in plugins config)")
            return 0

        plugins_enabled = adapter_plugins.get("enabled", False)
        plugins_dir = adapter_plugins.get("dir")

        if not plugins_enabled:
            logger.info(f"Plugins disabled for {adapter} (enabled=false or not set)")
            return 0

        if not plugins_dir:
            logger.info(f"No plugins dir configured for {adapter}")
            return 0

        plugins_path = Path(plugins_dir).expanduser()
        logger.debug(f"Plugin directory configured: {plugins_dir} -> {plugins_path}")

        return load_plugins(adapter, plugins_path)

    def _lookup_person_with_plugins(self, donation_data_row, adapter: str):
        """
        Look up person using plugin or default logic.

        Args:
            donation_data_row: DonationData object
            adapter: Adapter name (canadahelps, paypal)

        Returns:
            Tuple of (person_id, success_flag, message)
        """
        from ..plugins.registry import get_plugins

        # Check if there's a person_lookup plugin registered
        plugins = get_plugins(adapter, "person_lookup")

        if plugins:
            # Use the first registered person_lookup plugin
            plugin_name, lookup_func = plugins[0]
            logger.debug(f"Using person_lookup plugin: {plugin_name}")

            # Create a callable for the default lookup
            def default_lookup():
                return donation_data_row.lookup_person(self.people)

            try:
                return lookup_func(donation_data_row, self.people, default_lookup)
            except Exception as e:
                logger.error(f"Error in person_lookup plugin {plugin_name}: {e}")
                # Fall back to default if plugin fails
                return donation_data_row.lookup_person(self.people)
        else:
            # No plugin, use default parser logic
            return donation_data_row.lookup_person(self.people)

    def run_import(
        self,
        input_filename: str = None,
        encoding: str = "utf-8",
        source_type: str = None,
        existing_log_filename: str = None,
        progress_callback: Optional[Callable[[float, Optional[str]], None]] = None,
    ) -> Tuple[bool, int, int]:
        """
        Run the complete import process.

        Args:
            input_filename (str, optional): Path to the input file (overrides config)
            encoding (str, optional): File encoding (defaults to utf-8)
            source_type (str, optional): Source type ('CanadaHelps' or 'PayPal', overrides config)
            existing_log_filename (str, optional): Path to an existing log file
            progress_callback: Optional callback function for reporting progress

        Returns:
            Tuple containing success status and counts of successful/failed imports
        """
        # If input filename or source type are not provided, get them from config
        if not input_filename or not source_type:
            config_input_filename, config_source_type, output_dir = self.determine_input_file()
            input_filename = input_filename or config_input_filename
            source_type = source_type or config_source_type

            if not input_filename or not source_type:
                logger.error("Failed to determine input file or source type. Exiting.")
                return False, 0, 0
        else:
            # When input_filename is explicitly provided, use its directory as the output dir
            # The storage provider will handle resolving paths
            output_dir = Path(".")

        # Generate output filenames - these will be just the base filenames without paths
        # The storage provider will handle resolving the full paths
        log_filename, success_filename, fail_filename = self.generate_output_filenames(
            input_filename, output_dir
        )

        # Get logger for import processing
        import_logger = (
            self.logging_provider.get_logger(__name__)
            if self.logging_provider
            else logging.getLogger(__name__)
        )

        # Use existing log file if provided, otherwise use normal logging
        if existing_log_filename:
            log_filename = existing_log_filename
            # Configure logging with the provided log filename
            if self.logging_provider:
                # Get log level from configuration
                logging_config = self.config.get_logging_config()
                file_level = (
                    logging_config.get("file_level", "DEBUG") if logging_config else "DEBUG"
                )
                log_level = file_level if file_level != "NONE" else "DEBUG"

                self.logging_provider.configure_logging(
                    log_filename=log_filename, log_level=log_level or "DEBUG"
                )

            import_logger.debug(f"Configured logging with existing log file: {log_filename}")

        # Process donations - all logs will go to unified APP log and be extracted later
        success_count = 0
        fail_count = 0
        success = False

        try:
            import_logger.debug("Starting import processing")

            # Process donations - logs will be extracted by post-processing
            success_count, fail_count = self.process_donations(
                input_filename,
                source_type,
                success_filename,
                fail_filename,
                encoding,
                progress_callback,
            )

            # Log completion
            import_logger.info(f"Import complete: {source_type}, {input_filename}")
            import_logger.info(f"Successful donations: {success_count} records, {success_filename}")
            if fail_count == 0:
                import_logger.info(f"Failed donations: {fail_count} records, {fail_filename}")
            else:
                import_logger.warning(f"Failed donations: {fail_count} records, {fail_filename}")

            success = True

        except Exception as e:
            import_logger.error(f"Error during import processing: {str(e)}")
            success = False

        return success, success_count, fail_count
