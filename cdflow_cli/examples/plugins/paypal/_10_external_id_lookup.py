"""
Example plugin: External ID lookup fallback for PayPal

This plugin provides a custom person lookup strategy for PayPal donations
when the donor has no email address. It falls back to using the Name field
as an external ID to match against NationBuilder records.

Use case: A client manually enters member Names into the external_id field
in NationBuilder, allowing donations without email to be matched.

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/paypal/)
2. Enable plugins in your config:
   plugins:
     paypal:
       enabled: true
       dir: "~/.config/cdflow/plugins/paypal"
3. Run your import as normal

Note: This plugin requires that your NationBuilder records have Names
populated in the external_id field for matching to work.
"""

from cdflow_cli.plugins.registry import register_plugin
import logging

logger = logging.getLogger(__name__)


@register_plugin("paypal", "person_lookup")
def external_id_fallback_lookup(donation, people_client, default_lookup):
    """
    Custom person lookup with external ID fallback.

    First tries the default email-based lookup. If that fails and there's
    no email, attempts to find the person using their Name as an external ID.

    Args:
        donation: DonationData object containing donor information
        people_client: NBPeople client for API calls
        default_lookup: Callable that performs default email lookup

    Returns:
        Tuple of (person_id, success_flag, message)
    """
    # Try default email lookup first
    person_id, success, message = default_lookup()

    # If email lookup fails and there's no email, try external ID lookup
    if not donation.NBemail and not success:
        logger.debug(
            f"Email lookup failed, trying external ID lookup using Name: {donation.get_value_case_insensitive('Name')}"
        )

        ext_id = donation.get_value_case_insensitive("Name")
        person_id, person_email, success, message = people_client.get_personid_by_extid(ext_id)

        # If we found a person by external ID and got their email, update donation object
        if success and person_email:
            logger.debug(f"Found person by external ID with email: {person_email}")
            donation.NBemail = person_email  # Update internal email state
        elif not person_id and not person_email:
            logger.warning("Could not locate person by email or external ID")

    return person_id, success, message
