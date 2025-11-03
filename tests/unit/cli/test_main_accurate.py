"""
Comprehensive tests for cdflow_cli.cli.main module.
Based on actual examination of the source code.
"""
import pytest
import sys
from unittest.mock import patch, MagicMock
from cdflow_cli.cli.main import main, get_version


class TestGetVersion:
    """Test the get_version function with all scenarios."""
    
    def test_get_version_with_importlib_metadata_success(self):
        """Test version retrieval when importlib.metadata works."""
        with patch('cdflow_cli.cli.main.version') as mock_version:
            mock_version.return_value = "1.6.8"
            result = get_version()
            assert result == "1.6.8"
            mock_version.assert_called_once_with("cdflow-cli")
    
    def test_get_version_package_not_found(self):
        """Test version when PackageNotFoundError is raised."""
        with patch('cdflow_cli.cli.main.version') as mock_version:
            from cdflow_cli.cli.main import PackageNotFoundError
            mock_version.side_effect = PackageNotFoundError("Package not found")
            result = get_version()
            assert result == "unknown (development)"
    
    def test_get_version_no_importlib_metadata(self):
        """Test version when importlib.metadata is not available."""
        with patch('cdflow_cli.cli.main.version', None):
            result = get_version()
            assert result == "unknown (importlib.metadata not available)"


class TestMainCLIArgParsing:
    """Test the main function's argument parsing logic."""
    
    def test_main_no_args_shows_help(self):
        """Test that running with no command shows help and exits."""
        test_args = ['cdflow']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1
    
    def test_main_version_flag(self):
        """Test --version flag triggers version output and exit."""
        test_args = ['cdflow', '--version']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # argparse exits with 0 for --version
            assert exc_info.value.code == 0


class TestMainSubcommandDispatch:
    """Test main function's subcommand dispatching."""
    
    @patch('cdflow_cli.cli.main.init_main')
    def test_main_init_command_basic(self, mock_init_main):
        """Test init command with no additional arguments."""
        test_args = ['cdflow', 'init']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_init_main.assert_called_once()
            # Check that sys.argv was reconstructed correctly
            assert sys.argv == ["cdflow-init"]
    
    @patch('cdflow_cli.cli.main.init_main')
    def test_main_init_command_with_config_dir(self, mock_init_main):
        """Test init command with --config-dir argument."""
        test_args = ['cdflow', 'init', '--config-dir', '/custom/path']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_init_main.assert_called_once()
            # Check sys.argv reconstruction includes config-dir
            expected_argv = ["cdflow-init", "--config-dir", "/custom/path"]
            assert sys.argv == expected_argv
    
    @patch('cdflow_cli.cli.main.init_main')
    def test_main_init_command_with_force_and_logo(self, mock_init_main):
        """Test init command with --force and --org-logo arguments."""
        test_args = ['cdflow', 'init', '--force', '--org-logo', 'logo.png']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_init_main.assert_called_once()
            # Check sys.argv reconstruction includes all options
            expected_argv = ["cdflow-init", "--force", "--org-logo", "logo.png"]
            assert sys.argv == expected_argv
    
    @patch('cdflow_cli.cli.main.import_main')
    def test_main_import_command_basic(self, mock_import_main):
        """Test import command with default arguments."""
        test_args = ['cdflow', 'import']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
            # Check default sys.argv reconstruction
            expected_argv = ["cdflow-import", "--config", "config.yaml", "--log-level", "INFO"]
            assert sys.argv == expected_argv
    
    @patch('cdflow_cli.cli.main.import_main')
    def test_main_import_command_with_custom_config_and_log_level(self, mock_import_main):
        """Test import command with custom config and log level."""
        test_args = ['cdflow', 'import', '--config', 'custom.yaml', '--log-level', 'DEBUG']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
            expected_argv = ["cdflow-import", "--config", "custom.yaml", "--log-level", "DEBUG"]
            assert sys.argv == expected_argv
    
    @patch('cdflow_cli.cli.main.import_main')
    def test_main_import_command_with_type_and_file(self, mock_import_main):
        """Test import command with --type and --file arguments."""
        test_args = ['cdflow', 'import', '--type', 'canadahelps', '--file', 'donations.csv']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
            expected_argv = [
                "cdflow-import", "--config", "config.yaml", "--log-level", "INFO", 
                "--type", "canadahelps", "--file", "donations.csv"
            ]
            assert sys.argv == expected_argv
    
    @patch('cdflow_cli.cli.main.rollback_main')
    def test_main_rollback_command_basic(self, mock_rollback_main):
        """Test rollback command with default arguments."""
        test_args = ['cdflow', 'rollback']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_rollback_main.assert_called_once()
            expected_argv = ["cdflow-rollback", "--config", "config.yaml", "--log-level", "INFO"]
            assert sys.argv == expected_argv
    
    @patch('cdflow_cli.cli.main.rollback_main')
    def test_main_rollback_command_with_custom_config(self, mock_rollback_main):
        """Test rollback command with custom config and log level."""
        test_args = ['cdflow', 'rollback', '--config', 'rollback.yaml', '--log-level', 'ERROR']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_rollback_main.assert_called_once()
            expected_argv = ["cdflow-rollback", "--config", "rollback.yaml", "--log-level", "ERROR"]
            assert sys.argv == expected_argv


