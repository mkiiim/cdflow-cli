"""
Example plugin: Sanitize ANON fields

This plugin transforms "ANON" values to empty strings for specified fields.
CanadaHelps uses "ANON" to indicate anonymous donor information.

Note: If you're using the 10_anonymous_email.py plugin, this plugin will
handle address and name fields while that one handles email. They work together.

Usage:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/canadahelps/)
2. Enable plugins in your config:
   plugins:
     canadahelps:
       enabled: true
       dir: "~/.config/cdflow/plugins/canadahelps"
3. Run your import as normal
"""

from cdflow_cli.plugins.registry import register_plugin

# Mapping of CSV fields to NB underscore fields
FIELDS_TO_SANITIZE = {
    "DONOR ADDRESS 1": "_billing_address_address1",
    "DONOR ADDRESS 2": "_billing_address_address2",
    "DONOR CITY": "_billing_address_city",
    "DONOR PROVINCE/STATE": "_billing_address_state",
    "DONOR POSTAL/ZIP CODE": "_billing_address_zip",
    "DONOR COUNTRY": "_billing_address_country",
}


@register_plugin("canadahelps", "row_transformer")
def sanitize_anon_fields(row_data: dict) -> dict:
    """
    Replace "ANON" values with empty strings for configured fields.

    CanadaHelps marks anonymous donor information with "ANON".
    This plugin sanitizes those fields to empty strings using underscore fields.

    Uses Option B architecture: Sets underscore fields (_field_name) that the
    base class will read during initialization. This preserves original CSV
    data immutability.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with underscore fields set for ANON values
    """
    for csv_field, underscore_field in FIELDS_TO_SANITIZE.items():
        if row_data.get(csv_field) == "ANON":
            row_data[underscore_field] = ""

    return row_data
