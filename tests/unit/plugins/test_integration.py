import pytest
from pathlib import Path
from cdflow_cli.plugins.registry import clear_registry, get_plugins
from cdflow_cli.plugins.loader import load_plugins
from cdflow_cli.adapters.canadahelps.mapper import CHDonationMapper


class TestPluginIntegration:
    """Integration tests for end-to-end plugin execution."""

    def setup_method(self):
        """Clear registry before each test."""
        clear_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_registry()

    def test_row_transformer_plugin_integration(self, tmp_path):
        """Test that row transformer plugins execute in DonationData.__init__."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a plugin that uppercases donor names
        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def uppercase_names(row_data: dict) -> dict:
    """Uppercase donor first and last names."""
    for key in row_data:
        if "name" in key.lower():
            row_data[key] = row_data[key].upper()
    return row_data
'''
        (plugins_dir / "uppercase.py").write_text(plugin_code)

        # Load plugin
        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        # Create donation data with plugin active
        test_row = {
            "DONOR FIRST NAME": "john",
            "DONOR LAST NAME": "doe",
            "DONOR EMAIL ADDRESS": "john@example.com",
            "AMOUNT": "100.00",
            "DONATION DATE": "2025-01-01",
            "DONATION TIME": "12:00:00",
            "TRANSACTION NUMBER": "TEST123",
        }

        donation = CHDonationMapper(test_row)

        # Plugin should have uppercased the names
        assert donation.NBfirst_name == "JOHN"
        assert donation.NBlast_name == "DOE"

    def test_multiple_plugins_execute_in_order(self, tmp_path):
        """Test that multiple plugins execute in alphabetical order."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Plugin 1: Replace ANON with empty string
        plugin1 = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def sanitize_anon(row_data: dict) -> dict:
    for key, value in row_data.items():
        if value == "ANON":
            row_data[key] = ""
    return row_data
'''
        # Plugin 2: Set default value for empty fields
        plugin2 = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def set_defaults(row_data: dict) -> dict:
    if not row_data.get("DONOR EMAIL ADDRESS"):
        row_data["DONOR EMAIL ADDRESS"] = "anonymous@donations.local"
    return row_data
'''
        (plugins_dir / "01_sanitize.py").write_text(plugin1)
        (plugins_dir / "02_defaults.py").write_text(plugin2)

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 2

        # Test data with ANON email
        test_row = {
            "DONOR FIRST NAME": "Jane",
            "DONOR LAST NAME": "Doe",
            "DONOR EMAIL ADDRESS": "ANON",
            "AMOUNT": "50.00",
            "DONATION DATE": "2025-01-01",
            "DONATION TIME": "12:00:00",
            "TRANSACTION NUMBER": "TEST456",
        }

        donation = CHDonationMapper(test_row)

        # Plugin 1 should clear ANON, Plugin 2 should set default
        assert donation.NBemail == "anonymous@donations.local"

    def test_plugin_error_does_not_crash_import(self, tmp_path, caplog):
        """Test that plugin errors are logged but don't crash the import."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create a plugin that raises an error
        bad_plugin = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def broken_plugin(row_data: dict) -> dict:
    raise ValueError("Intentional error for testing")
'''
        (plugins_dir / "bad.py").write_text(bad_plugin)

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        test_row = {
            "DONOR FIRST NAME": "Test",
            "DONOR LAST NAME": "User",
            "DONOR EMAIL ADDRESS": "test@example.com",
            "AMOUNT": "25.00",
            "DONATION DATE": "2025-01-01",
            "DONATION TIME": "12:00:00",
            "TRANSACTION NUMBER": "TEST789",
        }

        # Should not raise, just log error
        donation = CHDonationMapper(test_row)

        # Donation should still be created successfully
        assert donation.NBfirst_name == "Test"
        assert "Error in row transformer plugin" in caplog.text

    def test_plugin_transforms_data_before_parsing(self, tmp_path):
        """Test plugin transforms data before parser processes it."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Plugin that adds a prefix to donor names
        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def add_prefix_to_names(row_data: dict) -> dict:
    """Add VIP prefix to donor names."""
    for key in row_data:
        if "first name" in key.lower():
            row_data[key] = f"VIP-{row_data[key]}"
    return row_data
'''
        (plugins_dir / "prefix.py").write_text(plugin_code)

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        test_row = {
            "DONOR FIRST NAME": "John",
            "DONOR LAST NAME": "Doe",
            "DONOR EMAIL ADDRESS": "john@example.com",
            "AMOUNT": "100.00",
            "DONATION DATE": "01/01/2025",
            "DONATION TIME": "12:00 PM",
            "TRANSACTION NUMBER": "TEST999",
        }

        donation = CHDonationMapper(test_row)

        # Plugin should have added VIP prefix before parser processed the data
        assert donation.NBfirst_name == "VIP-John"
        assert donation.NBlast_name == "Doe"  # Unchanged

    def test_no_plugins_loaded_normal_processing(self):
        """Test that normal processing works when no plugins are loaded."""
        # No plugins loaded
        assert len(get_plugins("canadahelps")) == 0

        test_row = {
            "DONOR FIRST NAME": "Normal",
            "DONOR LAST NAME": "Processing",
            "DONOR EMAIL ADDRESS": "normal@example.com",
            "AMOUNT": "75.00",
            "DONATION DATE": "2025-01-01",
            "DONATION TIME": "12:00:00",
            "TRANSACTION NUMBER": "NORMAL123",
        }

        donation = CHDonationMapper(test_row)

        # Should work normally without plugins
        assert donation.NBfirst_name == "Normal"
        assert donation.NBlast_name == "Processing"
        assert donation.NBemail == "normal@example.com"
