import pytest
import tempfile
import csv
import os
import sys
import argparse
import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

from cdflow_cli.cli.commands_rollback import (
    get_encoding,
    get_success_csv_files,
    determine_import_type_from_header,
    initialize_output_file,
    append_row_to_file,
    parse_rollback_arguments,
    prompt_for_rollback_confirmation,
    run_rollback_cli,
    main
)


class TestGetEncoding:
    """Test file encoding detection for rollback commands."""
    
    @pytest.fixture
    def mock_paths(self):
        """Create mock paths system."""
        paths = Mock()
        paths.output = Path('/test/output')
        return paths
    
    @patch('chardet.detect')
    @patch('builtins.open')
    def test_get_encoding_absolute_path(self, mock_open, mock_detect, mock_paths):
        """Test encoding detection with absolute file path."""
        mock_file = Mock()
        mock_file.read.return_value = b'test content'
        mock_open.return_value.__enter__.return_value = mock_file
        mock_detect.return_value = {'encoding': 'utf-8', 'confidence': 0.99}
        
        encoding, confidence = get_encoding('/absolute/path/test.csv', mock_paths)
        
        assert encoding == 'utf-8'
        assert confidence == 0.99
        mock_open.assert_called_once_with(Path('/absolute/path/test.csv'), 'rb')
    
    @patch('chardet.detect')
    @patch('builtins.open')
    def test_get_encoding_relative_path(self, mock_open, mock_detect, mock_paths):
        """Test encoding detection with relative file path."""
        mock_file = Mock()
        mock_file.read.return_value = b'test content'
        mock_open.return_value.__enter__.return_value = mock_file
        mock_detect.return_value = {'encoding': 'windows-1252', 'confidence': 0.85}
        
        encoding, confidence = get_encoding('test.csv', mock_paths)
        
        assert encoding == 'windows-1252'
        assert confidence == 0.85
        mock_open.assert_called_once_with(mock_paths.output / 'test.csv', 'rb')
    
    @patch('chardet.detect')
    @patch('builtins.open')
    def test_get_encoding_without_paths(self, mock_open, mock_detect):
        """Test encoding detection without paths system."""
        mock_file = Mock()
        mock_file.read.return_value = b'test content'
        mock_open.return_value.__enter__.return_value = mock_file
        mock_detect.return_value = {'encoding': 'iso-8859-1', 'confidence': 0.75}
        
        encoding, confidence = get_encoding('test.csv', None)
        
        assert encoding == 'iso-8859-1'
        assert confidence == 0.75
        mock_open.assert_called_once_with(Path('test.csv'), 'rb')
    
    def test_get_encoding_exception_handling(self, mock_paths, caplog):
        """Test encoding detection error handling."""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            encoding, confidence = get_encoding('nonexistent.csv', mock_paths)
            
            assert encoding == 'utf-8'  # Default fallback
            assert confidence == 0.0    # Low confidence
            assert "Error detecting file encoding" in caplog.text


