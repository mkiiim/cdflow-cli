import pytest
import tempfile
import csv
from pathlib import Path
from unittest.mock import Mock, patch
from cdflow_cli.adapters.canadahelps.mapper import CHDonationMapper
from cdflow_cli.adapters.paypal.mapper import PPDonationMapper
from cdflow_cli.services.import_service import DonationImportService


class TestDataProcessingWorkflows:
    """Integration tests for data processing workflows."""
    
    @pytest.fixture
    def canadahelps_csv_file(self, temp_dir, sample_canadahelps_data):
        """Create a CanadaHelps CSV file for testing."""
        csv_file = temp_dir / 'canadahelps.csv'
        csv_file.write_text(sample_canadahelps_data)
        return csv_file
    
    @pytest.fixture
    def paypal_csv_file(self, temp_dir, sample_paypal_data):
        """Create a PayPal CSV file for testing."""
        csv_file = temp_dir / 'paypal.csv'
        csv_file.write_text(sample_paypal_data)
        return csv_file
    
    @pytest.fixture
    def mock_import_config(self, canadahelps_csv_file):
        """Mock import configuration."""
        return {
            'source': {
                'type': 'canadahelps',
                'file_path': str(canadahelps_csv_file)
            },
            'processing': {
                'batch_size': 2,
                'rate_limit': 60,
                'dry_run': True
            }
        }
    
    def test_canadahelps_data_parsing_workflow(self, canadahelps_csv_file):
        """Test complete CanadaHelps data parsing workflow."""
        # Read CSV file
        with open(canadahelps_csv_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Process each row
        donations = []
        for row in rows:
            # Validate row
            is_valid, error = CHDonationMapper.validate_row(row)
            assert is_valid, f"Row validation failed: {error}"
            
            # Parse donation data
            donation = CHDonationMapper(row)
            donations.append(donation)
        
        # Verify parsed data
        assert len(donations) == 3
        
        # Check first donation
        first_donation = donations[0]
        assert first_donation.NBfirst_name == 'John'
        assert first_donation.NBlast_name == 'Doe'
        assert first_donation.NBemail == 'test@example.com'
        assert first_donation.NBamount_in_cents == 2500  # 25.00 * 100
        
        # Check all donations have required fields
        for donation in donations:
            assert donation.NBfirst_name is not None
            assert donation.NBlast_name is not None
            assert donation.NBemail is not None
            assert donation.NBamount_in_cents > 0
            assert donation.NBsucceeded_at is not None
    
    def test_paypal_data_parsing_workflow(self, paypal_csv_file):
        """Test complete PayPal data parsing workflow."""
        # Read CSV file
        with open(paypal_csv_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Process each row
        donations = []
        for row in rows:
            # Validate row
            is_valid, error = PPDonationMapper.validate_row(row)
            assert is_valid, f"Row validation failed: {error}"
            
            # Parse donation data
            donation = PPDonationMapper(row)
            donations.append(donation)
        
        # Verify parsed data
        assert len(donations) == 3
        
        # Check first donation
        first_donation = donations[0]
        assert first_donation.NBfirst_name == 'John'
        assert first_donation.NBlast_name == 'Doe'
        assert first_donation.NBemail == 'test@example.com'
        assert first_donation.NBamount_in_cents == 2500  # 25.00 * 100
        assert first_donation.get_value_case_insensitive('Fee') == '1.25'
        assert first_donation.get_value_case_insensitive('Net') == '23.75'
        
        # Check currency handling
        for donation in donations:
            assert donation.get_value_case_insensitive('Currency') == 'CAD'
    
    @patch('cdflow_cli.services.import_service.NBPeople')
    @patch('cdflow_cli.services.import_service.NBDonation')
    @patch('cdflow_cli.services.import_service.NationBuilderOAuth')
    def test_import_service_workflow(self, mock_oauth, mock_donation, mock_people, 
                                   mock_import_config, mock_config_provider):
        """Test complete import service workflow."""
        # Setup mocks
        mock_config_provider.get_import_config.return_value = mock_import_config
        mock_config_provider.get_nationbuilder_config.return_value = {
            'slug': 'test-nation',
            'client_id': 'test-id',
            'client_secret': 'test-secret'
        }
        
        # Mock OAuth flow
        mock_auth = Mock()
        mock_auth.get_access_token.return_value = 'test-token'
        mock_oauth.return_value = mock_auth
        
        # Mock API clients
        mock_people_api = Mock()
        mock_donation_api = Mock()
        mock_people.return_value = mock_people_api
        mock_donation.return_value = mock_donation_api
        
        # Create service
        service = DonationImportService(config_provider=mock_config_provider)
        
        # Run import (in dry run mode)
        with patch.object(service, '_load_csv_data') as mock_load_csv:
            # Mock CSV data loading
            mock_csv_data = [
                {
                    'DONOR FIRST NAME': 'John',
                    'DONOR LAST NAME': 'Doe',
                    'DONOR EMAIL ADDRESS': 'john@example.com',
                    'AMOUNT': '25.00',
                    'DONATION DATE': '2024-01-15',
                    'DONATION TIME': '14:30:00',
                    'TRANSACTION NUMBER': 'CH-123456'
                }
            ]
            mock_load_csv.return_value = mock_csv_data
            
            # Run the service
            result = service.run()
            
            # Verify result
            assert result is not None
            assert 'processed' in result or 'status' in result
    
    def test_batch_processing_workflow(self, canadahelps_csv_file):
        """Test batch processing of donations."""
        # Read CSV data
        with open(canadahelps_csv_file, 'r') as f:
            reader = csv.DictReader(f)
            all_rows = list(reader)
        
        # Process in batches of 2
        batch_size = 2
        batches = []
        
        for i in range(0, len(all_rows), batch_size):
            batch = all_rows[i:i + batch_size]
            batches.append(batch)
        
        # Process each batch
        all_donations = []
        for batch_num, batch in enumerate(batches):
            batch_donations = []
            
            for row in batch:
                is_valid, error = CHDonationMapper.validate_row(row)
                if is_valid:
                    donation = CHDonationMapper.from_row(row)
                    batch_donations.append(donation)
            
            all_donations.extend(batch_donations)
            
            # Simulate rate limiting between batches
            if batch_num < len(batches) - 1:
                # In real implementation, this would be time.sleep()
                pass
        
        # Verify all donations were processed
        assert len(all_donations) == 3
    
    def test_error_handling_workflow(self, temp_dir):
        """Test error handling in data processing workflow."""
        # Create CSV with mixed valid and invalid data
        invalid_csv_content = """ID,DONOR FIRST NAME,DONOR LAST NAME,DONOR EMAIL ADDRESS,AMOUNT,DONATION DATE,DONATION TIME,TRANSACTION NUMBER
1,John,Doe,john@example.com,25.00,2024-01-15,14:30:00,CH-123456
2,Jane,Smith,,50.00,2024-01-16,15:30:00,CH-123457
3,Bob,Johnson,bob@example.com,invalid-amount,2024-01-17,16:30:00,CH-123458
4,Alice,Brown,alice@example.com,75.00,invalid-date,17:30:00,CH-123459"""
        
        csv_file = temp_dir / 'mixed_data.csv'
        csv_file.write_text(invalid_csv_content)
        
        # Process data with error handling
        valid_donations = []
        errors = []
        
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            
            for row_num, row in enumerate(reader, 1):
                try:
                    # Validate row
                    is_valid, validation_error = CHDonationMapper.validate_row(row)
                    if not is_valid:
                        errors.append(f"Row {row_num}: {validation_error}")
                        continue
                    
                    # Parse donation
                    donation = CHDonationMapper.from_row(row)
                    valid_donations.append(donation)
                    
                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")
        
        # Verify error handling
        assert len(valid_donations) == 1  # Only first row is completely valid
        assert len(errors) == 3  # Three rows have errors
        
        # Verify specific errors were caught
        assert any('empty' in error.lower() for error in errors)  # Empty email
        assert any('amount' in error.lower() for error in errors)  # Invalid amount
        assert any('date' in error.lower() for error in errors)  # Invalid date
    
    def test_data_transformation_workflow(self, canadahelps_csv_file):
        """Test data transformation and normalization workflow."""
        # Read and process data
        with open(canadahelps_csv_file, 'r') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Transform data for API submission
        api_ready_data = []
        
        for row in rows:
            donation = CHDonationMapper.from_row(row)
            
            # Transform to API format
            api_data = {
                'person': {
                    'first_name': donation.first_name,
                    'last_name': donation.last_name,
                    'email': donation.email,
                    'primary_address': {
                        'state': donation.province,
                        'zip': donation.postal_code
                    } if donation.province or donation.postal_code else None
                },
                'donation': {
                    'amount_in_cents': int(donation.amount * 100),
                    'payment_type': 'Credit Card',
                    'donated_at': donation.donation_date.isoformat(),
                    'tracking_code': donation.transaction_id
                }
            }
            
            api_ready_data.append(api_data)
        
        # Verify transformations
        assert len(api_ready_data) == 3
        
        # Check first record transformation
        first_record = api_ready_data[0]
        assert first_record['person']['first_name'] == 'John'
        assert first_record['person']['email'] == 'test@example.com'
        assert first_record['donation']['amount_in_cents'] == 2500  # $25.00 in cents
        assert 'donated_at' in first_record['donation']
        assert 'tracking_code' in first_record['donation']
    
    def test_duplicate_detection_workflow(self, temp_dir):
        """Test duplicate detection in data processing."""
        # Create CSV with duplicate data
        duplicate_csv_content = """ID,DONOR FIRST NAME,DONOR LAST NAME,DONOR EMAIL ADDRESS,AMOUNT,DONATION DATE,DONATION TIME,TRANSACTION NUMBER
1,John,Doe,john@example.com,25.00,2024-01-15,14:30:00,CH-123456
2,John,Doe,john@example.com,25.00,2024-01-15,14:30:00,CH-123456
3,Jane,Smith,jane@example.com,50.00,2024-01-16,15:30:00,CH-123457"""
        
        csv_file = temp_dir / 'duplicates.csv'
        csv_file.write_text(duplicate_csv_content)
        
        # Process with duplicate detection
        seen_transactions = set()
        unique_donations = []
        duplicates = []
        
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                donation = CHDonationMapper.from_row(row)
                
                # Create unique key for duplicate detection
                unique_key = (
                    donation.email,
                    donation.amount,
                    donation.donation_date.date(),
                    donation.transaction_id
                )
                
                if unique_key in seen_transactions:
                    duplicates.append(donation)
                else:
                    seen_transactions.add(unique_key)
                    unique_donations.append(donation)
        
        # Verify duplicate detection
        assert len(unique_donations) == 2  # Two unique donations
        assert len(duplicates) == 1  # One duplicate detected