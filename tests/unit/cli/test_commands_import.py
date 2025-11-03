import pytest
import tempfile
import os
import sys
import uuid
import argparse
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
from io import StringIO

from cdflow_cli.cli.commands_import import (
    clear_screen,
    get_encoding,
    initialize_logging,
    parse_arguments,
    prompt_for_confirmation,
    validate_import_file,
    create_cli_processing_copy,
    get_import_settings,
    monitor_cli_job,
    run_cli_with_jobs,
    main
)


# Shared fixtures for performance optimization
@pytest.fixture(scope="session")
def session_temp_dir():
    """Create a session-level temporary directory."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(scope="class")
def mock_chardet():
    """Create a reusable chardet mock."""
    with patch('chardet.detect') as mock_detect:
        mock_detect.return_value = {'encoding': 'utf-8', 'confidence': 0.99}
        yield mock_detect


@pytest.fixture
def base_mock_config():
    """Create a basic mock config object."""
    config = Mock()
    config.get_logging_config.return_value = {
        'provider': 'file',
        'file_level': 'DEBUG',
        'settings': {'directory': './logs'}
    }
    return config


class TestClearScreen:
    """Test terminal screen clearing functionality."""
    
    @patch('os.system')
    def test_clear_screen_windows(self, mock_system):
        """Test clear screen on Windows."""
        with patch('os.name', 'nt'):
            clear_screen()
            mock_system.assert_called_once_with('cls')
    
    @patch('os.system')
    def test_clear_screen_unix(self, mock_system):
        """Test clear screen on Unix/Linux/Mac."""
        with patch('os.name', 'posix'):
            clear_screen()
            mock_system.assert_called_once_with('clear')


class TestGetEncoding:
    """Test file encoding detection functionality."""
    
    @pytest.fixture(scope="class")  # Use class scope for better performance
    def mock_paths(self):
        """Create mock paths system."""
        paths = Mock()
        paths.cli_source = Path('/test/cli_source')
        paths.app_processing = Path('/test/app_processing')
        return paths
    
    @pytest.fixture
    def mock_file_content(self):
        """Create mock file content."""
        mock_file = Mock()
        mock_file.read.return_value = b'test content'
        return mock_file
    
    def test_get_encoding_cli_usage(self, mock_chardet, mock_paths, mock_file_content):
        """Test encoding detection for CLI usage."""
        with patch('builtins.open') as mock_open:
            mock_open.return_value.__enter__.return_value = mock_file_content
            
            encoding, confidence = get_encoding('test.csv', mock_paths)
            
            assert encoding == 'utf-8'
            assert confidence == 0.99
            mock_open.assert_called_once_with(mock_paths.cli_source / 'test.csv', 'rb')
    
    def test_get_encoding_api_usage(self, mock_paths, mock_file_content):
        """Test encoding detection for API usage."""
        with patch('chardet.detect', return_value={'encoding': 'windows-1252', 'confidence': 0.85}), \
             patch('builtins.open') as mock_open:
            mock_open.return_value.__enter__.return_value = mock_file_content
            
            encoding, confidence = get_encoding('canadahelps/test.csv', mock_paths)
            
            assert encoding == 'windows-1252'
            assert confidence == 0.85
            mock_open.assert_called_once_with(mock_paths.app_processing / 'canadahelps/test.csv', 'rb')
    
    def test_get_encoding_paypal_api_usage(self, mock_paths, mock_file_content):
        """Test encoding detection for PayPal API usage."""
        with patch('chardet.detect', return_value={'encoding': 'iso-8859-1', 'confidence': 0.75}), \
             patch('builtins.open') as mock_open:
            mock_open.return_value.__enter__.return_value = mock_file_content
            
            encoding, confidence = get_encoding('paypal/transactions.csv', mock_paths)
            
            assert encoding == 'iso-8859-1'
            assert confidence == 0.75
            mock_open.assert_called_once_with(mock_paths.app_processing / 'paypal/transactions.csv', 'rb')
    
    def test_get_encoding_exception_handling(self, mock_paths, caplog):
        """Test encoding detection error handling."""
        with patch('builtins.open', side_effect=FileNotFoundError("File not found")):
            encoding, confidence = get_encoding('nonexistent.csv', mock_paths)
            
            assert encoding == 'utf-8'  # Default fallback
            assert confidence == 0.0    # Low confidence
            assert "Error detecting file encoding" in caplog.text


class TestInitializeLogging:
    """Test logging initialization functionality."""
    
    def test_initialize_logging_with_config(self, base_mock_config):
        """Test logging initialization with configuration."""
        with patch('cdflow_cli.cli.commands_import.get_logging_provider') as mock_get_provider:
            mock_provider = Mock()
            mock_get_provider.return_value = mock_provider
            
            provider, log_path = initialize_logging(base_mock_config)
            
            assert provider == mock_provider
            assert log_path is None  # Not early init
            mock_provider.configure_logging.assert_called_once_with(log_level='DEBUG', early_init=False)
    
    def test_initialize_logging_early_init(self, base_mock_config):
        """Test early logging initialization."""
        base_mock_config.get_logging_config.return_value = {'provider': 'file', 'file_level': 'INFO'}
        
        with patch('cdflow_cli.cli.commands_import.get_logging_provider') as mock_get_provider:
            mock_provider = Mock()
            mock_provider.configure_logging.return_value = '/path/to/log'
            mock_get_provider.return_value = mock_provider
            
            provider, log_path = initialize_logging(base_mock_config, early_init=True)
            
            assert provider == mock_provider
            assert log_path == '/path/to/log'
            # Should call configure_logging with log_filename and early_init=True
            call_args = mock_provider.configure_logging.call_args
            assert call_args[1]['early_init'] is True
            assert 'IMPORTDONATIONS_' in call_args[1]['log_filename']
    
    def test_initialize_logging_no_config(self):
        """Test logging initialization without configuration."""
        mock_config = Mock()
        mock_config.get_logging_config.return_value = None
        
        with patch('cdflow_cli.cli.commands_import.get_logging_provider') as mock_get_provider:
            mock_provider = Mock()
            mock_get_provider.return_value = mock_provider
            
            provider, log_path = initialize_logging(mock_config)
            
            # Should use default config
            expected_config = {
                'provider': 'file',
                'settings': {'directory': './logs', 'level': 'DEBUG', 'console_level': 'INFO'}
            }
            mock_get_provider.assert_called_once_with(expected_config)
            mock_provider.configure_logging.assert_called_once_with(log_level='DEBUG', early_init=False)


class TestParseArguments:
    """Test command line argument parsing."""
    
    def test_parse_arguments_all_options(self):
        """Test parsing all command line options."""
        test_args = ['--config', 'config.yaml', '--log-level', 'DEBUG', '--type', 'paypal', '--file', 'test.csv']
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            args = parse_arguments()
            
            assert args.config == 'config.yaml'
            assert args.log_level == 'DEBUG'
            assert args.type == 'paypal'
            assert args.file == 'test.csv'
    
    def test_parse_arguments_required_only(self):
        """Test parsing with only required arguments."""
        test_args = ['--config', 'config.yaml']
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            args = parse_arguments()
            
            assert args.config == 'config.yaml'
            assert args.log_level == 'INFO'  # default
            assert args.type is None
            assert args.file is None
    
    def test_parse_arguments_invalid_log_level(self):
        """Test parsing with invalid log level."""
        test_args = ['--config', 'config.yaml', '--log-level', 'INVALID']
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            with pytest.raises(SystemExit):
                parse_arguments()
    
    def test_parse_arguments_invalid_type(self):
        """Test parsing with invalid import type."""
        test_args = ['--config', 'config.yaml', '--type', 'invalid']
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            with pytest.raises(SystemExit):
                parse_arguments()
    
    def test_parse_arguments_missing_config(self):
        """Test parsing without required config argument."""
        test_args = ['--type', 'canadahelps']
        
        with patch.object(sys, 'argv', ['command'] + test_args):
            with pytest.raises(SystemExit):
                parse_arguments()


class TestPromptForConfirmation:
    """Test user confirmation prompt functionality."""
    
    @patch('cdflow_cli.cli.commands_import.start_fresh_output')
    @patch('builtins.input')
    def test_prompt_for_confirmation_accept(self, mock_input, mock_start_fresh):
        """Test user accepting confirmation prompt."""
        mock_input.return_value = ''  # User presses Enter
        
        with patch('cdflow_cli.cli.commands_import.logger') as mock_logger:
            result = prompt_for_confirmation('test-nation', 'test.csv', 'CanadaHelps')
            
            assert result is True
            mock_start_fresh.assert_called_once()
            # Verify logger was called with expected messages
            mock_logger.info.assert_called()
    
    @patch('cdflow_cli.cli.commands_import.start_fresh_output')
    @patch('builtins.input')
    def test_prompt_for_confirmation_cancel(self, mock_input, mock_start_fresh):
        """Test user canceling confirmation prompt."""
        mock_input.side_effect = KeyboardInterrupt()
        
        with patch('cdflow_cli.cli.commands_import.logger') as mock_logger:
            result = prompt_for_confirmation('test-nation', 'test.csv', 'PayPal')
            
            assert result is False
            mock_start_fresh.assert_called_once()
            # Verify logger was called with cancel message
            mock_logger.info.assert_called()


class TestValidateImportFile:
    """Test import file validation functionality."""
    
    @pytest.fixture(scope="class")  # Use class scope for better performance
    def temp_storage_dir(self):
        """Create temporary storage directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_config_with_paths(self, temp_storage_dir):
        """Create mock config with paths system."""
        config = Mock()
        # Remove the patch that doesn't exist and create a simpler mock
        mock_paths = Mock()
        mock_paths.get_path.return_value = temp_storage_dir / 'cli_source'
        config.paths = mock_paths
        return config
    
    def test_validate_import_file_absolute_path(self, temp_storage_dir, mock_config_with_paths):
        """Test validation with absolute file path."""
        # Create test file
        test_file = temp_storage_dir / 'test.csv'
        test_file.write_text('test,data\n1,2')
        
        with patch('cdflow_cli.cli.commands_import.Path') as mock_path_cls:
            mock_path_cls.return_value.exists.return_value = True
            mock_path_cls.return_value.is_file.return_value = True
            mock_path_cls.return_value.resolve.return_value = test_file
            
            result = validate_import_file(str(test_file), mock_config_with_paths)
            assert str(result) == str(test_file)
    
    def test_validate_import_file_relative_from_cwd(self, temp_storage_dir, mock_config_with_paths):
        """Test validation with relative path from current directory."""
        test_file = temp_storage_dir / 'test.csv'
        
        with patch('cdflow_cli.cli.commands_import.Path') as mock_path_cls, \
             patch('cdflow_cli.cli.commands_import.Path.cwd', return_value=temp_storage_dir):
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.is_file.return_value = True
            mock_path_instance.resolve.return_value = test_file
            mock_path_cls.return_value = mock_path_instance
            
            result = validate_import_file('test.csv', mock_config_with_paths, resolve_from_cwd=True)
            assert str(result) == str(test_file)
    
    def test_validate_import_file_relative_from_cli_source(self, temp_storage_dir, mock_config_with_paths):
        """Test validation with relative path from cli_source."""
        cli_source = temp_storage_dir / 'cli_source'
        test_file = cli_source / 'test.csv'
        
        # Mock the initialize_paths function that's imported within validate_import_file
        with patch('cdflow_cli.utils.paths.initialize_paths') as mock_init_paths:
            mock_paths = Mock()
            mock_paths.get_path.return_value = cli_source
            mock_init_paths.return_value = mock_paths
            
            # Create actual file for validation
            cli_source.mkdir(parents=True, exist_ok=True)
            test_file.write_text('test,data\n1,2')
            
            try:
                result = validate_import_file('test.csv', mock_config_with_paths, resolve_from_cwd=False)
                assert result.resolve() == test_file.resolve()  # Use resolve() to handle symlinks
            finally:
                # Cleanup
                if test_file.exists():
                    test_file.unlink()
                if cli_source.exists():
                    cli_source.rmdir()
    
    def test_validate_import_file_not_found(self, mock_config_with_paths):
        """Test validation with non-existent file."""
        with patch('cdflow_cli.cli.commands_import.Path') as mock_path_cls:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = False
            mock_path_instance.resolve.return_value = Path('/nonexistent/nonexistent.csv')
            mock_path_cls.return_value = mock_path_instance
            
            with pytest.raises(FileNotFoundError) as exc_info:
                validate_import_file('nonexistent.csv', mock_config_with_paths)
            
            error_msg = str(exc_info.value)
            assert "Import file not found: nonexistent.csv" in error_msg
    
    def test_validate_import_file_is_directory(self, temp_storage_dir, mock_config_with_paths):
        """Test validation when path is a directory."""
        test_dir = temp_storage_dir / 'testdir'
        test_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            with pytest.raises(ValueError) as exc_info:
                validate_import_file(str(test_dir), mock_config_with_paths)
            
            assert "Path exists but is not a file" in str(exc_info.value)
        finally:
            # Cleanup
            if test_dir.exists():
                test_dir.rmdir()