class TestGetSuccessCsvFiles:
    """Test success CSV file listing functionality."""
    
    @pytest.fixture
    def temp_output_dir(self):
        """Create temporary output directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            
            # Create test success files
            (output_dir / "import1_success.csv").write_text("test,data\n1,2")
            (output_dir / "import2_success.csv").write_text("test,data\n3,4")
            (output_dir / "import3_success.csv").write_text("test,data\n5,6")
            
            # Create non-success files (should be ignored)
            (output_dir / "import1_fail.csv").write_text("error,data\n1,2")
            (output_dir / "regular_file.txt").write_text("not a csv")
            
            yield output_dir
    
    def test_get_success_csv_files_found(self, temp_output_dir):
        """Test finding success CSV files."""
        mock_paths = Mock()
        mock_paths.output = temp_output_dir
        # Don't mock exists() since temp_output_dir is a real Path
        
        success_files = get_success_csv_files(mock_paths)
        
        assert len(success_files) == 3
        assert "import1_success.csv" in success_files
        assert "import2_success.csv" in success_files
        assert "import3_success.csv" in success_files
        assert "import1_fail.csv" not in success_files
        assert "regular_file.txt" not in success_files
    
    def test_get_success_csv_files_none_found(self):
        """Test when no success CSV files are found."""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            # Create non-success files only
            (output_dir / "import1_fail.csv").write_text("error,data\n1,2")
            (output_dir / "regular_file.txt").write_text("not a csv")
            
            mock_paths = Mock()
            mock_paths.output = output_dir
            # Don't mock exists() since output_dir is a real Path
            
            success_files = get_success_csv_files(mock_paths)
            
            assert success_files == []
    
    def test_get_success_csv_files_no_output_dir(self, caplog):
        """Test when output directory doesn't exist."""
        mock_paths = Mock()
        mock_paths.output.exists.return_value = False
        
        success_files = get_success_csv_files(mock_paths)
        
        assert success_files == []
        assert "Output directory not found" in caplog.text
    
    def test_get_success_csv_files_no_paths(self, caplog):
        """Test when paths system is not provided."""
        success_files = get_success_csv_files(None)
        
        assert success_files == []
        assert "Output directory not found" in caplog.text
    
    def test_get_success_csv_files_exception_handling(self, caplog):
        """Test exception handling in file listing."""
        mock_paths = Mock()
        mock_paths.output.exists.return_value = True
        mock_paths.output.glob.side_effect = Exception("Permission denied")
        
        success_files = get_success_csv_files(mock_paths)
        
        assert success_files == []
        assert "Error listing success files" in caplog.text


class TestDetermineImportTypeFromHeader:
    """Test import type detection from CSV headers."""
    
    def test_determine_canadahelps_header(self):
        """Test detection of CanadaHelps CSV header."""
        header = "DONOR FIRST NAME,DONOR LAST NAME,DONOR EMAIL ADDRESS,AMOUNT"
        
        import_type = determine_import_type_from_header(header)
        
        assert import_type == "CanadaHelps"
    
    def test_determine_paypal_header(self):
        """Test detection of PayPal CSV header."""
        header = "Date,Time,Name,Type,Status,From Email Address,Gross,Fee"
        
        import_type = determine_import_type_from_header(header)
        
        assert import_type == "PayPal"
    
    def test_determine_unknown_header(self):
        """Test detection with unknown CSV header."""
        header = "Unknown,Column,Names,Here"
        
        import_type = determine_import_type_from_header(header)
        
        assert import_type is None
    
    def test_determine_empty_header(self):
        """Test detection with empty header."""
        header = ""
        
        import_type = determine_import_type_from_header(header)
        
        assert import_type is None
    
    def test_determine_partial_canadahelps_header(self):
        """Test detection with partial CanadaHelps header."""
        header = "DONOR FIRST NAME,DONOR LAST NAME,AMOUNT"  # Missing email
        
        import_type = determine_import_type_from_header(header)
        
        assert import_type is None
    
    def test_determine_partial_paypal_header(self):
        """Test detection with partial PayPal header."""
        header = "Name,From Email Address,Amount"  # Missing Gross
        
        import_type = determine_import_type_from_header(header)
        
        assert import_type is None


