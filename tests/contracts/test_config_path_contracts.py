from pathlib import Path
from unittest.mock import patch

from cdflow_cli.utils.config_paths import resolve_config_path


class TestConfigPathContracts:
    """Behavior-first contracts for config path resolution."""

    def test_bare_filename_resolves_under_xdg_cdflow_directory(self):
        fake_config_home = Path("/tmp/cdflow-config-home")

        with patch.dict("os.environ", {"XDG_CONFIG_HOME": str(fake_config_home)}, clear=False):
            resolved = resolve_config_path("config.yaml")

        assert resolved == fake_config_home / "cdflow" / "config.yaml"

    def test_explicit_relative_path_resolves_from_current_working_directory(self):
        with patch("pathlib.Path.resolve", return_value=Path("/worktree/configs/local.yaml")):
            resolved = resolve_config_path("./configs/local.yaml")

        assert resolved == Path("/worktree/configs/local.yaml")

    def test_absolute_path_is_preserved(self):
        absolute_path = Path("/etc/cdflow/config.yaml")

        resolved = resolve_config_path(absolute_path)

        assert resolved == absolute_path
