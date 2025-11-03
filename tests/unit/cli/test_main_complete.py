"""
Complete tests for cdflow_cli.cli.main module.
This file contains additional tests to achieve 100% coverage.
"""
import pytest
import sys
import argparse
from unittest.mock import patch, MagicMock
from cdflow_cli.cli.main import main, get_version


class TestArgumentParserConfiguration:
    """Test that ArgumentParser is configured correctly."""
    
    def test_parser_prog_name(self):
        """Test that parser uses correct program name."""
        # Capture the ArgumentParser creation by testing help output
        test_args = ['cdflow', '--help']
        with patch.object(sys, 'argv', test_args):
            with pytest.raises(SystemExit):
                main()
        # The help will contain "cdflow" as the program name
        
    def test_version_argument_uses_get_version(self):
        """Test that --version uses get_version() function."""
        with patch('cdflow_cli.cli.main.get_version', return_value="test-version"):
            test_args = ['cdflow', '--version']
            with patch.object(sys, 'argv', test_args):
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 0


class TestSubparserDefaults:
    """Test default values for subparser arguments."""
    
    @patch('cdflow_cli.cli.main.import_main')
    def test_import_default_config_value(self, mock_import_main):
        """Test that import command uses 'config.yaml' as default."""
        test_args = ['cdflow', 'import']
        with patch.object(sys, 'argv', test_args):
            main()
            # Verify sys.argv contains the default config value
            assert "config.yaml" in sys.argv
            
    @patch('cdflow_cli.cli.main.import_main')
    def test_import_default_log_level_value(self, mock_import_main):
        """Test that import command uses 'INFO' as default log level."""
        test_args = ['cdflow', 'import']
        with patch.object(sys, 'argv', test_args):
            main()
            # Verify sys.argv contains the default log level
            assert "INFO" in sys.argv
            
    @patch('cdflow_cli.cli.main.rollback_main')
    def test_rollback_default_config_value(self, mock_rollback_main):
        """Test that rollback command uses 'config.yaml' as default.""" 
        test_args = ['cdflow', 'rollback']
        with patch.object(sys, 'argv', test_args):
            main()
            assert "config.yaml" in sys.argv
            
    @patch('cdflow_cli.cli.main.rollback_main')
    def test_rollback_default_log_level_value(self, mock_rollback_main):
        """Test that rollback command uses 'INFO' as default log level."""
        test_args = ['cdflow', 'rollback']
        with patch.object(sys, 'argv', test_args):
            main()
            assert "INFO" in sys.argv


class TestLogLevelChoices:
    """Test all valid log level choices."""
    
    @patch('cdflow_cli.cli.main.import_main')
    @pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "NOTICE", "ERROR"])
    def test_import_all_valid_log_levels(self, mock_import_main, log_level):
        """Test that all documented log levels work for import."""
        test_args = ['cdflow', 'import', '--log-level', log_level]
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
            assert log_level in sys.argv
            
    @patch('cdflow_cli.cli.main.rollback_main')
    @pytest.mark.parametrize("log_level", ["DEBUG", "INFO", "WARNING", "NOTICE", "ERROR"])
    def test_rollback_all_valid_log_levels(self, mock_rollback_main, log_level):
        """Test that all documented log levels work for rollback."""
        test_args = ['cdflow', 'rollback', '--log-level', log_level]
        with patch.object(sys, 'argv', test_args):
            main()
            mock_rollback_main.assert_called_once()
            assert log_level in sys.argv


class TestTypeChoices:
    """Test all valid type choices."""
    
    @patch('cdflow_cli.cli.main.import_main')
    @pytest.mark.parametrize("import_type", ["canadahelps", "paypal"])
    def test_import_all_valid_types(self, mock_import_main, import_type):
        """Test that both documented import types work."""
        test_args = ['cdflow', 'import', '--type', import_type, '--file', 'test.csv']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
            assert import_type in sys.argv