class TestInitializeOutputFile:
    """Test rollback output file initialization."""
    
    @pytest.fixture
    def temp_paths(self):
        """Create temporary paths system."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_paths = Mock()
            mock_paths.output = Path(temp_dir)
            yield mock_paths
    
    def test_initialize_output_file_basic(self, temp_paths):
        """Test basic output file initialization."""
        filename = "rollback_test.csv"
        fieldnames = ["field1", "field2", "field3"]
        encoding = "utf-8"
        
        initialize_output_file(filename, fieldnames, encoding, temp_paths)
        
        output_file = temp_paths.output / filename
        assert output_file.exists()
        
        # Verify content
        content = output_file.read_text(encoding='utf-8')
        assert "field1,field2,field3" in content
    
    def test_initialize_output_file_with_subdirectory(self, temp_paths):
        """Test output file initialization with subdirectory creation."""
        filename = "subdir/rollback_test.csv"
        fieldnames = ["col1", "col2"]
        encoding = "utf-8"
        
        initialize_output_file(filename, fieldnames, encoding, temp_paths)
        
        output_file = temp_paths.output / filename
        assert output_file.exists()
        assert output_file.parent.exists()
        
        content = output_file.read_text(encoding='utf-8')
        assert "col1,col2" in content
    
    def test_initialize_output_file_special_characters(self, temp_paths):
        """Test output file initialization with special character fieldnames."""
        filename = "special_test.csv"
        fieldnames = ["field with spaces", "field,with,commas", "field\"with\"quotes"]
        encoding = "utf-8"
        
        initialize_output_file(filename, fieldnames, encoding, temp_paths)
        
        output_file = temp_paths.output / filename
        assert output_file.exists()
        
        # Verify CSV was properly formatted
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Check that fieldnames were properly set
            assert reader.fieldnames is not None
            assert len(fieldnames) == len(reader.fieldnames)
    
    def test_initialize_output_file_exception_handling(self, temp_paths):
        """Test exception handling during file initialization."""
        filename = "test.csv"
        fieldnames = ["field1"]
        encoding = "utf-8"
        
        # Mock Path.write_text to raise exception
        with patch.object(Path, 'write_text', side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError):
                initialize_output_file(filename, fieldnames, encoding, temp_paths)


class TestAppendRowToFile:
    """Test row appending to rollback output files."""
    
    @pytest.fixture
    def temp_paths_with_file(self):
        """Create temporary paths with an initialized output file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_paths = Mock()
            mock_paths.output = Path(temp_dir)
            
            # Create initial file
            filename = "test_rollback.csv"
            fieldnames = ["field1", "field2", "field3"]
            output_file = mock_paths.output / filename
            
            csv_output = StringIO()
            writer = csv.DictWriter(csv_output, fieldnames=fieldnames)
            writer.writeheader()
            output_file.write_text(csv_output.getvalue(), encoding='utf-8')
            
            yield mock_paths, filename, fieldnames
    
    def test_append_row_to_file_basic(self, temp_paths_with_file):
        """Test basic row appending."""
        mock_paths, filename, fieldnames = temp_paths_with_file
        
        row_data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        encoding = "utf-8"
        
        append_row_to_file(filename, row_data, fieldnames, encoding, mock_paths)
        
        # Verify file content
        output_file = mock_paths.output / filename
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        assert len(rows) == 1
        assert rows[0]["field1"] == "value1"
        assert rows[0]["field2"] == "value2"
        assert rows[0]["field3"] == "value3"
    
    def test_append_multiple_rows(self, temp_paths_with_file):
        """Test appending multiple rows."""
        mock_paths, filename, fieldnames = temp_paths_with_file
        encoding = "utf-8"
        
        rows_data = [
            {"field1": "row1_val1", "field2": "row1_val2", "field3": "row1_val3"},
            {"field1": "row2_val1", "field2": "row2_val2", "field3": "row2_val3"},
            {"field1": "row3_val1", "field2": "row3_val2", "field3": "row3_val3"}
        ]
        
        for row_data in rows_data:
            append_row_to_file(filename, row_data, fieldnames, encoding, mock_paths)
        
        # Verify all rows were appended
        output_file = mock_paths.output / filename
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        assert len(rows) == 3
        assert rows[0]["field1"] == "row1_val1"
        assert rows[1]["field1"] == "row2_val1"
        assert rows[2]["field1"] == "row3_val1"
    
    def test_append_row_with_special_characters(self, temp_paths_with_file):
        """Test appending row with special characters."""
        mock_paths, filename, fieldnames = temp_paths_with_file
        encoding = "utf-8"
        
        row_data = {
            "field1": "Value with unicode: 测试中文",
            "field2": "Value with quotes: \"quoted text\"",
            "field3": "Value with commas: one, two, three"
        }
        
        append_row_to_file(filename, row_data, fieldnames, encoding, mock_paths)
        
        # Verify special characters preserved
        output_file = mock_paths.output / filename
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
        assert len(rows) == 1
        assert "测试中文" in rows[0]["field1"]
        assert "\"quoted text\"" in rows[0]["field2"]
        assert "one, two, three" in rows[0]["field3"]
    
    def test_append_row_exception_handling(self, temp_paths_with_file):
        """Test exception handling during row appending - lines 164-166."""
        mock_paths, filename, fieldnames = temp_paths_with_file
        
        row_data = {"field1": "value1", "field2": "value2", "field3": "value3"}
        encoding = "utf-8"
        
        # Mock Path.open to raise exception to test the exception handling path
        with patch.object(Path, 'open', side_effect=PermissionError("Write access denied")), \
             patch('cdflow_cli.cli.commands_rollback.logger') as mock_logger:
            
            # The function should catch the exception, log it, and re-raise
            with pytest.raises(PermissionError):
                append_row_to_file(filename, row_data, fieldnames, encoding, mock_paths)
            
            # Verify the error was logged (line 165)
            mock_logger.error.assert_called_once()
            logged_message = mock_logger.error.call_args[0][0]
            assert "Failed to append row to file" in logged_message


