"""
Example plugin: Payment type mapper for CanadaHelps

This plugin maps CanadaHelps payment methods to NationBuilder payment types.
This is the standard mapping that translates CanadaHelps terminology to
NationBuilder's payment type vocabulary.

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/canadahelps/)
2. Customize the mapping if your NationBuilder has different payment types
3. Enable plugins in your config:
   plugins:
     canadahelps:
       enabled: true
       dir: "~/.config/cdflow/plugins/canadahelps"
4. Run your import as normal

Customization:
- Modify PAYMENT_TYPE_MAP to match your NationBuilder payment types
- Add new mappings for additional CanadaHelps payment methods
"""

from cdflow_cli.plugins.registry import register_plugin


# Mapping: CanadaHelps payment method -> NationBuilder payment type
PAYMENT_TYPE_MAP = {
    "ApplePay": "Apple Pay",
    "GooglePay": "Google Pay",
    "Paypal": "Other",
    "Securities": "Other",
    "Gift Card": "Other",
    "Cheque": "Check",
}


@register_plugin("canadahelps", "row_transformer")
def map_payment_type(row_data: dict) -> dict:
    """
    Map CanadaHelps payment method to NationBuilder payment type.

    Reads the PAYMENT METHOD field and sets a _payment_type field
    that the parser will use for NBpayment_type_name.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _payment_type field set
    """
    # Find payment method field (case-insensitive, BOM-insensitive)
    payment_method = None
    for key in row_data.keys():
        if key.lower().replace("\ufeff", "") == "payment method":
            payment_method = row_data[key]
            break

    # Map to NationBuilder payment type, or pass through if not in map
    if payment_method:
        row_data["_payment_type"] = PAYMENT_TYPE_MAP.get(payment_method, payment_method)

    return row_data
