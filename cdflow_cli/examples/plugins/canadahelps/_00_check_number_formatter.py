"""
Example plugin: Check number formatter for CanadaHelps

This plugin formats the check number field with a prefix to identify
the source platform. This helps distinguish donations from different
sources in NationBuilder.

Default: Prefixes transaction number with "CH_" (CanadaHelps)

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/canadahelps/)
2. Customize the prefix or formatting logic for your organization
3. Enable plugins in your config:
   plugins:
     canadahelps:
       enabled: true
       dir: "~/.config/cdflow/plugins/canadahelps"
4. Run your import as normal

Customization:
- Change CHECK_NUMBER_PREFIX to use a different prefix
- Add additional formatting logic (e.g., padding, date prefixes)
- Remove prefix entirely by setting CHECK_NUMBER_PREFIX = ""
"""

from cdflow_cli.plugins.registry import register_plugin


# Prefix to add to transaction number for check number field
CHECK_NUMBER_PREFIX = "CH_"


@register_plugin("canadahelps", "row_transformer")
def format_check_number(row_data: dict) -> dict:
    """
    Format check number with platform prefix.

    Reads the TRANSACTION NUMBER field and creates a _check_number field
    that the parser will use for NBcheck_number.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _check_number field set
    """
    # Find transaction number field (case-insensitive, BOM-insensitive)
    transaction_number = None
    for key in row_data.keys():
        if key.lower().replace("\ufeff", "") == "transaction number":
            transaction_number = row_data[key]
            break

    # Format check number with prefix
    if transaction_number:
        row_data["_check_number"] = f"{CHECK_NUMBER_PREFIX}{transaction_number}"

    return row_data