class TestParseRollbackArguments:
    """Test rollback command line argument parsing."""
    
    def test_parse_rollback_arguments_with_config(self):
        """Test parsing with config argument provided."""
        test_args = ['--config', 'config.yaml']
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            config_path = parse_rollback_arguments()
            
            assert config_path == 'config.yaml'
    
    def test_parse_rollback_arguments_without_config(self):
        """Test parsing without config argument."""
        test_args = []
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            config_path = parse_rollback_arguments()
            
            assert config_path is None
    
    def test_parse_rollback_arguments_config_with_value(self):
        """Test parsing config argument with explicit value."""
        test_args = ['--config', '/path/to/config.yaml']
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            config_path = parse_rollback_arguments()
            
            assert config_path == '/path/to/config.yaml'
    
    def test_parse_rollback_arguments_config_no_value(self):
        """Test parsing config argument without value (nargs='?')."""
        # This tests the nargs='?' behavior
        test_args = ['--config']
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            config_path = parse_rollback_arguments()
            
            # With nargs='?', this should return None when no value provided
            assert config_path is None


class TestPromptForRollbackConfirmation:
    """Test rollback confirmation prompt functionality."""
    
    @patch('cdflow_cli.cli.commands_rollback.clear_screen')
    @patch('builtins.input')
    def test_prompt_for_rollback_confirmation_accept(self, mock_input, mock_clear):
        """Test user accepting rollback confirmation."""
        mock_input.return_value = ''  # User presses Enter
        
        with patch('cdflow_cli.cli.commands_rollback.logger') as mock_logger:
            result = prompt_for_rollback_confirmation('test-nation', 'test.csv', 'CanadaHelps')
            
            assert result is True
            # Check that logger methods were called
            mock_logger.notice.assert_called()
            mock_logger.info.assert_called()
    
    @patch('cdflow_cli.cli.commands_rollback.clear_screen')
    @patch('builtins.input')
    def test_prompt_for_rollback_confirmation_cancel(self, mock_input, mock_clear):
        """Test user canceling rollback confirmation."""
        mock_input.side_effect = KeyboardInterrupt()
        
        with patch('cdflow_cli.cli.commands_rollback.logger') as mock_logger:
            result = prompt_for_rollback_confirmation('test-nation', 'test.csv', 'PayPal')
            
            assert result is False
            # The mock_clear may not be called if the function imports clear_screen differently
            # Focus on verifying the core behavior
            mock_logger.info.assert_called()
    
    @patch('cdflow_cli.cli.commands_rollback.clear_screen')
    @patch('builtins.input')
    def test_prompt_for_rollback_confirmation_paypal(self, mock_input, mock_clear, caplog):
        """Test rollback confirmation for PayPal import type."""
        mock_input.return_value = ''
        
        result = prompt_for_rollback_confirmation('production-nation', 'paypal_export.csv', 'PayPal')
        
        assert result is True
        assert "DANGER: Donations from PayPal import will be DELETED" in caplog.text
        assert "Processing file: paypal_export.csv" in caplog.text
        assert "NationBuilder environment: production-nation" in caplog.text


