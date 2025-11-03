"""
Basic functionality tests that verify the core CLI components work.
"""
import pytest
from unittest.mock import Mock, patch


class TestBasicImports:
    """Test that we can import the main components."""
    
    def test_import_main_cli(self):
        """Test that we can import the main CLI module."""
        from cdflow_cli.cli.main import main, get_version
        assert callable(main)
        assert callable(get_version)
    
    def test_import_commands_init(self):
        """Test that we can import the init command."""
        from cdflow_cli.cli.commands_init import main, get_template_content
        assert callable(main)
        assert callable(get_template_content)
    
    def test_import_canadahelps_parser(self):
        """Test that we can import CanadaHelps parser."""
        from cdflow_cli.adapters.canadahelps.mapper import CHDonationMapper
        assert hasattr(CHDonationMapper, 'validate_row')
    
    def test_import_paypal_parser(self):
        """Test that we can import PayPal parser."""
        from cdflow_cli.adapters.paypal.mapper import PPDonationMapper
        assert hasattr(PPDonationMapper, 'validate_row')
    
    def test_import_nb_client(self):
        """Test that we can import NationBuilder client."""
        from cdflow_cli.adapters.nationbuilder.client import NBClient
        assert callable(NBClient)
    
    def test_import_config_provider(self):
        """Test that we can import config provider."""
        from cdflow_cli.utils.config import ConfigProvider
        assert callable(ConfigProvider)


class TestVersionFunction:
    """Test the version function works."""
    
    def test_get_version_returns_string(self):
        """Test get_version returns a string."""
        from cdflow_cli.cli.main import get_version
        version = get_version()
        assert isinstance(version, str)
        assert len(version) > 0


class TestValidation:
    """Test basic validation functions."""
    
    def test_canadahelps_validation_basic(self):
        """Test basic CanadaHelps validation."""
        from cdflow_cli.adapters.canadahelps.mapper import CHDonationMapper
        
        # Test with missing fields
        empty_row = {}
        is_valid, error = CHDonationMapper.validate_row(empty_row)
        assert is_valid is False
        assert "Missing required fields" in error
    
    def test_paypal_validation_basic(self):
        """Test basic PayPal validation."""
        from cdflow_cli.adapters.paypal.mapper import PPDonationMapper
        
        # Test with missing fields  
        empty_row = {}
        is_valid, error = PPDonationMapper.validate_row(empty_row)
        assert is_valid is False
        assert "Missing required fields" in error


class TestNBClient:
    """Test NationBuilder client basic functionality."""
    
    def test_nb_client_creation(self):
        """Test NBClient can be created."""
        from cdflow_cli.adapters.nationbuilder.client import NBClient
        
        mock_oauth = Mock()
        mock_oauth.nb_jwt_token = 'test-token'
        mock_oauth.slug = 'test-nation'
        
        client = NBClient(mock_oauth)
        assert client.nation_slug == 'test-nation'
        assert client.access_token == 'test-token'
        assert 'Authorization' in client.headers