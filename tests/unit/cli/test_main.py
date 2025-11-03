import pytest
import sys
from unittest.mock import patch, MagicMock
from cdflow_cli.cli.main import main, get_version, PackageNotFoundError


class TestMainCLI:
    """Test the main CLI entry point."""
    
    def test_get_version_with_installed_package(self):
        """Test version retrieval for installed package."""
        with patch('cdflow_cli.cli.main.version') as mock_version:
            mock_version.return_value = "1.6.8"
            assert get_version() == "1.6.8"
    
    def test_get_version_package_not_found(self):
        """Test version when package not found."""
        with patch('cdflow_cli.cli.main.version') as mock_version:
            mock_version.side_effect = PackageNotFoundError("not installed")
            assert "unknown" in get_version()
    
    def test_get_version_no_importlib(self):
        """Test version when importlib.metadata unavailable."""
        with patch('cdflow_cli.cli.main.version', None):
            result = get_version()
            assert "unknown" in result and "not available" in result
    
    def test_main_no_args_shows_help(self):
        """Test main with no arguments shows help."""
        test_args = ['cdflow']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
    
    def test_main_version_flag(self):
        """Test --version flag."""
        test_args = ['cdflow', '--version']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
    
    @patch('cdflow_cli.cli.main.init_main')
    def test_main_init_command(self, mock_init_main):
        """Test init command dispatch."""
        test_args = ['cdflow', 'init']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_init_main.assert_called_once()
    
    @patch('cdflow_cli.cli.main.import_main')
    def test_main_import_command(self, mock_import_main):
        """Test import command dispatch."""
        test_args = ['cdflow', 'import', '--config', 'test.yaml']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
    
    @patch('cdflow_cli.cli.main.rollback_main')
    def test_main_rollback_command(self, mock_rollback_main):
        """Test rollback command dispatch."""
        test_args = ['cdflow', 'rollback', '--config', 'test.yaml']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_rollback_main.assert_called_once()
    
    def test_import_type_file_validation(self):
        """Test that --type and --file must be used together."""
        test_args = ['cdflow', 'import', '--type', 'canadahelps']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
        
        test_args = ['cdflow', 'import', '--file', 'test.csv']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 2
    
    @patch('cdflow_cli.cli.main.import_main')
    def test_import_with_type_and_file(self, mock_import_main):
        """Test import with both --type and --file."""
        test_args = ['cdflow', 'import', '--type', 'canadahelps', '--file', 'test.csv', '--config', 'config.yaml']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