class TestMainValidation:
    """Test the validation logic in main function."""
    
    def test_import_type_without_file_raises_error(self):
        """Test that --type without --file raises an error."""
        test_args = ['cdflow', 'import', '--type', 'canadahelps']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # argparse.error() calls sys.exit(2)
            assert exc_info.value.code == 2
    
    def test_import_file_without_type_raises_error(self):
        """Test that --file without --type raises an error."""
        test_args = ['cdflow', 'import', '--file', 'donations.csv']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # argparse.error() calls sys.exit(2)
            assert exc_info.value.code == 2
    
    def test_import_valid_type_choices(self):
        """Test that only valid choices are accepted for --type."""
        # Test invalid type choice
        test_args = ['cdflow', 'import', '--type', 'invalid_type', '--file', 'test.csv']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Invalid choice causes argparse to exit with code 2
            assert exc_info.value.code == 2
    
    def test_import_valid_log_level_choices(self):
        """Test that only valid choices are accepted for --log-level."""
        # Test invalid log level choice
        test_args = ['cdflow', 'import', '--log-level', 'INVALID']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Invalid choice causes argparse to exit with code 2
            assert exc_info.value.code == 2


class TestMainEdgeCases:
    """Test edge cases and error conditions."""
    
    @patch('cdflow_cli.cli.main.init_main')
    def test_main_init_with_all_options(self, mock_init_main):
        """Test init command with all possible options."""
        test_args = [
            'cdflow', 'init', 
            '--config-dir', '/custom/dir',
            '--org-logo', '/path/to/logo.png',
            '--force'
        ]
        with patch.object(sys, 'argv', test_args):
            main()
            mock_init_main.assert_called_once()
            expected_argv = [
                "cdflow-init", 
                "--config-dir", "/custom/dir",
                "--force",
                "--org-logo", "/path/to/logo.png"
            ]
            assert sys.argv == expected_argv
    
    def test_main_unknown_command(self):
        """Test that unknown commands show help and exit."""
        test_args = ['cdflow', 'unknown_command']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            # Unknown subcommand causes argparse to exit with code 2
            assert exc_info.value.code == 2


class TestMainIntegration:
    """Integration-style tests that test multiple components together."""
    
    def test_version_integration(self):
        """Test that version function integrates properly with argparse."""
        # This test doesn't mock the version function to test integration
        test_args = ['cdflow', '--version']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0
    
    @patch('cdflow_cli.cli.main.import_main')
    def test_paypal_import_integration(self, mock_import_main):
        """Test PayPal import command integration."""
        test_args = [
            'cdflow', 'import',
            '--type', 'paypal', 
            '--file', 'paypal_data.csv',
            '--config', 'paypal_config.yaml',
            '--log-level', 'WARNING'
        ]
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
            expected_argv = [
                "cdflow-import", 
                "--config", "paypal_config.yaml", 
                "--log-level", "WARNING",
                "--type", "paypal", 
                "--file", "paypal_data.csv"
            ]
            assert sys.argv == expected_argv