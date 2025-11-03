"""Tests for person_lookup plugin type."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from cdflow_cli.plugins.registry import register_plugin, get_plugins, clear_registry
from cdflow_cli.plugins.loader import load_plugins
from cdflow_cli.adapters.paypal.mapper import PPDonationMapper


class TestPersonLookupPlugin:
    """Test person_lookup plugin functionality."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Clear registry before and after each test."""
        clear_registry()
        yield
        clear_registry()

    def test_person_lookup_plugin_registration(self):
        """Test that person_lookup plugins can be registered."""
        @register_plugin("paypal", "person_lookup")
        def custom_lookup(donation, people_client, default_lookup):
            return (123, True, "Found via plugin")

        plugins = get_plugins("paypal", "person_lookup")
        assert len(plugins) == 1
        assert plugins[0][0] == "custom_lookup"

    def test_person_lookup_plugin_execution(self):
        """Test that person_lookup plugin gets called with correct parameters."""
        call_log = []

        @register_plugin("paypal", "person_lookup")
        def tracking_lookup(donation, people_client, default_lookup):
            call_log.append({
                "donation": donation,
                "people_client": people_client,
                "default_lookup": default_lookup
            })
            return (456, True, "Plugin executed")

        plugins = get_plugins("paypal", "person_lookup")
        plugin_name, plugin_func = plugins[0]

        # Create mock objects
        mock_donation = Mock()
        mock_people_client = Mock()
        mock_default_lookup = Mock()

        # Execute plugin
        person_id, success, message = plugin_func(
            mock_donation,
            mock_people_client,
            mock_default_lookup
        )

        assert person_id == 456
        assert success is True
        assert message == "Plugin executed"
        assert len(call_log) == 1
        assert call_log[0]["donation"] == mock_donation

    def test_external_id_fallback_plugin(self, tmp_path):
        """Test the external ID fallback plugin example."""
        # Create plugin file
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin
import logging

logger = logging.getLogger(__name__)

@register_plugin("paypal", "person_lookup")
def external_id_fallback(donation, people_client, default_lookup):
    """External ID fallback lookup."""
    # Try default lookup first
    person_id, success, message = default_lookup()

    # If failed and no email, try external ID
    if not donation.NBemail and not success:
        ext_id = donation.get_value_case_insensitive("Name")
        person_id, person_email, success, message = people_client.get_personid_by_extid(ext_id)

        if success and person_email:
            donation.NBemail = person_email

    return person_id, success, message
'''
        (plugins_dir / "external_id.py").write_text(plugin_code)

        # Load the plugin
        load_plugins("paypal", plugins_dir)

        # Get the registered plugin
        plugins = get_plugins("paypal", "person_lookup")
        assert len(plugins) == 1
        plugin_name, plugin_func = plugins[0]

        # Create mock donation (no email)
        mock_donation = Mock()
        mock_donation.NBemail = ""
        mock_donation.get_value_case_insensitive = Mock(return_value="John Doe")

        # Mock people_client
        mock_people_client = Mock()

        # Email lookup fails (default_lookup)
        mock_default_lookup = Mock(return_value=(None, False, "Email not found"))

        # External ID lookup succeeds
        mock_people_client.get_personid_by_extid = Mock(
            return_value=(789, "john@example.com", True, "Found by ext ID")
        )

        # Execute plugin
        person_id, success, message = plugin_func(
            mock_donation,
            mock_people_client,
            mock_default_lookup
        )

        # Verify default lookup was tried
        mock_default_lookup.assert_called_once()

        # Verify external ID lookup was tried
        mock_people_client.get_personid_by_extid.assert_called_once_with("John Doe")

        # Verify email was updated on donation
        assert mock_donation.NBemail == "john@example.com"

        # Verify return values
        assert person_id == 789
        assert success is True
        assert message == "Found by ext ID"

    def test_person_lookup_plugin_with_email_success(self, tmp_path):
        """Test that plugin uses default lookup when email lookup succeeds."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("paypal", "person_lookup")
def external_id_fallback(donation, people_client, default_lookup):
    """External ID fallback lookup."""
    person_id, success, message = default_lookup()

    if not donation.NBemail and not success:
        ext_id = donation.get_value_case_insensitive("Name")
        person_id, person_email, success, message = people_client.get_personid_by_extid(ext_id)
        if success and person_email:
            donation.NBemail = person_email

    return person_id, success, message
'''
        (plugins_dir / "external_id.py").write_text(plugin_code)
        load_plugins("paypal", plugins_dir)

        plugins = get_plugins("paypal", "person_lookup")
        plugin_name, plugin_func = plugins[0]

        # Mock donation with email
        mock_donation = Mock()
        mock_donation.NBemail = "test@example.com"

        # Mock people_client
        mock_people_client = Mock()

        # Email lookup succeeds
        mock_default_lookup = Mock(return_value=(999, True, "Found by email"))

        # Execute plugin
        person_id, success, message = plugin_func(
            mock_donation,
            mock_people_client,
            mock_default_lookup
        )

        # Verify default lookup was used
        mock_default_lookup.assert_called_once()

        # Verify external ID lookup was NOT called
        mock_people_client.get_personid_by_extid.assert_not_called()

        # Verify return values from default lookup
        assert person_id == 999
        assert success is True
        assert message == "Found by email"
