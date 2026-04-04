from cdflow_cli.plugins.loader import load_plugins
from cdflow_cli.plugins.registry import clear_registry, get_plugins, register_plugin


class TestPluginContracts:
    """Behavior-first contracts for plugin ordering and callback semantics."""

    def setup_method(self):
        clear_registry()

    def teardown_method(self):
        clear_registry()

    def test_loader_skips_disabled_files_and_preserves_alphabetical_order(self, tmp_path):
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "_disabled.py").write_text(
            """
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def disabled_plugin(row_data):
    return row_data
"""
        )
        (plugins_dir / "z_last.py").write_text(
            """
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def plugin_z(row_data):
    return row_data
"""
        )
        (plugins_dir / "a_first.py").write_text(
            """
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def plugin_a(row_data):
    return row_data
"""
        )

        count = load_plugins("canadahelps", plugins_dir)
        plugins = get_plugins("canadahelps", "row_transformer")

        assert count == 2
        assert [name for name, _func in plugins] == ["plugin_a", "plugin_z"]

    def test_person_lookup_plugin_receives_default_lookup_contract(self):
        observed = {}

        @register_plugin("paypal", "person_lookup")
        def external_fallback(donation, people_client, default_lookup):
            observed["donation"] = donation
            observed["people_client"] = people_client
            observed["default_lookup"] = default_lookup

            person_id, success, message = default_lookup()
            if not success:
                return people_client.lookup_external(), True, "plugin fallback"
            return person_id, success, message

        plugin_name, plugin_func = get_plugins("paypal", "person_lookup")[0]

        class Donation:
            pass

        class PeopleClient:
            def lookup_external(self):
                return 999

        donation = Donation()
        people_client = PeopleClient()

        person_id, success, message = plugin_func(
            donation,
            people_client,
            lambda: (None, False, "not found"),
        )

        assert plugin_name == "external_fallback"
        assert observed["donation"] is donation
        assert observed["people_client"] is people_client
        assert callable(observed["default_lookup"])
        assert person_id == 999
        assert success is True
        assert message == "plugin fallback"
