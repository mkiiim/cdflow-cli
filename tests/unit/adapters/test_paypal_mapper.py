import pytest
from datetime import datetime
from unittest.mock import Mock, patch
from cdflow_cli.adapters.paypal.mapper import PPDonationMapper


class TestPPDonationMapper:
    """Test PayPal donation data parser."""
    
    @pytest.fixture
    def valid_paypal_row(self):
        """Valid PayPal row data."""
        return {
            'Date': '01/15/2024',
            'Time': '14:30:00',
            'Name': 'John Doe',
            'Type': 'Donation',
            'Status': 'Completed',
            'Currency': 'CAD',
            'Gross': '25.00',
            'Fee': '1.25',
            'Net': '23.75',
            'From Email Address': 'john@example.com',
            'Transaction ID': 'PP-123456',
            'Subject': 'Monthly Donation',
            'Note': 'Keep up the great work!'
        }
    
    @pytest.fixture
    def business_paypal_row(self):
        """PayPal row with business name."""
        return {
            'Date': '01/16/2024',
            'Name': 'Acme Corp',
            'Type': 'Donation',
            'Status': 'Completed',
            'Currency': 'USD',
            'Amount': '100.00',
            'Fee': '3.20',
            'Net': '96.80',
            'From Email Address': 'billing@acme.com',
            'Subject': 'Corporate Donation'
        }
    
    def test_validate_row_success(self, valid_paypal_row):
        """Test successful row validation."""
        is_valid, error = PPDonationMapper.validate_row(valid_paypal_row)
        assert is_valid is True
        assert error is None
    
    def test_validate_row_missing_fields(self):
        """Test row validation with missing required fields."""
        incomplete_row = {
            'Date': '01/15/2024',
            'Name': 'John Doe'
            # Missing other required fields
        }
        
        is_valid, error = PPDonationMapper.validate_row(incomplete_row)
        assert is_valid is False
        assert "Missing required fields" in error
        assert "Gross" in error  # Actual parser uses "Gross" not "Amount"
        assert "From Email Address" in error
    
    def test_validate_row_non_donation_type(self, valid_paypal_row):
        """Test validation accepts non-donation transactions."""
        valid_paypal_row['Type'] = 'Payment'
        
        # Current parser: More permissive, accepts all PayPal transaction types
        # Filtering by type happens in business logic, not validation
        is_valid, error = PPDonationMapper.validate_row(valid_paypal_row)
        assert is_valid is True
        assert error is None
    
    def test_validate_row_incomplete_status(self, valid_paypal_row):
        """Test validation accepts incomplete transactions."""
        valid_paypal_row['Status'] = 'Pending'
        
        # Current parser: More permissive, accepts all PayPal transaction statuses
        # Status filtering happens in business logic, not validation
        is_valid, error = PPDonationMapper.validate_row(valid_paypal_row)
        assert is_valid is True
        assert error is None
    
    def test_from_row_valid_data(self, valid_paypal_row):
        """Test creating donation data from valid row."""
        donation = PPDonationMapper(valid_paypal_row)
        
        assert donation.NBfirst_name == 'John'
        assert donation.NBlast_name == 'Doe'
        assert donation.NBemail == 'john@example.com'
        assert donation.NBamount_in_cents == 2500  # 25.00 * 100
        assert donation.get_value_case_insensitive('Currency') == 'CAD'
        assert donation.get_value_case_insensitive('Fee') == '1.25'
        assert donation.get_value_case_insensitive('Net') == '23.75'
    
    def test_from_row_business_name(self, business_paypal_row):
        """Test handling business names."""
        # Fix the business row to use 'Gross' instead of 'Amount'
        business_paypal_row['Gross'] = business_paypal_row.pop('Amount', '100.00')
        business_paypal_row['Time'] = '14:30:00'
        business_paypal_row['Transaction ID'] = 'PP-789012'
        
        donation = PPDonationMapper(business_paypal_row)
        
        assert donation.NBfirst_name == 'Acme'
        assert donation.NBlast_name == 'Corp'
        assert donation.NBemail == 'billing@acme.com'
        assert donation.NBamount_in_cents == 10000  # 100.00 * 100
        assert donation.get_value_case_insensitive('Currency') == 'USD'
    
    def test_parse_date_formats(self, valid_paypal_row):
        """Test various date formats."""
        # PayPal parser uses DD/MM/YYYY format, not MM/DD/YYYY
        date_formats = [
            ('15/01/2024', datetime(2024, 1, 15)),  # DD/MM/YYYY (PayPal standard)
            ('01/01/2024', datetime(2024, 1, 1)),   # DD/MM/YYYY
            ('31/12/2023', datetime(2023, 12, 31)), # DD/MM/YYYY
        ]
        
        for date_str, expected_date in date_formats:
            valid_paypal_row['Date'] = date_str
            donation = PPDonationMapper(valid_paypal_row)
            # NBsucceeded_at is the parsed date field in ISO format
            parsed_date = datetime.fromisoformat(donation.NBsucceeded_at.replace('Z', '+00:00'))
            assert parsed_date.date() == expected_date.date()
    
    def test_parse_amount_formats(self, valid_paypal_row):
        """Test various amount formats."""
        # PayPal parser only handles standard decimal formats, not European comma separators
        amount_formats = [
            ('25.00', 2500),
            ('1250.00', 125000),  # Standard format
            ('-25.00', -2500)     # Negative (refund)
        ]
        
        for amount_str, expected_amount_cents in amount_formats:
            valid_paypal_row['Gross'] = amount_str  # Use 'Gross' not 'Amount'
            donation = PPDonationMapper(valid_paypal_row)
            assert donation.NBamount_in_cents == expected_amount_cents
    
    def test_invalid_amount_format(self, valid_paypal_row):
        """Test handling of invalid amount format."""
        valid_paypal_row['Gross'] = 'invalid'  # Use 'Gross' not 'Amount'
        
        with pytest.raises(ValueError):
            PPDonationMapper(valid_paypal_row)
    
    def test_invalid_date_format(self, valid_paypal_row):
        """Test handling of invalid date format."""
        valid_paypal_row['Date'] = 'invalid-date'
        
        # Current implementation uses fallback datetime, doesn't raise exception
        donation = PPDonationMapper(valid_paypal_row)
        # Should have fallback datetime string
        assert donation.NBsucceeded_at is not None
    
    def test_name_parsing_variations(self, valid_paypal_row):
        """Test various name formats."""
        name_variations = [
            ('John Doe', 'John', 'Doe'),
            ('John', 'John', ''),
            ('Dr. John Smith Jr.', 'Dr.', 'Jr.'),  # First and last word
            ('Mary Jane Watson', 'Mary', 'Watson'),  # First and last word
            ('', '', '')  # Empty name
        ]
        
        for full_name, expected_first, expected_last in name_variations:
            valid_paypal_row['Name'] = full_name
            donation = PPDonationMapper(valid_paypal_row)
            assert donation.NBfirst_name == expected_first
            assert donation.NBlast_name == expected_last
    
    def test_currency_handling(self, valid_paypal_row):
        """Test different currency codes."""
        currencies = ['CAD', 'USD', 'EUR', 'GBP']
        
        for currency in currencies:
            valid_paypal_row['Currency'] = currency
            donation = PPDonationMapper(valid_paypal_row)
            assert donation.get_value_case_insensitive('Currency') == currency
    
    def test_fee_and_net_calculation(self, valid_paypal_row):
        """Test fee and net amount handling."""
        valid_paypal_row['Gross'] = '100.00'  # Use 'Gross' not 'Amount'
        valid_paypal_row['Fee'] = '3.50'
        valid_paypal_row['Net'] = '96.50'
        
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.NBamount_in_cents == 10000  # 100.00 * 100
        assert donation.get_value_case_insensitive('Fee') == '3.50'
        assert donation.get_value_case_insensitive('Net') == '96.50'
    
    def test_missing_fee_data(self, valid_paypal_row):
        """Test handling when fee data is missing."""
        valid_paypal_row['Fee'] = ''
        valid_paypal_row['Net'] = ''
        
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.get_value_case_insensitive('Fee') == ''
        assert donation.get_value_case_insensitive('Net') == ''
    
    def test_subject_and_note_extraction(self, valid_paypal_row):
        """Test subject and note field extraction."""
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.get_value_case_insensitive('Subject') == 'Monthly Donation'
        assert donation.get_value_case_insensitive('Note') == 'Keep up the great work!'
    
    def test_transaction_id_without_plugin(self, valid_paypal_row):
        """Test transaction ID when no plugin is configured."""
        from cdflow_cli.plugins.registry import clear_registry

        clear_registry()
        donation = PPDonationMapper(valid_paypal_row)

        # Without plugin, check_number should be None (Option B)
        assert donation.NBcheck_number is None

    def test_check_number_via_plugin(self, valid_paypal_row, tmp_path):
        """Test check_number is set via plugin."""
        from cdflow_cli.plugins.registry import clear_registry
        from cdflow_cli.plugins.loader import load_plugins

        clear_registry()
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("paypal", "row_transformer")
def set_check_number(row_data: dict) -> dict:
    transaction_id = row_data.get("Transaction ID", "")
    row_data["_check_number"] = f"PP_{transaction_id}"
    return row_data
