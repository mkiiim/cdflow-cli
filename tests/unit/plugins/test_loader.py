import pytest
from pathlib import Path
from cdflow_cli.plugins.loader import load_plugins
from cdflow_cli.plugins.registry import get_plugins, clear_registry


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

    def test_load_plugins_empty_directory(self, tmp_path):
        """Test loading plugins from empty directory."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 0

    def test_load_single_plugin(self, tmp_path):
        """Test loading a single plugin file."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def test_plugin(row_data: dict) -> dict:
    return row_data
'''
        plugin_file = plugins_dir / "test_plugin.py"
        plugin_file.write_text(plugin_code)

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
        assert plugins[0][0] == "test_plugin"

    def test_load_multiple_plugins(self, tmp_path):
        """Test loading multiple plugin files."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin1_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def plugin_one(row_data: dict) -> dict:
    return row_data
'''
        plugin2_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "field_processor")
def plugin_two(field_name: str, value, row_data: dict):
    return value
'''
        (plugins_dir / "01_plugin.py").write_text(plugin1_code)
        (plugins_dir / "02_plugin.py").write_text(plugin2_code)

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 2

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 2

    def test_load_plugins_alphabetical_order(self, tmp_path):
        """Test that plugins are loaded in alphabetical order."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        execution_order = []

        plugin_a = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def plugin_a(row_data: dict) -> dict:
    return row_data
'''
        plugin_z = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def plugin_z(row_data: dict) -> dict:
    return row_data
'''
        (plugins_dir / "z_last.py").write_text(plugin_z)
        (plugins_dir / "a_first.py").write_text(plugin_a)

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 2

        plugins = get_plugins("canadahelps", "row_transformer")
        assert plugins[0][0] == "plugin_a"
        assert plugins[1][0] == "plugin_z"

    def test_skip_disabled_plugins(self, tmp_path):
        """Test that plugins starting with underscore are skipped."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        enabled_plugin = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def enabled_plugin(row_data: dict) -> dict:
    return row_data
'''
        disabled_plugin = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def disabled_plugin(row_data: dict) -> dict:
    return row_data
'''
        (plugins_dir / "enabled.py").write_text(enabled_plugin)
        (plugins_dir / "_disabled.py").write_text(disabled_plugin)

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
        assert plugins[0][0] == "enabled_plugin"

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

        ch_plugin = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def ch_plugin(row_data: dict) -> dict:
    return row_data
'''
        pp_plugin = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("paypal", "row_transformer")
def pp_plugin(row_data: dict) -> dict:
    return row_data
'''
        (ch_dir / "ch.py").write_text(ch_plugin)
        (pp_dir / "pp.py").write_text(pp_plugin)

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

    def test_load_plugins_ignores_non_py_files(self, tmp_path):
        """Test that non-.py files are ignored."""
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        (plugins_dir / "readme.txt").write_text("This is a readme")
        (plugins_dir / "config.yaml").write_text("config: value")

        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("canadahelps", "row_transformer")
def plugin(row_data: dict) -> dict:
    return row_data
'''
        (plugins_dir / "plugin.py").write_text(plugin_code)

        count = load_plugins("canadahelps", plugins_dir)
        assert count == 1

        plugins = get_plugins("canadahelps")
        assert len(plugins) == 1
