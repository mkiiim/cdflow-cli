"""
Default plugin: Anonymous donor email handler

This plugin provides the default anonymous email behavior for CanadaHelps imports.
When a donor's email is marked as "ANON" in the CSV, this plugin converts it
to a configurable email address.

To customize the anonymous email address:
1. Copy this file to your plugins directory (e.g., ~/.config/cdflow/plugins/canadahelps/)
2. Edit the ANONYMOUS_EMAIL constant below
3. Enable plugins in your config:
   plugins:
     canadahelps:
       enabled: true
       dir: "~/.config/cdflow/plugins/canadahelps"
"""

from cdflow_cli.plugins.registry import register_plugin

# Configure your anonymous email address here
ANONYMOUS_EMAIL = "anonymous@donations.local"


@register_plugin("canadahelps", "row_transformer")
def handle_anonymous_email(row_data: dict) -> dict:
    """
    Convert ANON email markers to a specific anonymous email address.

    CanadaHelps uses "ANON" to indicate that a donor wishes to remain anonymous.
    This plugin converts those markers to a real email address for NationBuilder.

    Uses Option B architecture: Sets underscore field (_email) that the base
    class will read during initialization. This preserves original CSV data
    immutability.

    Args:
        row_data: Raw CSV row as dictionary

    Returns:
        Modified row_data with _email underscore field set
    """
    # Check if email field is marked as anonymous
    email_field = row_data.get("DONOR EMAIL ADDRESS")

    if email_field == "ANON":
        row_data["_email"] = ANONYMOUS_EMAIL

    return row_data