'''
        (plugins_dir / "check_number.py").write_text(plugin_code)
        load_plugins("paypal", plugins_dir)

        donation = PPDonationMapper(valid_paypal_row)
        assert donation.NBcheck_number == "PP_PP-123456"
        assert len(donation.NBcheck_number) > 3

        # Should be consistent for same data
        donation2 = PPDonationMapper(valid_paypal_row)
        assert donation.NBcheck_number == donation2.NBcheck_number

        clear_registry()
    
    def test_timezone_handling(self, valid_paypal_row):
        """Test timezone handling for PayPal dates."""
        donation = PPDonationMapper(valid_paypal_row)
        
        # Should have parsed date as ISO string
        assert donation.NBsucceeded_at is not None
        assert isinstance(donation.NBsucceeded_at, str)
        # Should be parseable as ISO datetime
        parsed_date = datetime.fromisoformat(donation.NBsucceeded_at.replace('Z', '+00:00'))
        assert parsed_date is not None

    def test_validate_row_missing_name_and_email(self):
        """Test validation failure when both Name and Email are empty (line 43)."""
        incomplete_row = {
            'Name': '',  # Empty name
            'From Email Address': '',  # Empty email
            'Date': '01/15/2024',
            'Time': '14:30:00',
            'Type': 'Donation',
            'Status': 'Completed',
            'Gross': '25.00',
            'Transaction ID': 'PP-123456'
        }
        
        is_valid, error = PPDonationMapper.validate_row(incomplete_row)
        assert is_valid is False
        assert "Either Name or Email must have a value" in error

    def test_empty_gross_amount_fallback(self, valid_paypal_row):
        """Test empty gross amount fallback to 0 (line 85)."""
        valid_paypal_row['Gross'] = ''  # Empty gross amount
        
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.NBamount_in_cents == 0

    def test_missing_date_time_fallback(self, valid_paypal_row):
        """Test missing date/time fallback logging."""
        # Remove date and time to trigger fallback
        del valid_paypal_row['Date']
        del valid_paypal_row['Time']

        with patch('cdflow_cli.models.donation.logger') as mock_base_logger:
            donation = PPDonationMapper(valid_paypal_row)

            # Should trigger warning for missing date and info log for fallback (both in base class)
            mock_base_logger.warning.assert_called_once()
            assert mock_base_logger.info.call_count >= 1  # DEBUG fallback log

            # Should still have a valid datetime (fallback)
            assert donation.NBsucceeded_at is not None

            # Verify warning message contains transaction number
            warning_call = mock_base_logger.warning.call_args[0][0]
            assert "Missing date or time for record" in warning_call
            assert valid_paypal_row['Transaction ID'] in warning_call

            # Verify one of the info calls contains fallback message
            info_calls = [call[0][0] for call in mock_base_logger.info.call_args_list]
            fallback_found = any("MISSING DATA FALLBACK" in call for call in info_calls)
            assert fallback_found

    def test_timezone_fallback_without_timezone_value(self, valid_paypal_row):
        """Test timezone fallback when no timezone value provided (line 170)."""
        # Remove timezone to trigger fallback path
        valid_paypal_row.pop('TimeZone', None)  # Make sure no timezone field
        
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.NBsucceeded_at is not None

    def test_timezone_aware_parsing_with_timezone_value(self, valid_paypal_row):
        """Test timezone-aware parsing when timezone value is provided (line 168)."""
        # Add timezone to trigger timezone-aware parsing
        valid_paypal_row['TimeZone'] = 'EST'  # Provide timezone value
        
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.NBsucceeded_at is not None

    def test_parse_datetime_with_paypal_timezone_method(self, valid_paypal_row):
        """Test _parse_datetime internal method with PayPal format and timezone."""
        donation = PPDonationMapper(valid_paypal_row)

        # Test the internal parsing method with PayPal format and timezone
        result = donation._parse_datetime(
            "15/01/2024 14:30:00", "%d/%m/%Y %H:%M:%S", "EST", "TEST-123"
        )
        assert result is not None
        assert isinstance(result, str)

    def test_is_eligible_all_conditions_met(self, valid_paypal_row):
        """Test is_eligible() when all conditions are met (lines 199-217)."""
        valid_paypal_row['Type'] = 'Subscription Payment'  # Valid type
        valid_paypal_row['Custom Number'] = ''  # Empty custom number (required)
        
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.data.get("_skip_row") != True

    def test_mapper_allows_missing_name_email(self, valid_paypal_row):
        """Test mapper doesn't enforce eligibility - that's done by plugins."""
        valid_paypal_row['Name'] = ''
        valid_paypal_row['From Email Address'] = ''

        # Mapper should allow this - eligibility is plugin responsibility
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.data.get("_skip_row") != True  # No plugin, so not filtered

    def test_is_eligible_with_skip_flag(self, valid_paypal_row):
        """Test is_eligible() when plugin sets _skip_row flag."""
        valid_paypal_row['_skip_row'] = True  # Plugin marked for skipping

        donation = PPDonationMapper(valid_paypal_row)
        assert donation.data.get("_skip_row") == True

    def test_is_eligible_plugin_based_filtering(self, valid_paypal_row, tmp_path):
        """Test is_eligible() with plugin-based filtering."""
        from cdflow_cli.plugins.registry import clear_registry
        from cdflow_cli.plugins.loader import load_plugins

        clear_registry()
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create eligibility filter plugin
        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("paypal", "row_transformer")
def filter_custom_number(row_data: dict) -> dict:
    if row_data.get("Custom Number"):
        row_data["_skip_row"] = True
    return row_data
'''
        (plugins_dir / "filter.py").write_text(plugin_code)
        load_plugins("paypal", plugins_dir)

        # Test with Custom Number (should be filtered)
        valid_paypal_row['Custom Number'] = 'DUPLICATE-123'
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.data.get("_skip_row") == True

        clear_registry()

    def test_lookup_person_by_email_success(self, valid_paypal_row):
        """Test lookup_person() uses base class default (email lookup)."""
        donation = PPDonationMapper(valid_paypal_row)

        mock_people_client = Mock()
        mock_people_client.get_personid_by_email.return_value = ("person_123", True, "Found")

        person_id, success, message = donation.lookup_person(mock_people_client)

        assert person_id == "person_123"
        assert success == True
        assert message == "Found"

    def test_tracking_code_plugin(self, valid_paypal_row, tmp_path):
        """Test tracking code via plugin."""
        from cdflow_cli.plugins.registry import clear_registry
        from cdflow_cli.plugins.loader import load_plugins

        clear_registry()
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create tracking code plugin
        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("paypal", "row_transformer")
