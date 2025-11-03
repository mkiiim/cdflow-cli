"""
Example plugin: Payment type mapper for PayPal

This plugin maps PayPal transaction data to NationBuilder payment types.
By default, the parser uses "Credit Card" for all PayPal transactions.

This plugin allows you to customize payment type based on:
- PayPal transaction type
- Payment method
- Other transaction attributes

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
- Map to payment types that exist in your NationBuilder setup
- Use additional PayPal fields for more sophisticated mapping
- Add logic based on amount, frequency, or other criteria
"""

from cdflow_cli.plugins.registry import register_plugin

# payment type dictionary
PAYPAL_PAYMENT_TYPE_MAP = {
    "Subscription Payment": "Credit Card",
    "Direct Credit Card Payment": "Credit Card",
    "Express Checkout Payment": "Credit Card",
}

@register_plugin("paypal", "row_transformer")
def map_payment_type(row_data: dict) -> dict:
    """
    Map PayPal transaction to NationBuilder payment type.

    Sets _payment_type field that the parser will use for
    NBpayment_type_name.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _payment_type field set
    """
    transaction_type = row_data.get("Type", "")

    # Map based on PayPal transaction type
    row_data["_payment_type"] = PAYPAL_PAYMENT_TYPE_MAP.get(transaction_type, transaction_type)

    return row_data
