import pytest
from unittest.mock import Mock, patch, MagicMock
from cdflow_cli.services.import_service import DonationImportService


class TestDonationImportServiceSimple:
    """Simple tests for the donation import service."""
    
    @pytest.fixture
    def mock_config_provider(self):
        """Mock configuration provider."""
        mock_config = Mock()
        mock_config.get_nationbuilder_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret'
        }
        # Mock logging config to return proper values
        mock_config.get_logging_config.return_value = {
            'file_level': 'DEBUG',
            'console_level': 'INFO'
        }
        # Mock paths configuration
        mock_config.get_app_setting.return_value = './storage'
        return mock_config
    
    def test_init_with_config_provider(self, mock_config_provider):
        """Test initialization with existing config provider."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_paths:
            with patch('cdflow_cli.services.import_service.get_logging_provider') as mock_logging_provider:
                # Mock paths system
                mock_paths.side_effect = RuntimeError('Not initialized')
                
                # Mock logging provider
                mock_logging_provider.return_value = Mock()
                
                service = DonationImportService(config_provider=mock_config_provider)
                assert service.config == mock_config_provider
                assert service.job_context is None
    
    def test_init_with_job_context(self, mock_config_provider):
        """Test initialization with job context."""
        job_context = {'job_id': 'test-123', 'machine_info': 'test-machine'}
        
        with patch('cdflow_cli.services.import_service.get_paths') as mock_paths:
            with patch('cdflow_cli.services.import_service.get_logging_provider') as mock_logging_provider:
                # Mock paths system
                mock_paths.side_effect = RuntimeError('Not initialized')
                
                # Mock logging provider
                mock_logging_provider.return_value = Mock()
                
                service = DonationImportService(
                    config_provider=mock_config_provider,
                    job_context=job_context
                )
                assert service.config == mock_config_provider
                assert service.job_context == job_context

    def test_append_row_to_file_filters_plugin_fields(self, mock_config_provider, tmp_path):
        """Test that _append_row_to_file filters out plugin-added fields."""
        with patch('cdflow_cli.services.import_service.get_paths') as mock_get_paths:
            with patch('cdflow_cli.services.import_service.get_logging_provider'):
                # Mock paths to use tmp_path
                mock_paths = Mock()
                mock_paths.output = tmp_path
                mock_get_paths.return_value = mock_paths

                service = DonationImportService(config_provider=mock_config_provider)

                # Create a row with both regular and plugin fields
                row = {
                    "Name": "John Doe",
                    "Email": "john@example.com",
                    "Amount": "25.00",
                    "_tracking_code": "membership_paypal_monthly",  # Plugin field
                    "_payment_type": "Recurring Credit Card",  # Plugin field
                    "_skip_row": False  # Plugin field
                }

                fieldnames = ["Name", "Email", "Amount"]
                filename = "test_output.csv"

                # Initialize the file first
                service._initialize_output_file(filename, fieldnames, "utf-8")

                # Append the row
                service._append_row_to_file(filename, row, fieldnames, "utf-8")

                # Read the file and verify plugin fields were filtered
                output_file = tmp_path / filename
                content = output_file.read_text(encoding="utf-8")

                # Should contain regular fields
                assert "John Doe" in content
                assert "john@example.com" in content
                assert "25.00" in content

                # Should NOT contain plugin field values
                assert "_tracking_code" not in content
                assert "membership_paypal_monthly" not in content
                assert "_payment_type" not in content
                assert "Recurring Credit Card" not in content
                assert "_skip_row" not in content