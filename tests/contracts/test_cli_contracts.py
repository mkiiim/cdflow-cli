import sys
from unittest.mock import patch

import pytest

from cdflow_cli.cli.main import main


class TestCLIContracts:
    """Behavior-first contracts for the top-level CLI surface."""

    def test_help_lists_supported_subcommands(self, capsys):
        with patch.object(sys, "argv", ["cdflow", "--help"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "init" in captured.out
        assert "import" in captured.out
        assert "rollback" in captured.out

    def test_version_prints_cdflow_and_exits_zero(self, capsys):
        with patch.object(sys, "argv", ["cdflow", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 0
        assert "cdflow" in captured.out

    def test_no_command_shows_usage_and_exits_nonzero(self, capsys):
        with patch.object(sys, "argv", ["cdflow"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 1
        assert "usage:" in captured.out.lower()

    def test_import_rejects_type_without_file(self, capsys):
        with patch.object(sys, "argv", ["cdflow", "import", "--type", "canadahelps"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        captured = capsys.readouterr()
        assert exc_info.value.code == 2
        assert "--type and --file must be used together or not at all" in captured.err

    def test_import_accepts_type_and_file_pair(self):
        with patch("cdflow_cli.cli.main.import_main") as mock_import_main:
            with patch.object(
                sys,
                "argv",
                ["cdflow", "import", "--type", "paypal", "--file", "sample.csv"],
            ):
                main()

        mock_import_main.assert_called_once_with()

    def test_rollback_uses_public_command_path(self):
        with patch("cdflow_cli.cli.main.rollback_main") as mock_rollback_main:
            with patch.object(sys, "argv", ["cdflow", "rollback"]):
                main()

        mock_rollback_main.assert_called_once_with()