def map_tracking(row_data: dict) -> dict:
    item_title = str(row_data.get("Item Title", "")).lower()
    if "month" in item_title:
        row_data["_tracking_code"] = "membership_paypal_monthly"
    else:
        row_data["_tracking_code"] = "donation_paypal"
    return row_data
'''
        (plugins_dir / "tracking.py").write_text(plugin_code)
        load_plugins("paypal", plugins_dir)

        # Test monthly
        monthly_row = valid_paypal_row.copy()
        monthly_row['Item Title'] = 'Monthly Membership'
        donation = PPDonationMapper(monthly_row)
        assert donation.NBtracking_code_slug == "membership_paypal_monthly"

        # Test default
        onetime_row = valid_paypal_row.copy()
        onetime_row['Item Title'] = 'One-time Donation'
        donation2 = PPDonationMapper(onetime_row)
        assert donation2.NBtracking_code_slug == "donation_paypal"

        clear_registry()

    def test_payment_type_plugin(self, valid_paypal_row, tmp_path):
        """Test payment type via plugin."""
        from cdflow_cli.plugins.registry import clear_registry
        from cdflow_cli.plugins.loader import load_plugins

        clear_registry()
        plugins_dir = tmp_path / "plugins"
        plugins_dir.mkdir()

        # Create payment type plugin
        plugin_code = '''
