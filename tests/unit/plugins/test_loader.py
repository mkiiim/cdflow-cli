import pytest
from pathlib import Path
from cdflow_cli.plugins.loader import load_plugin_bundle, load_plugins
from cdflow_cli.plugins.registry import get_plugins, clear_registry


PLUGIN_TEMPLATE = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("{adapter}", "{plugin_type}")
def {name}(row_data: dict) -> dict:
    return row_data
'''


def _write_plugin(plugins_dir, filename, name, adapter="canadahelps", plugin_type="row_transformer"):
    (plugins_dir / filename).write_text(
        PLUGIN_TEMPLATE.format(adapter=adapter, plugin_type=plugin_type, name=name)
    )


def _write_whitelist(plugins_dir, enabled):
    lines = "\n".join(f"  - {name}" for name in enabled)
    (plugins_dir / "plugins.yaml").write_text(f"enabled:\n{lines}\n" if enabled else "enabled: []\n")


class TestPluginLoader:

    def setup_method(self):
        """Clear registry before each test."""
        clear_registry()

    def teardown_method(self):
        """Clear registry after each test."""
        clear_registry()

    def test_load_plugins_directory_not_exist(self):
        """Test loading plugins from non-existent directory."""
        non_existent = Path("/tmp/nonexistent_plugin_dir_12345")
        count = load_plugins("canadahelps", non_existent)
        assert count == 0

    def test_load_plugins_not_a_directory(self, tmp_path):
        """Test loading plugins when path is a file not a directory."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("test")

        count = load_plugins("canadahelps", file_path)
        assert count == 0

    def test_load_plugins_missing_whitelist_loads_nothing(self, tmp_path, caplog):
        """Test that no plugins load and an error is logged without plugins.yaml."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "test_plugin.py", "test_plugin")

        count = load_plugins("canadahelps", plugins_dir)

        assert count == 0
        assert len(get_plugins("canadahelps")) == 0
        assert "Plugin whitelist not found" in caplog.text

    def test_load_plugins_invalid_whitelist_loads_nothing(self, tmp_path, caplog):
        """Test that an invalid plugins.yaml loads nothing and logs an error."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "test_plugin.py", "test_plugin")
        (plugins_dir / "plugins.yaml").write_text("just a string\n")

        count = load_plugins("canadahelps", plugins_dir)

        assert count == 0
        assert "Invalid plugin whitelist" in caplog.text

    def test_load_plugins_empty_whitelist_loads_nothing(self, tmp_path):
        """Test that an explicit empty whitelist is valid and loads nothing."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "test_plugin.py", "test_plugin")
        _write_whitelist(plugins_dir, [])

        count = load_plugins("canadahelps", plugins_dir)

        assert count == 0
        assert len(get_plugins("canadahelps")) == 0

    def test_load_whitelisted_plugin(self, tmp_path):
        """Test loading a plugin listed in plugins.yaml."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "test_plugin.py", "test_plugin")
        _write_whitelist(plugins_dir, ["test_plugin"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
        assert plugins[0][0] == "test_plugin"

    def test_unlisted_plugin_not_loaded(self, tmp_path):
        """Test that files not in the whitelist do not load."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "listed.py", "listed_plugin")
        _write_plugin(plugins_dir, "unlisted.py", "unlisted_plugin")
        _write_whitelist(plugins_dir, ["listed"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
        assert plugins[0][0] == "listed_plugin"

    def test_underscore_prefix_has_no_loader_meaning(self, tmp_path):
        """Test that a whitelisted _-prefixed file loads and an unlisted plain file does not."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "_reference_copy.py", "reference_plugin")
        _write_plugin(plugins_dir, "live_but_unlisted.py", "unlisted_plugin")
        _write_whitelist(plugins_dir, ["_reference_copy"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
        assert plugins[0][0] == "reference_plugin"

    def test_whitelisted_name_without_file_warns_and_skips(self, tmp_path, caplog):
        """Test that a whitelisted name with no matching file warns but does not fail."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "present.py", "present_plugin")
        _write_whitelist(plugins_dir, ["present", "missing_plugin"])

        count = load_plugins("canadahelps", plugins_dir)

        assert count == 1
        assert "Whitelisted plugin has no matching file" in caplog.text
        assert "missing_plugin" in caplog.text

    def test_enabled_names_overrides_whitelist_file(self, tmp_path):
        """Test that an explicit enabled_names list wins over plugins.yaml."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "from_file.py", "file_plugin")
        _write_plugin(plugins_dir, "from_arg.py", "arg_plugin")
        _write_whitelist(plugins_dir, ["from_file"])

        count = load_plugins("canadahelps", plugins_dir, enabled_names=["from_arg"])
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
        assert plugins[0][0] == "arg_plugin"

    def test_enabled_names_empty_list_loads_nothing(self, tmp_path):
        """Test that an explicit empty enabled_names loads nothing even with a whitelist file."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "from_file.py", "file_plugin")
        _write_whitelist(plugins_dir, ["from_file"])

        count = load_plugins("canadahelps", plugins_dir, enabled_names=[])

        assert count == 0
        assert len(get_plugins("canadahelps")) == 0

    def test_load_multiple_plugins(self, tmp_path):
        """Test loading multiple whitelisted plugin files."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "01_plugin.py", "plugin_one")
        _write_plugin(plugins_dir, "02_plugin.py", "plugin_two", plugin_type="field_processor")
        _write_whitelist(plugins_dir, ["01_plugin", "02_plugin"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 2

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 2

    def test_load_plugins_alphabetical_order_ignores_whitelist_order(self, tmp_path):
        """Test that load order is alphabetical by filename, not whitelist order."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "z_last.py", "plugin_z")
        _write_plugin(plugins_dir, "a_first.py", "plugin_a")
        _write_whitelist(plugins_dir, ["z_last", "a_first"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 2

        plugins = get_plugins("canadahelps", "row_transformer")
        assert plugins[0][0] == "plugin_a"
        assert plugins[1][0] == "plugin_z"

    def test_load_plugin_with_syntax_error(self, tmp_path, caplog):
        """Test that plugin with syntax error is logged and skipped."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        bad_plugin = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def bad_plugin(row_data: dict) -> dict:
    return this is invalid syntax
'''
        (plugins_dir / "bad_plugin.py").write_text(bad_plugin)
        _write_whitelist(plugins_dir, ["bad_plugin"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 0

        assert "Error loading plugin" in caplog.text

    def test_load_plugin_with_import_error(self, tmp_path, caplog):
        """Test that plugin with import error is logged and skipped."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        bad_import = '''
from nonexistent_module import something

@register_plugin("canadahelps", "row_transformer")
def plugin(row_data: dict) -> dict:
    return row_data
'''
        (plugins_dir / "bad_import.py").write_text(bad_import)
        _write_whitelist(plugins_dir, ["bad_import"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 0

        assert "Error loading plugin" in caplog.text

    def test_load_plugin_without_registration(self, tmp_path):
        """Test loading a valid Python file that doesn't register any plugins."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        no_registration = '''
def some_function():
    return "hello"
'''
        (plugins_dir / "no_reg.py").write_text(no_registration)
        _write_whitelist(plugins_dir, ["no_reg"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 0

    def test_load_plugins_multiple_registrations_in_file(self, tmp_path):
        """Test loading plugin file with multiple registrations."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        multi_plugin = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def transformer(row_data: dict) -> dict:
    return row_data

@register_plugin("canadahelps", "field_processor")
def processor(field_name: str, value, row_data: dict):
    return value
'''
        (plugins_dir / "multi.py").write_text(multi_plugin)
        _write_whitelist(plugins_dir, ["multi"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 2

    def test_load_plugins_for_different_adapters(self, tmp_path):
        """Test loading plugins for different adapters from separate directories."""
        ch_dir = tmp_path / "canadahelps"
        pp_dir = tmp_path / "paypal"
        ch_dir.mkdir()
        pp_dir.mkdir()

        _write_plugin(ch_dir, "ch.py", "ch_plugin", adapter="canadahelps")
        _write_plugin(pp_dir, "pp.py", "pp_plugin", adapter="paypal")
        _write_whitelist(ch_dir, ["ch"])
        _write_whitelist(pp_dir, ["pp"])

        ch_count = load_plugins("canadahelps", ch_dir)
        pp_count = load_plugins("paypal", pp_dir)

        assert ch_count == 1
        assert pp_count == 1

        ch_plugins = get_plugins("canadahelps")
        pp_plugins = get_plugins("paypal")

        assert len(ch_plugins) == 1
        assert len(pp_plugins) == 1
        assert ch_plugins[0][0] == "ch_plugin"
        assert pp_plugins[0][0] == "pp_plugin"

    def test_load_plugin_bundle_returns_resolved_plugins(self, tmp_path):
        """Test that loader can return an explicit bundle snapshot."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("paypal", "person_lookup")
def fallback_lookup(donation, people_client, default_lookup):
    return default_lookup()
'''
        (plugins_dir / "lookup.py").write_text(plugin_code)
        _write_whitelist(plugins_dir, ["lookup"])

        bundle = load_plugin_bundle("paypal", plugins_dir)

        assert [name for name, _func in bundle.all_plugins] == ["fallback_lookup"]
        assert [name for name, _func in bundle.by_type["person_lookup"]] == ["fallback_lookup"]

    def test_load_plugin_bundle_missing_whitelist_returns_empty_bundle(self, tmp_path, caplog):
        """Test that the bundle path honours the no-whitelist-no-plugins rule."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "test_plugin.py", "test_plugin", adapter="paypal")

        bundle = load_plugin_bundle("paypal", plugins_dir)

        assert bundle.all_plugins == []
        assert "Plugin whitelist not found" in caplog.text

    def test_load_plugin_bundle_enabled_names_override(self, tmp_path):
        """Test that the bundle path accepts an explicit enabled_names whitelist."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()
        _write_plugin(plugins_dir, "_reference.py", "reference_plugin", adapter="paypal")

        bundle = load_plugin_bundle("paypal", plugins_dir, enabled_names=["_reference"])

        assert [name for name, _func in bundle.all_plugins] == ["reference_plugin"]

    def test_load_plugins_ignores_non_py_files(self, tmp_path):
        """Test that non-.py files are ignored."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "readme.txt").write_text("This is a readme")
        _write_plugin(plugins_dir, "plugin.py", "plugin")
        _write_whitelist(plugins_dir, ["plugin"])

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