class TestGetImportSettings:
    """Test import settings retrieval functionality."""
    
    def test_get_import_settings_cli_override(self):
        """Test getting settings from CLI override."""
        mock_config = Mock()
        mock_config._cli_override = {
            'type': 'PayPal',
            'file': 'cli_file.csv'
        }
        
        source_type, filename = get_import_settings(mock_config)
        
        assert source_type == 'paypal'  # lowercased
        assert filename == 'cli_file.csv'
    
    def test_get_import_settings_from_config(self):
        """Test getting settings from config file."""
        mock_config = Mock()
        # No CLI override
        if hasattr(mock_config, '_cli_override'):
            delattr(mock_config, '_cli_override')
        
        # Mock config file settings
        mock_config.get_import_setting.return_value = {
            'type': 'CanadaHelps',
            'file': 'config_file.csv'
        }
        
        source_type, filename = get_import_settings(mock_config)
        
        assert source_type == 'canadahelps'  # lowercased
        assert filename == 'config_file.csv'
    
    def test_get_import_settings_no_cli_config(self):
        """Test error when no CLI config is available."""
        mock_config = Mock()
        # Remove CLI override attribute if it exists
        if hasattr(mock_config, '_cli_override'):
            delattr(mock_config, '_cli_override')
        mock_config.get_import_setting.return_value = None
        
        with pytest.raises(ValueError, match="No CLI import configuration found"):
            get_import_settings(mock_config)
    
    def test_get_import_settings_incomplete_config(self):
        """Test error when config is missing required fields."""
        mock_config = Mock()
        # Remove CLI override attribute if it exists
        if hasattr(mock_config, '_cli_override'):
            delattr(mock_config, '_cli_override')
        mock_config.get_import_setting.return_value = {
            'type': 'canadahelps'
            # missing 'file' field
        }
        
        with pytest.raises(ValueError, match="missing required 'type' or 'file' fields"):
            get_import_settings(mock_config)


