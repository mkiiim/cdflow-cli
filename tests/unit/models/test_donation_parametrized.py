import pytest
from datetime import datetime
from cdflow_cli.models.donation import DonationMapper


class TestParametrizedExamples:
    """Examples of parametrized testing patterns."""
    
    @pytest.mark.parametrize("field_name,expected_value", [
        ('First Name', 'John'),
        ('first name', 'John'), 
        ('FIRST NAME', 'John'),
        ('Email', 'john@example.com'),
        ('email', 'john@example.com'),
        ('EMAIL', 'john@example.com')
    ])
    def test_case_insensitive_access_parametrized(self, field_name, expected_value):
        """Test case-insensitive field access with multiple cases."""
        sample_data = {
            'First Name': 'John',
            'Email': 'john@example.com'
        }
        donation = DonationMapper(sample_data)
        
        result = donation.get_value_case_insensitive(field_name)
        assert result == expected_value
    
    @pytest.mark.parametrize("dirty_key,clean_key", [
        ('\ufeffFirst Name', 'first name'),      # BOM character
        ('\ufeffEMAIL', 'email'),                # BOM + caps
        ('Amount', 'amount'),                     # Normal case
        ('PHONE NUMBER', 'phone number'),        # All caps with space
        ('Last Name', 'last name'),              # Mixed case
    ])
    def test_keys_map_cleaning_parametrized(self, dirty_key, clean_key):
        """Test that various dirty keys get cleaned properly."""
        test_data = {dirty_key: 'test_value'}
        donation = DonationMapper(test_data)
        
        # Clean key should exist in keys_map
        assert clean_key in donation.keys_map
        # And should map back to original dirty key
        assert donation.keys_map[clean_key] == dirty_key
    
    @pytest.mark.parametrize("amount_string,expected_cents", [
        ('25.00', 2500),
        ('1250.00', 125000),
        ('0.99', 99),
        ('-25.00', -2500),  # Refunds
        ('1000000.00', 100000000)  # Large amounts
    ])
    def test_amount_conversion_examples(self, amount_string, expected_cents):
        """Example of how amount conversion testing might work."""
        # This is a conceptual example - your actual conversion logic may differ
        # Converting string dollars to cents
        actual_cents = int(float(amount_string) * 100)
        assert actual_cents == expected_cents
    
    @pytest.mark.parametrize("invalid_field", [
        'NonExistentField',
        'missing_field', 
        'DOES_NOT_EXIST',
        ''  # Empty string
    ])
    def test_missing_fields_return_none(self, invalid_field):
        """Test that missing fields consistently return None."""
        sample_data = {'First Name': 'John'}
        donation = DonationMapper(sample_data)
        
        result = donation.get_value_case_insensitive(invalid_field)
        assert result is None
    
    @pytest.mark.parametrize("test_data,expected_keys", [
        # Single field
        ({'Name': 'John'}, ['name']),
        
        # Multiple fields
        ({'First Name': 'John', 'Email': 'john@example.com'}, ['first name', 'email']),
        
        # BOM characters
        ({'\ufeffFirst Name': 'John'}, ['first name']),
        
        # Mixed cases
        ({'FIRST NAME': 'John', 'last_name': 'Doe'}, ['first name', 'last_name']),
    ])
    def test_keys_map_contents(self, test_data, expected_keys):
        """Test that keys_map contains expected clean keys."""
        donation = DonationMapper(test_data)
        
        # All expected keys should be in keys_map
        for key in expected_keys:
            assert key in donation.keys_map
        
        # keys_map should have exactly the expected number of keys
        assert len(donation.keys_map) == len(expected_keys)