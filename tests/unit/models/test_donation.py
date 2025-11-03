import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from cdflow_cli.models.donation import DonationMapper


class TestDonationMapper:
    """Test the base DonationMapper class."""
    
    @pytest.fixture
    def sample_data(self):
        """Sample donation data for testing."""
        return {
            'First Name': 'John',
            'Last Name': 'Doe',
            'Email': 'john@example.com',
            'Amount': '25.00',
            'Date': '2024-01-15',
            'Time': '14:30:00'
        }
    
    @pytest.fixture
    def job_context(self):
        """Sample job context for testing."""
        return {
            'job_id': 'test-job-123',
            'machine_info': 'test-machine'
        }
    
    def test_init_basic(self, sample_data):
        """Test basic initialization."""
        donation = DonationMapper(sample_data)
        
        assert donation.data == sample_data
        assert donation.class_name == 'DonationMapper'
        assert donation.job_context is None
        assert donation.custom_fields_available == {}
    
    def test_init_with_job_context(self, sample_data, job_context):
        """Test initialization with job context."""
        donation = DonationMapper(sample_data, job_context=job_context)
        
        assert donation.job_context == job_context
    
    def test_init_with_custom_fields(self, sample_data):
        """Test initialization with custom fields."""
        custom_fields = {'custom_field_1': True, 'custom_field_2': False}
        donation = DonationMapper(sample_data, custom_fields_available=custom_fields)
        
        assert donation.custom_fields_available == custom_fields
    
    def test_keys_map_creation(self, sample_data):
        """Test case-insensitive key mapping."""
        donation = DonationMapper(sample_data)
        
        # Should have lowercase keys mapping to original keys
        assert 'first name' in donation.keys_map
        assert donation.keys_map['first name'] == 'First Name'
        assert 'email' in donation.keys_map
        assert donation.keys_map['email'] == 'Email'
    
    def test_keys_map_with_bom(self):
        """Test BOM character removal in keys."""
        data_with_bom = {
            '\ufeffFirst Name': 'John',  # BOM character
            'Email': 'john@example.com'
        }
        donation = DonationMapper(data_with_bom)
        
        # BOM should be removed from key mapping
        assert 'first name' in donation.keys_map
        assert donation.keys_map['first name'] == '\ufeffFirst Name'
    
    def test_get_value_case_insensitive(self, sample_data):
        """Test case-insensitive value retrieval."""
        donation = DonationMapper(sample_data)
        
        # Should work with various cases
        assert donation.get_value_case_insensitive('First Name') == 'John'
        assert donation.get_value_case_insensitive('first name') == 'John'
        assert donation.get_value_case_insensitive('FIRST NAME') == 'John'
        assert donation.get_value_case_insensitive('email') == 'john@example.com'
    
    def test_get_value_case_insensitive_missing(self, sample_data):
        """Test case-insensitive retrieval for missing fields."""
        donation = DonationMapper(sample_data)
        
        assert donation.get_value_case_insensitive('Missing Field') is None
    
    def test_initial_nb_fields(self, sample_data):
        """Test that NationBuilder fields are initialized."""
        donation = DonationMapper(sample_data)
        
        # Base class should initialize common NB fields to empty strings
        assert donation.NBfirst_name == ""
        assert donation.NBlast_name == ""
        assert donation.NBmiddle_name == ""
    
    def test_to_json_people_data(self, sample_data, job_context):
        """Test JSON people data generation."""
        donation = DonationMapper(sample_data, job_context=job_context)
        
        # Set some NB fields for testing
        donation.NBfirst_name = "John"
        donation.NBlast_name = "Doe"
        donation.NBemail = "john@example.com"
        
        json_data = donation.to_json_people_data()
        parsed_data = eval(json_data)  # Note: In real tests, use json.loads
        
        assert parsed_data['first_name'] == "John"
        assert parsed_data['last_name'] == "Doe"
        assert parsed_data['email'] == "john@example.com"
    
    def test_to_json_donation_data(self, sample_data, job_context):
        """Test JSON donation data generation."""
        donation = DonationMapper(sample_data, job_context=job_context)
        
        # Set some NB fields for testing
        donation.NBamount_in_cents = 2500
        donation.NBemail = "john@example.com"
        donation.NBsucceeded_at = "2024-01-15T14:30:00"
        
        json_data = donation.to_json_donation_data()
        parsed_data = eval(json_data)  # Note: In real tests, use json.loads
        
        assert parsed_data['amount_in_cents'] == 2500
        assert parsed_data['email'] == "john@example.com"
        assert parsed_data['succeeded_at'] == "2024-01-15T14:30:00"
    
    def test_parse_datetime_with_timezone(self, sample_data):
        """Test timezone-aware datetime parsing."""
        donation = DonationMapper(sample_data)
        
        # Test with valid datetime string
        result = donation.parse_datetime_with_timezone(
            "2024-01-15 14:30:00", 
            "%Y-%m-%d %H:%M:%S", 
            "test-123"
        )
        
        # Should return ISO format string
        assert isinstance(result, str)
        assert "2024-01-15" in result
        assert "T" in result  # ISO format separator
    
    def test_parse_datetime_with_timezone_invalid(self, sample_data):
        """Test datetime parsing with invalid format."""
        donation = DonationMapper(sample_data)
        
        # Test with invalid datetime string
        result = donation.parse_datetime_with_timezone(
            "invalid-date", 
            "%Y-%m-%d %H:%M:%S", 
            "test-123"
        )
        
        # Should return fallback datetime
        assert isinstance(result, str)
        # Should be current date (fallback)
        assert "T" in result  # ISO format