import pytest
from cdflow_cli.plugins.registry import (
    register_plugin,
    get_plugins,
    clear_registry,
    _registry
)


class TestPluginRegistry:

    def setup_method(self):
        """Clear registry before each test."""
        clear_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_registry()

    def test_register_plugin_basic(self):
        """Test basic plugin registration."""
        @register_plugin("canadahelps", "row_transformer")
        def test_plugin(row_data: dict) -> dict:
            return row_data

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
        assert plugins[0][0] == "test_plugin"
        assert plugins[0][1] == test_plugin

    def test_register_multiple_plugins(self):
        """Test registering multiple plugins."""
        @register_plugin("canadahelps", "row_transformer")
        def plugin_one(row_data: dict) -> dict:
            return row_data

        @register_plugin("canadahelps", "field_processor")
        def plugin_two(field_name: str, value, row_data: dict):
            return value

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 2
        assert plugins[0][0] == "plugin_one"
        assert plugins[1][0] == "plugin_two"

    def test_register_different_adapters(self):
        """Test registering plugins for different adapters."""
        @register_plugin("canadahelps", "row_transformer")
        def ch_plugin(row_data: dict) -> dict:
            return row_data

        @register_plugin("paypal", "row_transformer")
        def pp_plugin(row_data: dict) -> dict:
            return row_data

        ch_plugins = get_plugins("canadahelps")
        pp_plugins = get_plugins("paypal")

        assert len(ch_plugins) == 1
        assert len(pp_plugins) == 1
        assert ch_plugins[0][0] == "ch_plugin"
        assert pp_plugins[0][0] == "pp_plugin"

    def test_get_plugins_by_type(self):
        """Test filtering plugins by type."""
        @register_plugin("canadahelps", "row_transformer")
        def transformer(row_data: dict) -> dict:
            return row_data

        @register_plugin("canadahelps", "field_processor")
        def processor(field_name: str, value, row_data: dict):
            return value

        @register_plugin("canadahelps", "donation_validator")
        def validator(donation):
            return donation

        all_plugins = get_plugins("canadahelps")
        row_transformers = get_plugins("canadahelps", "row_transformer")
        field_processors = get_plugins("canadahelps", "field_processor")
        validators = get_plugins("canadahelps", "donation_validator")

        assert len(all_plugins) == 3
        assert len(row_transformers) == 1
        assert len(field_processors) == 1
        assert len(validators) == 1

        assert row_transformers[0][0] == "transformer"
        assert field_processors[0][0] == "processor"
        assert validators[0][0] == "validator"

    def test_get_plugins_empty_adapter(self):
        """Test getting plugins for adapter with no plugins."""
        plugins = get_plugins("canadahelps")
        assert len(plugins) == 0

    def test_get_plugins_unknown_adapter(self):
        """Test getting plugins for unknown adapter."""
        plugins = get_plugins("unknown_adapter")
        assert len(plugins) == 0

    def test_clear_registry_specific_adapter(self):
        """Test clearing registry for specific adapter."""
        @register_plugin("canadahelps", "row_transformer")
        def ch_plugin(row_data: dict) -> dict:
            return row_data

        @register_plugin("paypal", "row_transformer")
        def pp_plugin(row_data: dict) -> dict:
            return row_data

        clear_registry("canadahelps")

        ch_plugins = get_plugins("canadahelps")
        pp_plugins = get_plugins("paypal")

        assert len(ch_plugins) == 0
        assert len(pp_plugins) == 1

    def test_clear_registry_all_adapters(self):
        """Test clearing registry for all adapters."""
        @register_plugin("canadahelps", "row_transformer")
        def ch_plugin(row_data: dict) -> dict:
            return row_data

        @register_plugin("paypal", "row_transformer")
        def pp_plugin(row_data: dict) -> dict:
            return row_data

        clear_registry()

        ch_plugins = get_plugins("canadahelps")
        pp_plugins = get_plugins("paypal")

        assert len(ch_plugins) == 0
        assert len(pp_plugins) == 0

    def test_plugin_execution(self):
        """Test that registered plugins can be executed."""
        @register_plugin("canadahelps", "row_transformer")
        def uppercase_values(row_data: dict) -> dict:
            return {k: v.upper() if isinstance(v, str) else v for k, v in row_data.items()}

        plugins = get_plugins("canadahelps", "row_transformer")
        assert len(plugins) == 1

        name, func = plugins[0]
        test_data = {"name": "john", "amount": "100"}
        result = func(test_data)

        assert result["name"] == "JOHN"
        assert result["amount"] == "100"

    def test_multiple_plugins_same_type_execution_order(self):
        """Test that multiple plugins of same type maintain registration order."""
        execution_order = []

        @register_plugin("canadahelps", "row_transformer")
        def first_plugin(row_data: dict) -> dict:
            execution_order.append("first")
            return row_data

        @register_plugin("canadahelps", "row_transformer")
        def second_plugin(row_data: dict) -> dict:
            execution_order.append("second")
            return row_data

        plugins = get_plugins("canadahelps", "row_transformer")

        for name, func in plugins:
            func({})

        assert execution_order == ["first", "second"]

    def test_register_plugin_preserves_function_name(self):
        """Test that decorator preserves original function name."""
        @register_plugin("canadahelps", "row_transformer")
        def my_custom_plugin(row_data: dict) -> dict:
            return row_data

        assert my_custom_plugin.__name__ == "my_custom_plugin"

    def test_register_new_adapter_dynamically(self):
        """Test that new adapters can be registered dynamically."""
        @register_plugin("custom_adapter", "row_transformer")
        def custom_plugin(row_data: dict) -> dict:
            return row_data

        plugins = get_plugins("custom_adapter")
        assert len(plugins) == 1
        assert plugins[0][0] == "custom_plugin"