class TestMonitorCliJob:
    """Test CLI job monitoring functionality."""
    
    def test_monitor_cli_job_successful_completion(self):
        """Test monitoring a successfully completed job."""
        mock_job_manager = Mock()
        
        # Simulate job progression: running -> completed (need both calls: one for loop, one for final status)
        job_statuses = [
            {'status': 'completed', 'result': {
                'success_count': 10,
                'fail_count': 0,
                'success_file': 'success.csv',
                'fail_file': 'fail.csv',
                'log_file': 'import.log'
            }},
            {'status': 'completed', 'result': {  # Second call for final status check
                'success_count': 10,
                'fail_count': 0,
                'success_file': 'success.csv',
                'fail_file': 'fail.csv',
                'log_file': 'import.log'
            }}
        ]
        mock_job_manager.get_job_status.side_effect = job_statuses
        
        with patch('builtins.print'), \
             patch('time.sleep'), \
             patch('cdflow_cli.cli.commands_import.logger') as mock_logger:
            result = monitor_cli_job(mock_job_manager, 'test-job-id')
            
            assert result == 0  # Success
            # Verify success logging was called
            mock_logger.notice.assert_called()
    
    def test_monitor_cli_job_failed_completion(self, capfd):
        """Test monitoring a failed job."""
        mock_job_manager = Mock()
        
        job_statuses = [
            {'status': 'running', 'progress': 25},
            {'status': 'failed', 'error_message': 'Connection timeout'}
        ]
        mock_job_manager.get_job_status.side_effect = job_statuses
        
        result = monitor_cli_job(mock_job_manager, 'test-job-id')
        
        assert result == 1  # Failure
    
    def test_monitor_cli_job_aborted_by_user(self, capfd):
        """Test monitoring when job is aborted by user."""
        mock_job_manager = Mock()
        
        job_statuses = [
            {'status': 'failed', 'error_message': 'Job aborted by user'}
        ]
        mock_job_manager.get_job_status.side_effect = job_statuses
        
        result = monitor_cli_job(mock_job_manager, 'test-job-id')
        
        assert result == 0  # Treated as success (user choice)
        captured = capfd.readouterr()
        assert "Job was aborted by user" in captured.out
    
    def test_monitor_cli_job_keyboard_interrupt(self):
        """Test monitoring with keyboard interrupt - properly testing the behavior."""
        mock_job_manager = Mock()
        
        # Create a custom side effect that raises KeyboardInterrupt on first call only
        call_count = 0
        def raise_keyboard_interrupt(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise KeyboardInterrupt()
            return {'status': 'completed', 'result': {'success_count': 1, 'fail_count': 0, 'success_file': 'test.csv', 'fail_file': 'fail.csv', 'log_file': 'log.txt'}}
        
        mock_job_manager.get_job_status.side_effect = raise_keyboard_interrupt
        
        # Mock the __import__ function to intercept the dynamic import of os
        original_import = __builtins__['__import__']
        mock_os_module = Mock()
        mock_os_module._exit = Mock()
        
        def mock_import(name, *args, **kwargs):
            if name == 'os':
                return mock_os_module
            return original_import(name, *args, **kwargs)
        
        with patch('builtins.__import__', side_effect=mock_import), \
             patch('builtins.print') as mock_print:
            
            monitor_cli_job(mock_job_manager, 'test-job-id')
            
            # Verify the expected behavior occurred
            mock_print.assert_called_with("\n\n⏹️  CTRL-C received. Terminating process.")
            mock_os_module._exit.assert_called_once_with(1)
    
    def test_monitor_cli_job_monitoring_exception(self, capfd):
        """Test monitoring with exception during status check."""
        mock_job_manager = Mock()
        mock_job_manager.get_job_status.side_effect = Exception("API error")
        
        result = monitor_cli_job(mock_job_manager, 'test-job-id')
        
        assert result == 1  # Error
        captured = capfd.readouterr()
        assert "Error monitoring job" in captured.out


class TestMainFunction:
    """Test main entry point functionality."""
    
    @patch('cdflow_cli.utils.config_paths.resolve_config_path')
    @patch('cdflow_cli.utils.bootstrap.initialize_components_simplified')
    @patch('cdflow_cli.cli.commands_import.run_cli')
    @patch('cdflow_cli.cli.commands_import.parse_arguments')
    def test_main_basic_execution(self, mock_parse, mock_run_cli, mock_init, mock_resolve):
        """Test basic main function execution."""
        # Setup argument parsing
        args = Mock()
        args.config = 'config.yaml'
        args.log_level = 'INFO'
        args.type = None
        args.file = None
        mock_parse.return_value = args
        
        # Setup path resolution
        mock_resolve.return_value = Path('/resolved/config.yaml')
        
        # Setup component initialization
        mock_config = Mock()
        mock_logging_provider = Mock()
        mock_logger = Mock()
        mock_logging_provider.get_logger.return_value = mock_logger
        mock_init.return_value = (mock_config, mock_logging_provider, '/path/to/log')
        
        # Setup CLI execution
        mock_run_cli.return_value = 0
        
        result = main()
        
        assert result == 0
        mock_resolve.assert_called_once_with('config.yaml')
        mock_init.assert_called_once_with(config_path='/resolved/config.yaml', console_log_level='INFO')
        mock_run_cli.assert_called_once_with(mock_config, mock_logging_provider)
    
    @patch('cdflow_cli.utils.config_paths.resolve_config_path')
    @patch('cdflow_cli.utils.bootstrap.initialize_components_simplified')
    @patch('cdflow_cli.cli.commands_import.run_cli')
    @patch('cdflow_cli.cli.commands_import.parse_arguments')
    def test_main_with_cli_overrides(self, mock_parse, mock_run_cli, mock_init, mock_resolve):
        """Test main function with CLI argument overrides."""
        # Setup argument parsing with overrides
        args = Mock()
        args.config = 'config.yaml'
        args.log_level = 'DEBUG'
        args.type = 'paypal'
        args.file = 'override.csv'
        mock_parse.return_value = args
        
        mock_resolve.return_value = Path('/resolved/config.yaml')
        
        # Setup component initialization
        mock_config = Mock()
        mock_config._cli_override = {}  # Make it support item assignment
        mock_logging_provider = Mock()
        mock_logger = Mock()
        mock_logging_provider.get_logger.return_value = mock_logger
        mock_init.return_value = (mock_config, mock_logging_provider, '/path/to/log')
        
        mock_run_cli.return_value = 0
        
        result = main()
        
        assert result == 0
        # Verify CLI overrides were applied to config
        assert hasattr(mock_config, '_cli_override')
        assert mock_config._cli_override['type'] == 'paypal'
        assert mock_config._cli_override['file'] == 'override.csv'
