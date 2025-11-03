"""
Example plugin: Eligibility filter for PayPal

IMPORTANT: This plugin should run LAST (99_ prefix) to filter donations
after all data transformations are complete.

This plugin filters out PayPal transactions that shouldn't be imported.
Different organizations have different eligibility criteria.

Note: Transaction type validation is handled by the payment_type_mapper plugin.
This plugin focuses on duplicate detection and other business rules.

This example shows a common pattern:
- Skip records with Custom Number (already processed)
- Additional business rules can be added (date ranges, amounts, etc.)

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/paypal/)
2. Customize the eligibility rules for your organization
3. Use 99_ prefix to ensure this runs last
4. Enable plugins in your config:
   plugins:
     paypal:
       enabled: true
       dir: "~/.config/cdflow/plugins/paypal"
5. Run your import as normal

Plugin Ordering:
- 00-89: Data transformations (tracking codes, payment types, etc.)
- 90-99: Filtering/validation (this plugin should be here)

Customization:
- Change PROCESSED_MARKER_FIELD to match your duplicate detection strategy
- Add date-based filtering (e.g., only import recent transactions)
- Add amount-based filtering (e.g., minimum donation amount)
- Add currency restrictions
- Add any other business rules specific to your workflow
"""

from cdflow_cli.plugins.registry import register_plugin

# Field used to track already-processed donations
PROCESSED_MARKER_FIELD = "Custom Number"


@register_plugin("paypal", "row_transformer")
def filter_eligible_donations(row_data: dict) -> dict:
    """
    Filter out ineligible PayPal transactions.

    Sets _skip_row=True for records that shouldn't be imported.
    The parser's is_eligible() method will check this flag.

    Note: Transaction type validation happens in the payment_type_mapper plugin.
    This plugin focuses on duplicate detection and other business rules.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _skip_row set if ineligible
    """
    # Check 1: Skip if Custom Number is populated (indicates already processed)
    # This could be the example organization's duplicate detection strategy
    if row_data.get(PROCESSED_MARKER_FIELD):
        row_data["_skip_row"] = True
        row_data["_skip_reason"] = "Duplicate - already processed (Custom Number populated)"
        return row_data

    # Check 2: Skip if missing both name and email (required for NationBuilder)
    name_value = row_data.get("Name", "")
    email_value = row_data.get("From Email Address", "")

    if not (bool(name_value) or bool(email_value)):
        row_data["_skip_row"] = True
        row_data["_skip_reason"] = "Missing both name and email"
        return row_data

    # Add other business rules here:
    # - Date range filtering
    # - Minimum amount checks
    # - Currency restrictions
    # - etc.

    # All checks passed - eligible for import
    return row_data
