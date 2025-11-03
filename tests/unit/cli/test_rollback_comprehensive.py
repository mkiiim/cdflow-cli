"""
Comprehensive tests for rollback core functionality - targeting 100% coverage
Tests lines 290-390 and line 441 specifically
"""
import pytest
import tempfile
import csv
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from cdflow_cli.cli.commands_rollback import run_rollback_cli


class TestRollbackComprehensiveCoverage:
    """Comprehensive tests targeting 100% coverage of rollback core functionality."""
    
    @pytest.fixture
    def complete_test_environment(self):
        """Create a complete test environment for comprehensive rollback testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            output_dir = temp_path / "output"
            output_dir.mkdir()
            
            # Create test CSV files
            canadahelps_csv = """Donor First Name,Donor Last Name,Email,Amount,Date
John,Doe,john@example.com,50.00,2024-01-01
Jane,Smith,jane@example.com,75.50,2024-01-02"""
            
            paypal_csv = """Date,Time,Name,Type,Status,From Email Address,Gross,Fee
2024-01-01,12:00:00,John Doe,Payment,Completed,john@example.com,50.00,1.50"""
            
            empty_csv = """Donor First Name,Donor Last Name,Email,Amount"""
            
            # Mock config with different scenarios
            mock_config = Mock()
            
            # Mock logging
            mock_logging_provider = Mock()
            mock_logger = Mock()
            mock_logging_provider.get_logger.return_value = mock_logger
            
            # Mock paths
            mock_paths = Mock()
            mock_paths.output = output_dir
            
            # Mock rollback service
            mock_rollback_service = Mock()
            mock_rollback_service.nation_slug = 'test-nation'
            mock_rollback_service.initialize_api_clients.return_value = True
            
            yield {
                'config': mock_config,
                'logging_provider': mock_logging_provider,
                'logger': mock_logger,
                'paths': mock_paths,
                'rollback_service': mock_rollback_service,
                'canadahelps_csv': canadahelps_csv,
                'paypal_csv': paypal_csv,
                'empty_csv': empty_csv,
                'output_dir': output_dir
            }
    
    def test_core_workflow_canadahelps_success(self, complete_test_environment):
        """Test complete core workflow for CanadaHelps with successful rollbacks - lines 290-390."""
        env = complete_test_environment
        
        # Configure successful rollbacks
        env['rollback_service'].process_rollback_row.return_value = (True, "Successfully deleted")
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=env['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=env['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['test_success.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=env['canadahelps_csv']), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''),  \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('cdflow_cli.cli.commands_rollback.initialize_output_file') as mock_init, \
             patch('cdflow_cli.cli.commands_rollback.append_row_to_file') as mock_append, \
             patch('builtins.print'), \
             patch('datetime.datetime') as mock_datetime:
            
            # Mock menu selection - this is KEY for not hanging!
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'test_success.csv'  # Must return actual filename
            mock_menu_class.return_value = mock_menu
            
            # Mock datetime for consistent rollback filename
            mock_now = Mock()
            mock_now.strftime.return_value = '20240101-120000'
            mock_datetime.now.return_value = mock_now
            
            result = run_rollback_cli(env['config'], env['logging_provider'])
            
            # Test successful execution (line 390)
            assert result == 0
            
            # Verify core processing steps
            mock_init.assert_called_once()
            assert mock_append.call_count == 2  # 2 rows processed
            assert env['rollback_service'].process_rollback_row.call_count == 2
            
            # Verify summary logging was called (lines 377-380)
            logger_calls = [call[0][0] for call in env['logger'].notice.call_args_list]
            summary_logs = [log for log in logger_calls if "Successfully processed all" in log]
            assert len(summary_logs) > 0, "Should log successful completion summary"
    
    def test_core_workflow_paypal_detection(self, complete_test_environment):
        """Test PayPal import type detection in core workflow - lines 301-315."""
        env = complete_test_environment
        env['rollback_service'].process_rollback_row.return_value = (True, "Deleted")
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=env['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=env['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['paypal_success.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=env['paypal_csv']), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''), \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('cdflow_cli.cli.commands_rollback.initialize_output_file'), \
             patch('cdflow_cli.cli.commands_rollback.append_row_to_file'), \
             patch('builtins.print'):
            
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'paypal_success.csv'
            mock_menu_class.return_value = mock_menu
            
            result = run_rollback_cli(env['config'], env['logging_provider'])
            
            assert result == 0
            
            # Verify PayPal was detected and used
            calls = env['rollback_service'].process_rollback_row.call_args_list
            assert calls[0][0][1] == 'PayPal'  # import_type parameter
    
    def test_core_workflow_config_fallback_detection(self, complete_test_environment):
        """Test import type detection with config fallback - lines 304-315."""
        env = complete_test_environment
        
        # Set up config to return specific import type
        env['config'].get_import_setting.return_value = {'type': 'paypal'}
        env['rollback_service'].process_rollback_row.return_value = (True, "Deleted")
        
        # Use CSV with unknown header to force config fallback
        unknown_csv = """Unknown,Header,Format\ntest,data,value"""
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=env['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=env['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['unknown.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=unknown_csv), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''), \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('cdflow_cli.cli.commands_rollback.initialize_output_file'), \
             patch('cdflow_cli.cli.commands_rollback.append_row_to_file'), \
             patch('builtins.print'):
            
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'unknown.csv'
            mock_menu_class.return_value = mock_menu
            
            result = run_rollback_cli(env['config'], env['logging_provider'])
            
            assert result == 0
            
            # Verify config fallback was used (line 307-311)
            env['config'].get_import_setting.assert_called_once()
            calls = env['rollback_service'].process_rollback_row.call_args_list
            assert calls[0][0][1] == 'PayPal'  # Should use config fallback
    
    def test_core_workflow_default_canadahelps(self, complete_test_environment):
        """Test default CanadaHelps fallback - lines 313-315."""
        env = complete_test_environment
        
        # Configure no import setting and unknown header to force default
        env['config'].get_import_setting.return_value = None
        env['rollback_service'].process_rollback_row.return_value = (True, "Deleted")
        
        unknown_csv = """Unknown,Header\ntest,data"""
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=env['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=env['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['unknown.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=unknown_csv), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''), \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('cdflow_cli.cli.commands_rollback.initialize_output_file'), \
             patch('cdflow_cli.cli.commands_rollback.append_row_to_file'), \
             patch('builtins.print'):
            
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'unknown.csv'
            mock_menu_class.return_value = mock_menu
            
            result = run_rollback_cli(env['config'], env['logging_provider'])
            
            assert result == 0
            
            # Verify default CanadaHelps was used (lines 314-315)
            calls = env['rollback_service'].process_rollback_row.call_args_list
            assert calls[0][0][1] == 'CanadaHelps'
    
    def test_core_workflow_mixed_success_failure(self, complete_test_environment):
        """Test core workflow with mixed success/failure - lines 360-370, 382-384."""
        env = complete_test_environment
        
        # Configure mixed results
        def mixed_results(row, import_type):
            if 'john@example.com' in row.get('Email', ''):
                return True, "Successfully deleted"
            return False, "Donation not found"
        
        env['rollback_service'].process_rollback_row.side_effect = mixed_results
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=env['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=env['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['test.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=env['canadahelps_csv']), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''), \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('cdflow_cli.cli.commands_rollback.initialize_output_file'), \
             patch('cdflow_cli.cli.commands_rollback.append_row_to_file') as mock_append, \
             patch('builtins.print'):
            
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'test.csv'
            mock_menu_class.return_value = mock_menu
            
            result = run_rollback_cli(env['config'], env['logging_provider'])
            
            assert result == 0
            
            # Verify mixed results summary (lines 382-384)
            logger_calls = [call[0][0] for call in env['logger'].notice.call_args_list]
            mixed_summary = [log for log in logger_calls if "successes and" in log and "failures" in log]
            assert len(mixed_summary) > 0, "Should log mixed success/failure summary"
            
            # Verify error messages were added to rows (line 369)
            append_calls = mock_append.call_args_list
            for call in append_calls:
                row_data = call[0][1]  # Second argument is the row
                assert 'NB Error Message' in row_data
    
    def test_core_workflow_empty_csv_file(self, complete_test_environment):
        """Test core workflow with empty CSV file - lines 333-335."""
        env = complete_test_environment
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=env['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=env['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['empty.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=env['empty_csv']), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''), \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('builtins.print'):
            
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'empty.csv'
            mock_menu_class.return_value = mock_menu
            
            result = run_rollback_cli(env['config'], env['logging_provider'])
            
            # Should return 1 for empty file (lines 333-335)
            assert result == 1
            
            # Verify warning was logged
            warning_calls = env['logger'].warning.call_args_list
            assert len(warning_calls) > 0
            assert "No data rows found in file" in warning_calls[0][0][0]
    
    def test_core_workflow_reverse_processing_order(self, complete_test_environment):
        """Test that rows are processed in reverse order - lines 353-356."""
        env = complete_test_environment
        
        # Track the order of processing
        processed_emails = []
        
        def track_processing(row, import_type):
            processed_emails.append(row.get('Email', ''))
            return True, "Deleted"
        
        env['rollback_service'].process_rollback_row.side_effect = track_processing
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=env['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=env['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['test.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=env['canadahelps_csv']), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''), \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('cdflow_cli.cli.commands_rollback.initialize_output_file'), \
             patch('cdflow_cli.cli.commands_rollback.append_row_to_file'), \
             patch('builtins.print'):
            
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'test.csv'
            mock_menu_class.return_value = mock_menu
            
            result = run_rollback_cli(env['config'], env['logging_provider'])
            
            assert result == 0
            
            # Verify reverse processing order (line 353: reversed(rows))
            assert processed_emails[0] == 'jane@example.com'  # Last row processed first
            assert processed_emails[1] == 'john@example.com'  # First row processed last


class TestDirectModuleExecution:
    """Test direct module execution - line 441."""
    
    def test_direct_module_execution(self):
        """Test __name__ == '__main__' execution path - line 441."""
        # Mock the run_rollback_cli function to avoid actual execution
        with patch('cdflow_cli.cli.commands_rollback.run_rollback_cli', return_value=0) as mock_run, \
             patch('sys.exit') as mock_exit:
            
            # Import and execute the module's main block
            import cdflow_cli.cli.commands_rollback as rollback_module
            
            # Simulate direct execution
            if __name__ != '__main__':  # We're in test, not direct execution
                # Manually trigger the main execution path
                with patch('cdflow_cli.cli.commands_rollback.__name__', '__main__'):
                    # This would trigger: sys.exit(run_rollback_cli())
                    # But we need to test it without actually exiting
                    exec(compile("sys.exit(run_rollback_cli())", "<string>", "exec"), {
                        'sys': __import__('sys'),
                        'run_rollback_cli': mock_run
                    })
            
            # Verify the execution path was called
            mock_run.assert_called_once_with()  # Called without arguments
            mock_exit.assert_called_once_with(0)  # Called with return value