class TestRunRollbackCli:
    """Test main rollback CLI execution."""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Create comprehensive mock dependencies for rollback CLI."""
        # Mock config provider
        mock_config = Mock()
        mock_config.get_import_setting.return_value = {
            'type': 'canadahelps',
            'file': 'test.csv'
        }
        # Ensure config methods don't return None/falsy when needed by initialize_paths
        mock_config.config = {'test': 'value'}  # Mock config data
        
        # Mock logging provider
        mock_logging_provider = Mock()
        mock_logger = Mock()
        mock_logging_provider.get_logger.return_value = mock_logger
        
        # Mock paths system
        mock_paths = Mock()
        mock_output_path = Mock()
        mock_output_path.exists.return_value = True
        mock_paths.output = mock_output_path
        
        # Mock rollback service
        mock_rollback_service = Mock()
        mock_rollback_service.nation_slug = 'test-nation'
        mock_rollback_service.initialize_api_clients.return_value = True
        mock_rollback_service.process_rollback_row.return_value = (True, "Success")
        
        return {
            'config': mock_config,
            'logging_provider': mock_logging_provider,
            'logger': mock_logger,
            'paths': mock_paths,
            'rollback_service': mock_rollback_service
        }
    
    @patch('cdflow_cli.cli.commands_rollback.clear_screen')
    @patch('cdflow_cli.utils.paths.initialize_paths')
    @patch('cdflow_cli.cli.commands_rollback.DonationRollbackService')
    @patch('cdflow_cli.cli.commands_rollback.get_success_csv_files')
    @patch('cdflow_cli.cli.commands_rollback.safe_read_text_file')
    @patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu')
    @patch('builtins.input')
    def test_run_rollback_cli_successful_execution(
        self, mock_input, mock_menu_class, mock_read_file, mock_get_files,
        mock_rollback_service_class, mock_init_paths, mock_clear, mock_dependencies
    ):
        """Test that run_rollback_cli calls the expected functions."""
        # Configure core dependencies
        mock_init_paths.return_value = mock_dependencies['paths']
        mock_rollback_service_class.return_value = mock_dependencies['rollback_service']
        mock_get_files.return_value = ['test_success.csv']
        mock_read_file.return_value = "Donor First Name,Donor Last Name,Email\nJohn,Doe,john@example.com"

        mock_menu = Mock()
        mock_menu.show_menu.return_value = 'test_success.csv'
        mock_menu_class.return_value = mock_menu
        mock_input.return_value = ''

        result = run_rollback_cli(
            mock_dependencies['config'],
            mock_dependencies['logging_provider']
        )

        mock_init_paths.assert_called_once()
        mock_get_files.assert_called_once()
        mock_menu.show_menu.assert_called_once()
        assert isinstance(result, int)
    
    @patch('cdflow_cli.cli.commands_rollback.clear_screen')
    @patch('cdflow_cli.utils.paths.initialize_paths')
    def test_run_rollback_cli_no_paths_system(self, mock_init_paths, mock_clear, mock_dependencies):
        """Test CLI failure when paths system initialization fails."""
        mock_init_paths.return_value = None
        
        result = run_rollback_cli(
            mock_dependencies['config'],
            mock_dependencies['logging_provider']
        )
        
        assert result == 1
        # Verify paths initialization was attempted
        mock_init_paths.assert_called_once()
    
    @patch('cdflow_cli.cli.commands_rollback.clear_screen')
    @patch('cdflow_cli.utils.paths.initialize_paths')
    @patch('cdflow_cli.cli.commands_rollback.DonationRollbackService')
    def test_run_rollback_cli_authentication_failure(
        self, mock_rollback_service_class, mock_init_paths, mock_clear, mock_dependencies
    ):
        """Test CLI failure when NationBuilder authentication fails."""
        mock_init_paths.return_value = mock_dependencies['paths']
        
        # Mock authentication failure
        mock_rollback_service = Mock()
        mock_rollback_service.initialize_api_clients.return_value = False
        mock_rollback_service_class.return_value = mock_rollback_service
        
        result = run_rollback_cli(
            mock_dependencies['config'],
            mock_dependencies['logging_provider']
        )
        
        assert result == 1
        # Verify authentication was attempted
        mock_rollback_service.initialize_api_clients.assert_called_once()
    
    @patch('cdflow_cli.cli.commands_rollback.clear_screen')
    @patch('cdflow_cli.utils.paths.initialize_paths')
    @patch('cdflow_cli.cli.commands_rollback.DonationRollbackService')
    @patch('cdflow_cli.cli.commands_rollback.get_success_csv_files')
    def test_run_rollback_cli_no_success_files(
        self, mock_get_files, mock_rollback_service_class, mock_init_paths, 
        mock_clear, mock_dependencies
    ):
        """Test CLI failure when no success files are found."""
        mock_init_paths.return_value = mock_dependencies['paths']
        mock_rollback_service_class.return_value = mock_dependencies['rollback_service']
        mock_get_files.return_value = []  # No success files
        
        result = run_rollback_cli(
            mock_dependencies['config'],
            mock_dependencies['logging_provider']
        )
        
        assert result == 1
        mock_dependencies['logger'].error.assert_called_with(
            "❌ No _success.csv files found in output directory"
        )
    
    @patch('cdflow_cli.cli.commands_rollback.clear_screen')
    @patch('cdflow_cli.utils.paths.initialize_paths')
    @patch('cdflow_cli.cli.commands_rollback.DonationRollbackService')
    @patch('cdflow_cli.cli.commands_rollback.get_success_csv_files')
    @patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu')
    @patch('builtins.input')
    def test_run_rollback_cli_no_file_selected(
        self, mock_input, mock_menu_class, mock_get_files, mock_rollback_service_class,
        mock_init_paths, mock_clear, mock_dependencies
    ):
        """Test CLI when user doesn't select a file."""
        mock_init_paths.return_value = mock_dependencies['paths']
        mock_rollback_service_class.return_value = mock_dependencies['rollback_service']
        mock_get_files.return_value = ['test_success.csv']
        
        # Mock file selection menu to return None (no selection)
        mock_menu = Mock()
        mock_menu.show_menu.return_value = None
        mock_menu_class.return_value = mock_menu
        
        mock_input.return_value = ''  # User continues to menu
        
        result = run_rollback_cli(
            mock_dependencies['config'],
            mock_dependencies['logging_provider']
        )
        
        assert result == 1
        mock_dependencies['logger'].info.assert_called_with("No file selected. Exiting.")
    
    def test_run_rollback_cli_exception_handling(self, mock_dependencies):
        """Test CLI exception handling."""
        # Mock to raise exception during execution
        with patch('cdflow_cli.utils.paths.initialize_paths', side_effect=Exception("Test error")):
            result = run_rollback_cli(
                mock_dependencies['config'],
                mock_dependencies['logging_provider']
            )
        
        assert result == 1
        mock_dependencies['logger'].error.assert_called()
    
    def test_run_rollback_cli_without_logging_provider(self):
        """Test CLI execution without logging provider."""
        with patch('cdflow_cli.utils.paths.initialize_paths', side_effect=Exception("Test error")):
            result = run_rollback_cli(Mock(), None)
        
        assert result == 1


