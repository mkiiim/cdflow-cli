"""
Example plugin: Check number formatter for PayPal

This plugin formats the check number field with a prefix to identify
the source platform. This helps distinguish donations from different
sources in NationBuilder.

Default: Prefixes transaction ID with "PP_" (PayPal)

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/paypal/)
2. Customize the prefix or formatting logic for your organization
3. Enable plugins in your config:
   plugins:
     paypal:
       enabled: true
       dir: "~/.config/cdflow/plugins/paypal"
4. Run your import as normal

Customization:
- Change CHECK_NUMBER_PREFIX to use a different prefix
- Add additional formatting logic (e.g., padding, date prefixes)
- Remove prefix entirely by setting CHECK_NUMBER_PREFIX = ""
"""

from cdflow_cli.plugins.registry import register_plugin


# Prefix to add to transaction ID for check number field
CHECK_NUMBER_PREFIX = "PP_"


@register_plugin("paypal", "row_transformer")
def format_check_number(row_data: dict) -> dict:
    """
    Format check number with platform prefix.

    Reads the Transaction ID field and creates a _check_number field
    that the parser will use for NBcheck_number.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _check_number field set
    """
    # Find transaction ID field (case-insensitive, BOM-insensitive)
    transaction_id = None
    for key in row_data.keys():
        if key.lower().replace("\ufeff", "") == "transaction id":
            transaction_id = row_data[key]
            break

    # Format check number with prefix
    if transaction_id:
        row_data["_check_number"] = f"{CHECK_NUMBER_PREFIX}{transaction_id}"

    return row_data