from cdflow_cli.plugins.registry import register_plugin

@register_plugin("paypal", "row_transformer")
def map_payment_type(row_data: dict) -> dict:
    if row_data.get("Type") == "Subscription Payment":
        row_data["_payment_type"] = "Recurring Credit Card"
    else:
        row_data["_payment_type"] = "Credit Card"
    return row_data
'''
        (plugins_dir / "payment.py").write_text(plugin_code)
        load_plugins("paypal", plugins_dir)

        # Test subscription
        valid_paypal_row['Type'] = 'Subscription Payment'
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.NBpayment_type_name == "Recurring Credit Card"

        # Test default
        valid_paypal_row['Type'] = 'Direct Credit Card Payment'
        donation = PPDonationMapper(valid_paypal_row)
        assert donation.NBpayment_type_name == "Credit Card"

        clear_registry()

    def test_defaults_without_plugins(self, valid_paypal_row):
        """Test defaults when no plugins are configured."""
        from cdflow_cli.plugins.registry import clear_registry

        clear_registry()

        donation = PPDonationMapper(valid_paypal_row)

        # Without plugins, fields should be None (Option B - not set by plugin)
        assert donation.NBtracking_code_slug is None
        assert donation.NBpayment_type_name is None
        assert donation.NBcheck_number is None
        assert donation.data.get("_skip_row") != True  # Has name and email