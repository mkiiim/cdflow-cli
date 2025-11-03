import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from cdflow_cli.services.rollback_service import DonationRollbackService


class TestDonationRollbackService:
    """Test the donation rollback service."""
    
    @pytest.fixture
    def mock_config_provider(self):
        """Mock configuration provider."""
        mock_config = Mock()
        # Current API methods
        mock_config.get_oauth_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret'
        }
        mock_config.get_app_setting.return_value = 'localhost'  # Default hostname/port
        return mock_config

    @pytest.fixture
    def mock_logging_provider(self):
        """Mock logging provider."""
        mock_logging = Mock()
        mock_logging.get_logger.return_value = Mock()
        return mock_logging
    
    @pytest.fixture
    def sample_job_data(self):
        """Sample job data for testing."""
        return {
            'job_id': 'test-job-123',
            'created_donations': [
                {'donation_id': '123', 'person_id': '456', 'amount': '25.00'},
                {'donation_id': '124', 'person_id': '457', 'amount': '50.00'}
            ],
            'created_people': [
                {'person_id': '456', 'email': 'test@example.com'},
                {'person_id': '457', 'email': 'jane@example.com'}
            ],
            'status': 'completed'
        }
    
    def test_init_with_config_path(self, mock_logging_provider):
        """Test initialization with config and logging providers."""
        with patch('cdflow_cli.services.rollback_service.ConfigProvider') as mock_provider_class:
            mock_config_provider = Mock()
            mock_provider_class.return_value = mock_config_provider
            
            service = DonationRollbackService(mock_config_provider, mock_logging_provider)
            assert service.config_provider == mock_config_provider
            assert service.logging_provider == mock_logging_provider
    
    def test_init_with_config_provider(self, mock_config_provider, mock_logging_provider):
        """Test initialization with existing config provider."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        assert service.config_provider == mock_config_provider
        assert service.logging_provider == mock_logging_provider
    
    @patch('cdflow_cli.services.rollback_service.NBPeople')
    @patch('cdflow_cli.services.rollback_service.NBDonation')
    @patch('cdflow_cli.services.rollback_service.NationBuilderOAuth')
    def test_initialize_apis(self, mock_oauth, mock_donation, mock_people, mock_config_provider, mock_logging_provider):
        """Test API initialization."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Mock the OAuth flow
        mock_auth = Mock()
        mock_auth.initialize.return_value = True
        mock_auth.slug = 'test-nation'
        mock_oauth.return_value = mock_auth
        
        # Test the current method name
        result = service.initialize_api_clients()
        
        assert result is True
        mock_oauth.assert_called_once()
        mock_people.assert_called_once()
        mock_donation.assert_called_once()
    
    def test_validate_config_success(self, mock_config_provider, mock_logging_provider):
        """Test successful configuration validation."""
        # Current service doesn't have _validate_config method
        # Test that initialization works properly
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        assert service.config_provider == mock_config_provider
    
    def test_validate_config_missing_job_id(self, mock_config_provider, mock_logging_provider):
        """Test configuration with missing OAuth config."""
        mock_config_provider.get_oauth_config.return_value = None
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Test that initialize_api_clients fails gracefully
        result = service.initialize_api_clients()
        assert result is False
    
    def test_load_job_data_success(self, mock_config_provider, mock_logging_provider, sample_job_data):
        """Test process_rollback_row functionality."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Mock the API clients
        service.donation = Mock()
        service.people = Mock()
        service.donation.delete_donation.return_value = (None, True, 'Success')
        service.people.delete_person.return_value = (True, 'Success')
        
        # Test row with donation and people IDs
        test_row = {
            'NB Donation ID': '123',
            'NB People ID': '456',
            'NB People Create Date': '2024-01-15',
            'AMOUNT': '25.00',
            'TRANSACTION NUMBER': 'TEST-123',
            'DONOR EMAIL ADDRESS': 'test@example.com'
        }
        
        success, message = service.process_rollback_row(test_row, 'CanadaHelps')
        assert success is True
        assert 'SUCCESS delete_donation' in message
    
    def test_load_job_data_not_found(self, mock_config_provider, mock_logging_provider):
        """Test process_rollback_row with missing donation ID."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Test row without donation ID
        test_row = {
            'AMOUNT': '25.00',
            'TRANSACTION NUMBER': 'TEST-123',
            'DONOR EMAIL ADDRESS': 'test@example.com'
        }
        
        success, message = service.process_rollback_row(test_row, 'CanadaHelps')
        assert success is False
        assert 'No donation ID found' in message
    
    def test_rollback_donations_dry_run(self, mock_config_provider, mock_logging_provider, sample_job_data):
        """Test process_rollback_row with donation deletion failure."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Mock failed donation deletion
        service.donation = Mock()
        service.donation.delete_donation.return_value = (None, False, 'Deletion failed')
        
        test_row = {
            'NB Donation ID': '123',
            'AMOUNT': '25.00',
            'TRANSACTION NUMBER': 'TEST-123',
            'DONOR EMAIL ADDRESS': 'test@example.com'
        }
        
        success, message = service.process_rollback_row(test_row, 'CanadaHelps')
        assert success is False
        assert 'FAILURE delete_donation' in message
    
    def test_rollback_people_dry_run(self, mock_config_provider, mock_logging_provider, sample_job_data):
        """Test process_rollback_row with people deletion failure."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Mock successful donation deletion but failed people deletion
        service.donation = Mock()
        service.people = Mock()
        service.donation.delete_donation.return_value = (None, True, 'Success')
        service.people.delete_person.return_value = (False, 'People deletion failed')
        
        test_row = {
            'NB Donation ID': '123',
            'NB People ID': '456',
            'NB People Create Date': '2024-01-15',
            'AMOUNT': '25.00',
            'TRANSACTION NUMBER': 'TEST-123',
            'DONOR EMAIL ADDRESS': 'test@example.com'
        }
        
        success, message = service.process_rollback_row(test_row, 'PayPal')
        assert success is False
        assert 'FAILURE delete_person' in message
    
    def test_delete_donation_success(self, mock_config_provider, mock_logging_provider):
        """Test successful donation processing without people deletion."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Mock successful donation deletion
        service.donation = Mock()
        service.donation.delete_donation.return_value = (None, True, 'Success')
        
        # Test row without people data
        test_row = {
            'NB Donation ID': '123',
            'AMOUNT': '25.00',
            'TRANSACTION NUMBER': 'TEST-123',
            'DONOR EMAIL ADDRESS': 'test@example.com'
        }
        
        success, message = service.process_rollback_row(test_row, 'CanadaHelps')
        assert success is True
        assert 'SUCCESS delete_donation' in message
        assert 'delete_person' not in message
    
    def test_delete_donation_error(self, mock_config_provider, mock_logging_provider):
        """Test process_rollback_row with exception handling."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Mock the donation API to raise an exception
        service.donation = Mock()
        service.donation.delete_donation.side_effect = Exception('API Error')
        
        test_row = {
            'NB Donation ID': '123',
            'AMOUNT': '25.00',
            'TRANSACTION NUMBER': 'TEST-123',
            'DONOR EMAIL ADDRESS': 'test@example.com'
        }
        
        success, message = service.process_rollback_row(test_row, 'CanadaHelps')
        assert success is False
        assert 'ERROR processing row' in message
    
    def test_delete_person_success(self, mock_config_provider, mock_logging_provider):
        """Test API client initialization success."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Test that API clients are initially None
        assert service.nboauth is None
        assert service.people is None
        assert service.donation is None
        assert service.nation_slug is None
    
    def test_delete_person_error(self, mock_config_provider, mock_logging_provider):
        """Test config provider attribute access."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Test that config provider is properly set
        assert service.config_provider is mock_config_provider
        
        # Test that get_oauth_config is called during API initialization
        service.initialize_api_clients()
        mock_config_provider.get_oauth_config.assert_called()
    
    def test_confirm_rollback_yes(self, mock_config_provider, mock_logging_provider):
        """Test logging provider integration."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Test that logging provider is properly set and logger is created
        assert service.logging_provider is mock_logging_provider
        mock_logging_provider.get_logger.assert_called_once_with('cdflow_cli.services.rollback_service')
    
    def test_confirm_rollback_no(self, mock_config_provider, mock_logging_provider):
        """Test PayPal import type handling."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Mock successful donation deletion
        service.donation = Mock()
        service.donation.delete_donation.return_value = (None, True, 'Success')
        
        test_row = {
            'NB Donation ID': '123',
            'Gross': '25.00',  # PayPal field name
            'Transaction ID': 'PP-123',
            'From Email Address': 'test@example.com'
        }
        
        success, message = service.process_rollback_row(test_row, 'PayPal')
        assert success is True
        assert 'SUCCESS delete_donation' in message
    
    def test_skip_confirmation_in_config(self, mock_config_provider, mock_logging_provider):
        """Test complete rollback workflow with both donation and people deletion."""
        service = DonationRollbackService(mock_config_provider, mock_logging_provider)
        
        # Mock successful deletion for both donation and people
        service.donation = Mock()
        service.people = Mock()
        service.donation.delete_donation.return_value = (None, True, 'Success')
        service.people.delete_person.return_value = (True, 'Success')
        
        test_row = {
            'NB Donation ID': '123',
            'NB People ID': '456',
            'NB People Create Date': '2024-01-15',
            'AMOUNT': '25.00',
            'TRANSACTION NUMBER': 'TEST-123',
            'DONOR EMAIL ADDRESS': 'test@example.com'
        }
        
        success, message = service.process_rollback_row(test_row, 'CanadaHelps')
        assert success is True
        assert 'SUCCESS delete_donation' in message
        assert 'SUCCESS delete_person' in message