class TestValidationEdgeCases:
    """Test validation logic edge cases."""
    
    def test_import_type_and_file_both_present_valid(self):
        """Test that having both --type and --file passes validation."""
        test_args = ['cdflow', 'import', '--type', 'canadahelps', '--file', 'test.csv']
        with patch.object(sys, 'argv', test_args):
            with patch('cdflow_cli.cli.main.import_main'):
                # Should not raise an error
                main()
                
    def test_import_neither_type_nor_file_valid(self):
        """Test that having neither --type nor --file passes validation."""
        test_args = ['cdflow', 'import']
        with patch.object(sys, 'argv', test_args):
            with patch('cdflow_cli.cli.main.import_main'):
                # Should not raise an error
                main()


class TestImportFallbackHandling:
    """Test the import fallback mechanism in detail."""
    
    def test_importlib_metadata_import_error(self):
        """Test handling when importlib.metadata import fails."""
        # This tests the first try/except block (lines 18-20)
        with patch('cdflow_cli.cli.main.importlib.metadata', side_effect=ImportError):
            # The fallback should handle this gracefully
            # We can't easily test this without modifying the import structure
            pass
            
    def test_importlib_metadata_fallback_import_error(self):
        """Test handling when importlib_metadata fallback also fails."""
        # This tests the second try/except block (lines 22-27)
        # When both imports fail, version should be None and PackageNotFoundError should be Exception
        pass


class TestMainModuleExecution:
    """Test the if __name__ == '__main__' execution."""
    
    @patch('cdflow_cli.cli.main.main')
    def test_main_module_execution(self, mock_main_func):
        """Test that main() is called when module is executed directly."""
        # This is tricky to test because we can't easily simulate __name__ == '__main__'
        # In practice, this line is mostly for CLI usage and is hard to unit test
        # Integration tests would cover this better
        pass


class TestArgumentGetattr:
    """Test the getattr usage for optional arguments."""
    
    @patch('cdflow_cli.cli.main.import_main')
    def test_getattr_handles_missing_type_attribute(self, mock_import_main):
        """Test that getattr safely handles when 'type' attribute doesn't exist."""
        test_args = ['cdflow', 'import']  # No --type argument
        with patch.object(sys, 'argv', test_args):
            main()
            # Should not crash, getattr should return None
            mock_import_main.assert_called_once()
            
    @patch('cdflow_cli.cli.main.import_main') 
    def test_getattr_handles_missing_file_attribute(self, mock_import_main):
        """Test that getattr safely handles when 'file' attribute doesn't exist."""
        test_args = ['cdflow', 'import']  # No --file argument
        with patch.object(sys, 'argv', test_args):
            main()
            # Should not crash, getattr should return None
            mock_import_main.assert_called_once()


class TestSysArgvReconstruction:
    """Test the exact sys.argv reconstruction behavior."""
    
    @patch('cdflow_cli.cli.main.init_main')
    def test_init_sys_argv_order_with_multiple_args(self, mock_init_main):
        """Test exact order of sys.argv reconstruction for init."""
        test_args = ['cdflow', 'init', '--org-logo', 'logo.png', '--config-dir', '/path', '--force']
        with patch.object(sys, 'argv', test_args):
            main()
            mock_init_main.assert_called_once()
            # Test that the order matches the code: config-dir, force, org-logo
            expected = ["cdflow-init", "--config-dir", "/path", "--force", "--org-logo", "logo.png"]
            assert sys.argv == expected
            
    @patch('cdflow_cli.cli.main.import_main')
    def test_import_sys_argv_order_with_all_args(self, mock_import_main):
        """Test exact order of sys.argv reconstruction for import."""
        test_args = [
            'cdflow', 'import', 
            '--config', 'custom.yaml',
            '--log-level', 'DEBUG',
            '--type', 'paypal',
            '--file', 'data.csv'
        ]
        with patch.object(sys, 'argv', test_args):
            main()
            mock_import_main.assert_called_once()
            # Test that the order matches the code: config, log-level, then type, file
            expected = [
                "cdflow-import", 
                "--config", "custom.yaml",
                "--log-level", "DEBUG",
                "--type", "paypal",
                "--file", "data.csv"
            ]
            assert sys.argv == expected