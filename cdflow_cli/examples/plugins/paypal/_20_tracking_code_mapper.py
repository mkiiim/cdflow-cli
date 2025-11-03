"""
Example plugin: Tracking code mapper for PayPal

This plugin maps PayPal Item Title to NationBuilder tracking codes.
Different organizations have different tracking code conventions.

This example shows a common pattern: separate tracking codes for monthly
vs one-time donations based on the Item Title field.

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/paypal/)
2. Customize the mapping logic for your organization
3. Enable plugins in your config:
   plugins:
     paypal:
       enabled: true
       dir: "~/.config/cdflow/plugins/paypal"
4. Run your import as normal

Customization:
- Change the tracking code names to match your NationBuilder setup
- Add more sophisticated parsing (product names, amounts, etc.)
- Add multiple tracking codes based on different criteria
"""

from cdflow_cli.plugins.registry import register_plugin


# Mapping: substring to search for (case-insensitive) -> tracking code
# First match wins, so order matters (more specific patterns should come first)
TRACKING_CODE_MAP = {
    "month": "membership_paypal_monthly",
    "year": "membership_paypal_annual",
    "annual": "membership_paypal_annual",
}

DEFAULT_TRACKING_CODE = "donation_paypal"


@register_plugin("paypal", "row_transformer")
def map_tracking_code(row_data: dict) -> dict:
    """
    Map PayPal Item Title to tracking code.

    Analyzes the Item Title field and sets a _tracking_code field
    that the parser will use for NBtracking_code_slug.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _tracking_code field set
    """
    item_title = row_data.get("Item Title", "")

    # Default to one-time donation tracking code
    tracking_code = DEFAULT_TRACKING_CODE

    # Check for keyword matches (case-insensitive)
    if item_title:
        item_title_lower = str(item_title).lower()
        for keyword, code in TRACKING_CODE_MAP.items():
            if keyword.lower() in item_title_lower:
                tracking_code = code
                break

    row_data["_tracking_code"] = tracking_code
    return row_data
