import pytest
import tempfile
import csv
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

from cdflow_cli.cli.commands_rollback import run_rollback_cli


class TestRollbackCoreFunctionality:
    """Test the core rollback processing functionality that was previously untested."""
    
    @pytest.fixture
    def complete_mock_environment(self):
        """Create a comprehensive mock environment for core rollback testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create real test files
            temp_path = Path(temp_dir)
            output_dir = temp_path / "output"
            output_dir.mkdir()
            
            # Create a real CSV file with test data
            test_csv_file = output_dir / "test_success.csv" 
            test_csv_content = """Donor First Name,Donor Last Name,Email,Amount,Date
John,Doe,john@example.com,50.00,2024-01-01
Jane,Smith,jane@example.com,75.50,2024-01-02
Bob,Johnson,bob@example.com,100.00,2024-01-03"""
            test_csv_file.write_text(test_csv_content)
            
            # Mock config
            mock_config = Mock()
            mock_config.get_import_setting.return_value = {'type': 'canadahelps'}
            
            # Mock logging provider and logger
            mock_logging_provider = Mock()
            mock_logger = Mock()
            mock_logging_provider.get_logger.return_value = mock_logger
            
            # Mock paths system  
            mock_paths = Mock()
            mock_paths.output = output_dir
            # Don't mock exists() on the real Path object
            
            # Mock rollback service
            mock_rollback_service = Mock()
            mock_rollback_service.nation_slug = 'test-nation'
            mock_rollback_service.initialize_api_clients.return_value = True
            
            # Configure process_rollback_row to simulate realistic behavior
            def mock_process_rollback(row, import_type):
                # Simulate success for most records, failure for specific ones
                if row.get('Email') == 'bob@example.com':
                    return False, "Donation not found in NationBuilder"
                return True, "Successfully deleted donation"
            
            mock_rollback_service.process_rollback_row.side_effect = mock_process_rollback
            
            yield {
                'config': mock_config,
                'logging_provider': mock_logging_provider,
                'logger': mock_logger,
                'paths': mock_paths,
                'rollback_service': mock_rollback_service,
                'test_csv_file': str(test_csv_file),
                'test_csv_content': test_csv_content,
                'output_dir': output_dir
            }
    
    def test_core_rollback_processing_workflow(self, complete_mock_environment):
        """Test the complete core rollback processing workflow with real CSV data."""
        mocks = complete_mock_environment
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=mocks['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=mocks['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['test_success.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=mocks['test_csv_content']), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''),  \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('cdflow_cli.cli.commands_rollback.initialize_output_file') as mock_init_output, \
             patch('cdflow_cli.cli.commands_rollback.append_row_to_file') as mock_append, \
             patch('builtins.print'):
            
            # Mock file selection menu
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'test_success.csv'
            mock_menu_class.return_value = mock_menu
            
            # Execute the core rollback functionality
            result = run_rollback_cli(mocks['config'], mocks['logging_provider'])
            
            # Verify successful execution
            assert result == 0, f"Core rollback processing should succeed, but got result: {result}"
            
            # Verify core processing steps were executed
            mock_init_output.assert_called_once()  # Output file was initialized
            assert mock_append.call_count == 3, "Should have processed 3 CSV rows"
            
            # Verify rollback service was called for each row
            assert mocks['rollback_service'].process_rollback_row.call_count == 3
            
            # Verify the rollback service was called with correct parameters
            calls = mocks['rollback_service'].process_rollback_row.call_args_list
            assert calls[0][0][1] == 'CanadaHelps'  # import_type parameter
            
            # Verify rows were processed in reverse order (as per rollback logic)
            first_call_row = calls[0][0][0]  # First argument of first call
            assert first_call_row['Email'] == 'bob@example.com'  # Should be last row first
    
    def test_core_rollback_with_failures(self, complete_mock_environment):
        """Test core rollback processing when some donations fail to rollback."""
        mocks = complete_mock_environment

        # Configure all rollbacks to fail
        mocks['rollback_service'].process_rollback_row.side_effect = None
        mocks['rollback_service'].process_rollback_row.return_value = (False, "API connection failed")
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=mocks['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=mocks['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['test_success.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=mocks['test_csv_content']), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''), \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('cdflow_cli.cli.commands_rollback.initialize_output_file'), \
             patch('cdflow_cli.cli.commands_rollback.append_row_to_file') as mock_append, \
             patch('builtins.print'):
            
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'test_success.csv'
            mock_menu_class.return_value = mock_menu
            
            result = run_rollback_cli(mocks['config'], mocks['logging_provider'])
            
            # Should still return 0 (success) even with failed rollbacks
            assert result == 0
            
            # Verify all rows were attempted
            assert mocks['rollback_service'].process_rollback_row.call_count == 3
            
            # Verify all rows were written to output (with error messages)
            assert mock_append.call_count == 3
            
            # Verify error messages were added to rows
            append_calls = mock_append.call_args_list
            for call in append_calls:
                row_data = call[0][1]  # Second argument is the row data
                assert 'NB Error Message' in row_data
                assert row_data['NB Error Message'] == "API connection failed"
    
    def test_core_rollback_empty_file(self, complete_mock_environment):
        """Test core rollback processing with empty CSV file."""
        mocks = complete_mock_environment
        
        # Create empty CSV content (headers only)
        empty_csv = "Donor First Name,Donor Last Name,Email,Amount"
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=mocks['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=mocks['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['test_success.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=empty_csv), \
             patch('cdflow_cli.cli.commands_rollback.FileSelectionMenu') as mock_menu_class, \
             patch('builtins.input', return_value=''), \
             patch('cdflow_cli.cli.commands_rollback.prompt_for_rollback_confirmation', return_value=True), \
             patch('cdflow_cli.cli.commands_rollback.get_encoding', return_value=('utf-8', 0.99)), \
             patch('builtins.print'):
            
            mock_menu = Mock()
            mock_menu.show_menu.return_value = 'test_success.csv'
            mock_menu_class.return_value = mock_menu
            
            with patch('cdflow_cli.cli.commands_rollback.initialize_output_file'), \
                 patch('cdflow_cli.cli.commands_rollback.append_row_to_file') as mock_append, \
                 patch('cdflow_cli.cli.commands_rollback.process_rollback_data') as mock_process:
                result = run_rollback_cli(mocks['config'], mocks['logging_provider'])
                mock_process.assert_not_called()

            # Should return 1 (failure) for empty file
            assert result == 1

            # Should not have called rollback service
            assert mocks['rollback_service'].process_rollback_row.call_count == 0
            mock_append.assert_not_called()
    
    def test_core_rollback_import_type_detection(self, complete_mock_environment):
        """Test core rollback processing with different import types."""
        mocks = complete_mock_environment
        
        # Test PayPal CSV content
        paypal_csv = """Date,Time,Name,Type,Status,From Email Address,Gross,Fee
2024-01-01,12:00:00,John Doe,Payment,Completed,john@example.com,50.00,1.50"""
        
        with patch('cdflow_cli.cli.commands_rollback.clear_screen'), \
             patch('cdflow_cli.utils.paths.initialize_paths', return_value=mocks['paths']), \
             patch('cdflow_cli.cli.commands_rollback.DonationRollbackService', return_value=mocks['rollback_service']), \
             patch('cdflow_cli.cli.commands_rollback.get_success_csv_files', return_value=['paypal_success.csv']), \
             patch('cdflow_cli.cli.commands_rollback.safe_read_text_file', return_value=paypal_csv), \
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
            
            result = run_rollback_cli(mocks['config'], mocks['logging_provider'])
            
            assert result == 0
            
            # Verify rollback service was called with PayPal import type
            calls = mocks['rollback_service'].process_rollback_row.call_args_list
            assert len(calls) == 1
            assert calls[0][0][1] == 'PayPal'  # import_type should be PayPal