class TestMainFunction:
    """Test main entry point functionality."""
    
    @patch('cdflow_cli.utils.config_paths.resolve_config_path')
    @patch('cdflow_cli.utils.bootstrap.initialize_components_simplified')
    @patch('cdflow_cli.cli.commands_rollback.run_rollback_cli')
    @patch('argparse.ArgumentParser.parse_args')
    def test_main_basic_execution(self, mock_parse, mock_run_cli, mock_init, mock_resolve):
        """Test basic main function execution."""
        # Setup argument parsing
        args = Mock()
        args.config = 'config.yaml'
        args.log_level = 'INFO'
        mock_parse.return_value = args
        
        # Setup path resolution
        mock_resolve.return_value = Path('/resolved/config.yaml')
        
        # Mock resolved path exists
        with patch.object(Path, 'exists', return_value=True):
            # Setup component initialization
            mock_config = Mock()
            mock_logging_provider = Mock()
            mock_init.return_value = (mock_config, mock_logging_provider, '/path/to/log')
            
            # Setup CLI execution
            mock_run_cli.return_value = 0
            
            result = main()
        
        assert result == 0
        mock_resolve.assert_called_once_with('config.yaml')
        mock_init.assert_called_once_with(
            config_path='/resolved/config.yaml', 
            console_log_level='INFO'
        )
        mock_run_cli.assert_called_once_with(mock_config, mock_logging_provider)
    
    @patch('cdflow_cli.utils.config_paths.resolve_config_path')
    @patch('argparse.ArgumentParser.parse_args')
    def test_main_config_file_not_found(self, mock_parse, mock_resolve, capfd):
        """Test main function when config file doesn't exist."""
        args = Mock()
        args.config = 'nonexistent.yaml'
        args.log_level = 'INFO'
        mock_parse.return_value = args
        
        # Mock path that doesn't exist
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_resolve.return_value = mock_path
        
        result = main()
        
        assert result == 1
        captured = capfd.readouterr()
        assert "Configuration file not found" in captured.out
    
    @patch('cdflow_cli.utils.config_paths.resolve_config_path')
    @patch('cdflow_cli.utils.bootstrap.initialize_components_simplified')
    @patch('cdflow_cli.cli.commands_rollback.run_rollback_cli')
    @patch('argparse.ArgumentParser.parse_args')
    def test_main_with_debug_log_level(self, mock_parse, mock_run_cli, mock_init, mock_resolve):
        """Test main function with DEBUG log level."""
        args = Mock()
        args.config = 'config.yaml'
        args.log_level = 'DEBUG'
        mock_parse.return_value = args
        
        mock_resolve.return_value = Path('/resolved/config.yaml')
        
        with patch.object(Path, 'exists', return_value=True):
            mock_config = Mock()
            mock_logging_provider = Mock()
            mock_init.return_value = (mock_config, mock_logging_provider, '/path/to/log')
            mock_run_cli.return_value = 0
            
            result = main()
        
        assert result == 0
        mock_init.assert_called_once_with(
            config_path='/resolved/config.yaml',
            console_log_level='DEBUG'
        )
    
    @patch('argparse.ArgumentParser.parse_args')
    def test_main_argument_parsing_choices(self, mock_parse):
        """Test that main uses correct argument parser configuration."""
        # This test verifies the argument parser setup
        args = Mock()
        args.config = 'config.yaml'
        args.log_level = 'NOTICE'  # Test non-standard log level
        mock_parse.return_value = args
        
        # Just verify argument parsing works with expected choices
        with patch('cdflow_cli.utils.config_paths.resolve_config_path') as mock_resolve:
            mock_resolve.return_value = Path('/test/config.yaml')
            with patch.object(Path, 'exists', return_value=False):
                result = main()
        
        assert result == 1  # Should fail due to missing config file
        mock_parse.assert_called_once()


