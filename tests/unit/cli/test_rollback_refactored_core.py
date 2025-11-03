"""
Test the refactored core rollback business logic.

This test demonstrates that the extracted process_rollback_data function
is now fully testable without UI coupling or OAuth initialization.
"""
import pytest
from unittest.mock import Mock, patch, call
from io import StringIO

from cdflow_cli.cli.commands_rollback import process_rollback_data


class TestRollbackRefactoredCore:
    """Test the extracted core rollback business logic."""

    def test_process_rollback_data_success_all_records(self):
        """Test successful processing of all records."""
        # Arrange - Create test data
        rows = [
            {"NB Donation ID": "12345", "Email": "john@example.com", "Amount": "50.00"},
            {"NB Donation ID": "67890", "Email": "jane@example.com", "Amount": "75.00"}
        ]
        
        # Mock rollback service that always succeeds
        mock_service = Mock()
        mock_service.process_rollback_row.return_value = (True, "SUCCESS delete_donation :: 12345")
        
        # Mock other dependencies
        mock_paths = Mock()
        mock_logger = Mock()
        
        # Mock the append_row_to_file function
        with patch('cdflow_cli.cli.commands_rollback.append_row_to_file') as mock_append:
            # Act - Call the core business logic function
            success_count, fail_count = process_rollback_data(
                rows=rows,
                import_type="CanadaHelps",
                rollback_service=mock_service,
                rollback_filename="test_rollback.csv",
                reader_fieldnames=["NB Donation ID", "Email", "Amount", "NB Error Message"],
                encoding="utf-8",
                paths=mock_paths,
                logger=mock_logger
            )
        
        # Assert - Verify results
        assert success_count == 2
        assert fail_count == 0
        
        # Verify service was called for each row (in reverse order)
        assert mock_service.process_rollback_row.call_count == 2
        calls = mock_service.process_rollback_row.call_args_list
        
        # Verify reverse processing order
        first_call_row = calls[0][0][0]  # First positional arg of first call
        second_call_row = calls[1][0][0]  # First positional arg of second call
        assert first_call_row["Email"] == "jane@example.com"  # Last row processed first
        assert second_call_row["Email"] == "john@example.com"  # First row processed last
        
        # Verify logging calls
        mock_logger.notice.assert_called_with("📊 Processing 2 donation records...")
        mock_logger.info.assert_any_call("✅ Record 1 processed successfully")
        mock_logger.info.assert_any_call("✅ Record 2 processed successfully")
        
        # Verify output file writes
        assert mock_append.call_count == 2

    def test_process_rollback_data_mixed_results(self):
        """Test processing with some successes and some failures."""
        # Arrange - Create test data
        rows = [
            {"NB Donation ID": "12345", "Email": "john@example.com"},
            {"NB Donation ID": "", "Email": "jane@example.com"}  # Missing ID should fail
        ]
        
        # Mock rollback service with mixed results
        mock_service = Mock()
        mock_service.process_rollback_row.side_effect = [
            (False, "WARNING: No donation ID found"),  # First call (reversed order) fails
            (True, "SUCCESS delete_donation :: 12345")   # Second call succeeds
        ]
        
        mock_paths = Mock()
        mock_logger = Mock()
        
        with patch('cdflow_cli.cli.commands_rollback.append_row_to_file'):
            # Act
            success_count, fail_count = process_rollback_data(
                rows=rows,
                import_type="CanadaHelps", 
                rollback_service=mock_service,
                rollback_filename="test_rollback.csv",
                reader_fieldnames=["NB Donation ID", "Email", "NB Error Message"],
                encoding="utf-8",
                paths=mock_paths,
                logger=mock_logger
            )
        
        # Assert
        assert success_count == 1
        assert fail_count == 1
        
        # Verify failure logging (remember: reverse processing, so record 2 fails, record 1 succeeds)
        mock_logger.warning.assert_called_with("❌ Record 2 failed: WARNING: No donation ID found")  
        mock_logger.info.assert_called_with("✅ Record 1 processed successfully")

    def test_process_rollback_data_empty_rows(self):
        """Test processing with empty row list."""
        # Arrange
        rows = []
        mock_service = Mock()
        mock_paths = Mock()
        mock_logger = Mock()
        
        with patch('cdflow_cli.cli.commands_rollback.append_row_to_file'):
            # Act
            success_count, fail_count = process_rollback_data(
                rows=rows,
                import_type="CanadaHelps",
                rollback_service=mock_service,
                rollback_filename="test_rollback.csv", 
                reader_fieldnames=["NB Donation ID"],
                encoding="utf-8",
                paths=mock_paths,
                logger=mock_logger
            )
        
        # Assert
        assert success_count == 0
        assert fail_count == 0
        
        # Verify no service calls made
        mock_service.process_rollback_row.assert_not_called()
        
        # Verify initial logging
        mock_logger.notice.assert_called_with("📊 Processing 0 donation records...")

    def test_process_rollback_data_paypal_import_type(self):
        """Test processing with PayPal import type."""
        # Arrange
        rows = [{"NB Donation ID": "12345", "From Email Address": "test@paypal.com"}]
        mock_service = Mock()
        mock_service.process_rollback_row.return_value = (True, "SUCCESS")
        
        mock_paths = Mock()
        mock_logger = Mock()
        
        with patch('cdflow_cli.cli.commands_rollback.append_row_to_file'):
            # Act
            process_rollback_data(
                rows=rows,
                import_type="PayPal",  # Test PayPal specifically
                rollback_service=mock_service,
                rollback_filename="test_rollback.csv",
                reader_fieldnames=["NB Donation ID", "From Email Address"],
                encoding="utf-8",
                paths=mock_paths,
                logger=mock_logger
            )
        
        # Assert - Verify PayPal import type was passed to service
        mock_service.process_rollback_row.assert_called_once_with(
            {"NB Donation ID": "12345", "From Email Address": "test@paypal.com", "NB Error Message": "SUCCESS"},
            "PayPal"
        )

    def test_process_rollback_data_error_message_added_to_row(self):
        """Test that error messages are properly added to rows for output."""
        # Arrange
        rows = [{"NB Donation ID": "12345", "Email": "test@example.com"}]
        mock_service = Mock()
        mock_service.process_rollback_row.return_value = (True, "SUCCESS delete_donation :: 12345")
        
        mock_paths = Mock()
        mock_logger = Mock()
        
        with patch('cdflow_cli.cli.commands_rollback.append_row_to_file') as mock_append:
            # Act
            process_rollback_data(
                rows=rows,
                import_type="CanadaHelps",
                rollback_service=mock_service,
                rollback_filename="test_rollback.csv",
                reader_fieldnames=["NB Donation ID", "Email", "NB Error Message"],
                encoding="utf-8",
                paths=mock_paths,
                logger=mock_logger
            )
        
        # Assert - Verify error message was added to row before output
        mock_append.assert_called_once()
        written_row = mock_append.call_args[0][1]  # Second positional argument (row)
        assert written_row["NB Error Message"] == "SUCCESS delete_donation :: 12345"
        assert written_row["Email"] == "test@example.com"  # Original data preserved


if __name__ == "__main__":
    pytest.main([__file__])