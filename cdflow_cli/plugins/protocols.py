"""
Plugin protocol definitions for type checking.

Defines the expected interfaces for different plugin types using Protocol classes.
"""

from typing import Protocol, runtime_checkable, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models.donation import DonationData


@runtime_checkable
class RowTransformer(Protocol):
    """
    Plugin that transforms raw CSV row data before parsing.

    Row transformers execute before the DonationData object is created,
    allowing modification of the raw dictionary data from the CSV file.

    Example:
        @register_plugin("canadahelps", "row_transformer")
        def sanitize_anon_fields(row_data: dict) -> dict:
            for key, value in row_data.items():
                if value == "ANON":
                    row_data[key] = ""
            return row_data
    """

    def __call__(self, row_data: dict) -> dict:
        """
        Transform row data and return modified dict.

        Args:
            row_data: Raw CSV row data as dictionary

        Returns:
            Modified row data dictionary
        """
        ...


@runtime_checkable
class FieldProcessor(Protocol):
    """
    Plugin that processes individual field values during parsing.

    Field processors execute during field assignment in the parser,
    allowing context-aware transformation of specific fields.

    Example:
        @register_plugin("canadahelps", "field_processor")
        def custom_email_handler(field_name: str, value: Any, row_data: dict) -> Any:
            if field_name == "DONOR EMAIL ADDRESS" and value == "ANON":
                return "custom@example.com"
            return value
    """

    def __call__(self, field_name: str, value: Any, row_data: dict) -> Any:
        """
        Process field value and return modified value.

        Args:
            field_name: Name of the field being processed
            value: Current value of the field
            row_data: Complete row data for context

        Returns:
            Modified field value
        """
        ...


@runtime_checkable
class DonationValidator(Protocol):
    """
    Plugin that validates/transforms complete donation objects.

    Donation validators execute after the DonationData object is fully
    constructed, allowing validation and modification of the complete object.

    Example:
        @register_plugin("canadahelps", "donation_validator")
        def enforce_minimum_amount(donation: DonationData) -> DonationData:
            if donation.NBamount_in_cents < 100:
                donation.NBamount_in_cents = 100
            return donation
    """

    def __call__(self, donation: "DonationData") -> "DonationData":
        """
        Validate/transform donation object and return it.

        Args:
            donation: DonationData object to validate/transform

        Returns:
            Modified or validated DonationData object
        """
        ...


@runtime_checkable
class PersonLookup(Protocol):
    """
    Plugin that customizes person lookup logic during import.

    Person lookup plugins execute when searching for a person in NationBuilder,
    allowing custom lookup strategies beyond simple email matching.

    Example:
        @register_plugin("paypal", "person_lookup")
        def external_id_fallback(donation, people_client, default_lookup):
            # Try default email lookup first
            person_id, success, message = default_lookup()

            # Fallback to external ID if email fails
            if not success and not donation.NBemail:
                ext_id = donation.get_value_case_insensitive("Name")
                person_id, email, success, msg = people_client.get_personid_by_extid(ext_id)
                if success and email:
                    donation.NBemail = email
                    message = msg

            return person_id, success, message
    """

    def __call__(
        self,
        donation: "DonationData",
        people_client: Any,
        default_lookup: Any
    ) -> tuple:
        """
        Perform custom person lookup logic.

        Args:
            donation: DonationData object containing donor information
            people_client: NBPeople client for API calls
            default_lookup: Callable that performs default email-based lookup

        Returns:
            Tuple of (person_id, success_flag, message)
        """
        ...