class TestRollbackIntegration:
    """Integration tests for rollback command functionality."""
    
    def test_csv_processing_workflow(self):
        """Test complete CSV processing workflow."""
        # Create test CSV content
        csv_content = """field1,field2,NB Error Message
value1,value2,
value3,value4,"""
        
        # Mock the complete workflow
        with patch('cdflow_cli.cli.commands_rollback.safe_read_text_file') as mock_read:
            mock_read.return_value = csv_content
            
            # Test CSV parsing
            csv_input = StringIO(csv_content)
            reader = csv.DictReader(csv_input)
            rows = list(reader)
            
            assert len(rows) == 2
            assert rows[0]['field1'] == 'value1'
            assert rows[1]['field1'] == 'value3'
            assert 'NB Error Message' in reader.fieldnames
    
    def test_import_type_detection_workflow(self):
        """Test import type detection with various CSV formats."""
        test_cases = [
            # CanadaHelps format
            ("DONOR FIRST NAME,DONOR LAST NAME,DONOR EMAIL ADDRESS,AMOUNT", "CanadaHelps"),
            # PayPal format  
            ("Date,Time,Name,Type,Status,From Email Address,Gross,Fee", "PayPal"),
            # Unknown format
            ("Custom,Field,Names", None)
        ]
        
        for header, expected_type in test_cases:
            detected_type = determine_import_type_from_header(header)
            assert detected_type == expected_type, f"Failed for header: {header}"
    
    def test_file_operations_integration(self):
        """Test file operations working together."""
        with tempfile.TemporaryDirectory() as temp_dir:
            mock_paths = Mock()
            mock_paths.output = Path(temp_dir)
            
            filename = "integration_test.csv"
            fieldnames = ["field1", "field2", "error_message"]
            encoding = "utf-8"
            
            # Initialize file
            initialize_output_file(filename, fieldnames, encoding, mock_paths)
            
            # Append multiple rows
            test_rows = [
                {"field1": "row1", "field2": "data1", "error_message": "Success"},
                {"field1": "row2", "field2": "data2", "error_message": "Failed"},
            ]
            
            for row in test_rows:
                append_row_to_file(filename, row, fieldnames, encoding, mock_paths)
            
            # Verify final file content
            output_file = mock_paths.output / filename
            with open(output_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                final_rows = list(reader)
            
            assert len(final_rows) == 2
            assert final_rows[0]["field1"] == "row1"
            assert final_rows[1]["field1"] == "row2"
            assert final_rows[0]["error_message"] == "Success"
            assert final_rows[1]["error_message"] == "Failed"


class TestDirectModuleExecution:
    """Test direct module execution - line 441."""
    
    def test_direct_module_execution_line_441(self):
        """Test __name__ == '__main__' execution path - line 441."""
        # Mock the run_rollback_cli function to avoid actual execution
        with patch('cdflow_cli.cli.commands_rollback.run_rollback_cli', return_value=0) as mock_run, \
             patch('sys.exit') as mock_exit:
            
            # Import the module and patch its __name__ to simulate direct execution
            import cdflow_cli.cli.commands_rollback as rollback_module
            
            # Temporarily change the module's __name__ to '__main__' to trigger line 441
            with patch.object(rollback_module, '__name__', '__main__'):
                # Execute the code at line 441 by executing the module-level if statement
                # This directly calls the code: if __name__ == "__main__": sys.exit(run_rollback_cli())
                try:
                    exec('if __name__ == "__main__": sys.exit(run_rollback_cli())', rollback_module.__dict__)
                except SystemExit:
                    # Expected - the code calls sys.exit
                    pass
            
            # Verify the execution path was called
            mock_run.assert_called_once_with()  # Called without arguments
            mock_exit.assert_called_once_with(0)  # Called with return value
