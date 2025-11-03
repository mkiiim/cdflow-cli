"""
Example plugin: Tracking code mapper for CanadaHelps

This plugin maps CanadaHelps donation types to NationBuilder tracking codes.
Different organizations have different tracking code conventions.

This example shows a common pattern: separate tracking codes for monthly
vs one-time donations based on the MONTHLY GIFT ID field.

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/canadahelps/)
2. Customize the tracking codes to match your NationBuilder setup
3. Enable plugins in your config:
   plugins:
     canadahelps:
       enabled: true
       dir: "~/.config/cdflow/plugins/canadahelps"
4. Run your import as normal

Customization:
- Change the tracking code names to match your NationBuilder setup
- Add more sophisticated logic (campaign-based, amount-based, etc.)
- Use additional fields to determine tracking codes
"""

from cdflow_cli.plugins.registry import register_plugin


# Tracking codes for different donation types
MONTHLY_TRACKING_CODE = "donation_canadahelps_monthly"
ONETIME_TRACKING_CODE = "donation_canadahelps"


@register_plugin("canadahelps", "row_transformer")
def map_tracking_code(row_data: dict) -> dict:
    """
    Map CanadaHelps donation to tracking code.

    Analyzes the MONTHLY GIFT ID field and sets a _tracking_code field
    that the parser will use for NBtracking_code_slug.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _tracking_code field set
    """
    # Find monthly gift ID field (case-insensitive, BOM-insensitive)
    monthly_gift_id = None
    for key in row_data.keys():
        if key.lower().replace("\ufeff", "") == "monthly gift id":
            monthly_gift_id = row_data[key]
            break

    # Set tracking code based on whether it's a monthly donation
    if monthly_gift_id:
        row_data["_tracking_code"] = MONTHLY_TRACKING_CODE
    else:
        row_data["_tracking_code"] = ONETIME_TRACKING_CODE

    return row_data
