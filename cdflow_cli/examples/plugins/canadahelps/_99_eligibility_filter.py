"""
Example plugin: Eligibility filter for CanadaHelps

This plugin filters out donations that should not be imported.
It runs LAST (99_ prefix) after all transformations are complete.

Default behavior: Skip donations without a receiptable amount.

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/canadahelps/)
2. Customize the eligibility logic for your organization's requirements
3. Enable plugins in your config:
   plugins:
     canadahelps:
       enabled: true
       dir: "~/.config/cdflow/plugins/canadahelps"
4. Run your import as normal

Customization:
- Modify the eligibility checks to match your organization's rules
- Add additional filtering criteria (e.g., date ranges, minimum amounts, specific campaigns)
- Remove the receiptable amount check if you want to import non-receiptable donations
"""

from cdflow_cli.plugins.registry import register_plugin


@register_plugin("canadahelps", "row_transformer")
def filter_eligible_donations(row_data: dict) -> dict:
    """
    Filter out ineligible CanadaHelps donations.

    Sets the _skip_row flag for donations that should not be imported.
    Default checks:
    - Skip donations without a receiptable amount
    - Skip donations without both name and email

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _skip_row flag set if ineligible
    """
    # Helper function to find field case-insensitively
    def get_field(field_name):
        for key in row_data.keys():
            if key.lower().replace("\ufeff", "") == field_name.lower():
                return row_data[key]
        return None

    # Check 1: Skip if receiptable amount is empty
    receiptable_amount = get_field("receiptable amount")
    if receiptable_amount == "" or receiptable_amount is None:
        row_data["_skip_row"] = True
        row_data["_skip_reason"] = "Missing receiptable amount"
        return row_data

    # Check 2: Skip if missing both name and email (required for NationBuilder)
    donor_first_name = get_field("donor first name")
    donor_last_name = get_field("donor last name")
    donor_email = get_field("donor email address")

    has_name = bool(donor_first_name) or bool(donor_last_name)
    has_email = bool(donor_email)

    if not (has_name or has_email):
        row_data["_skip_row"] = True
        row_data["_skip_reason"] = "Missing both name and email"

    return row_data
