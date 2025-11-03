"""
Comprehensive tests for NationBuilder Donation API client.

Tests all methods in NBDonation class with comprehensive edge case coverage.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
import json
from cdflow_cli.adapters.nationbuilder.donation_api import NBDonation
from cdflow_cli.adapters.nationbuilder.oauth import NationBuilderOAuth


@patch('cdflow_cli.adapters.nationbuilder.oauth.NationBuilderOAuth.ensure_valid_nb_jwt', lambda x: x)
class TestNBDonation:
    """Test NationBuilder Donation API client."""
    
    @pytest.fixture
    def mock_oauth(self):
        """Mock OAuth instance."""
        oauth = Mock(spec=NationBuilderOAuth)
        oauth.slug = "test-nation"  # Required by NBClient
        oauth.nb_nation_slug = "test-nation"
        oauth.nb_jwt_token = "test-jwt-token"
        oauth.nb_refresh_token = "test-refresh-token"
        oauth.nb_token_expires_in = 3600
        oauth.nb_token_created_at = 1234567890
        return oauth
    
    @pytest.fixture
    def donation_client(self, mock_oauth):
        """Create NBDonation client with mocked OAuth."""
        return NBDonation(mock_oauth)
    
    def test_init_sets_base_url(self, donation_client):
        """Test that initialization sets correct base URL."""
        assert "donations" in donation_client.base_url
        assert donation_client.base_url.endswith("/donations")
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_get_donationid_by_params_success_match_found(self, mock_get, donation_client):
        """Test successful donation lookup with matching check number."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"id": 1, "check_number": "CHECK-123", "amount_in_cents": 2500},
                {"id": 2, "check_number": "CHECK-456", "amount_in_cents": 5000},
                {"id": 3, "check_number": "CHECK-789", "amount_in_cents": 1000}
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"):
            
            params = {"succeeded_at": "2024-01-15"}
            donation_id, success, message = donation_client.get_donationid_by_params(params, "CHECK-456")
            
            assert donation_id == 2
            assert success is True
            assert message == "Success"
            
            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "search?succeeded_at=2024-01-15" in call_args[1]['url']
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_get_donationid_by_params_success_no_match(self, mock_get, donation_client):
        """Test donation lookup with no matching check number."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"id": 1, "check_number": "CHECK-123", "amount_in_cents": 2500},
                {"id": 2, "check_number": "CHECK-456", "amount_in_cents": 5000}
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"):
            
            params = {"succeeded_at": "2024-01-15"}
            donation_id, success, message = donation_client.get_donationid_by_params(params, "NOT-FOUND")
            
            assert donation_id is None
            assert success is False
            assert message == "Success"
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_get_donationid_by_params_empty_results(self, mock_get, donation_client):
        """Test donation lookup with empty results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"):
            
            params = {"succeeded_at": "2024-01-15"}
            donation_id, success, message = donation_client.get_donationid_by_params(params, "CHECK-123")
            
            assert donation_id is None
            assert success is False
            assert message == "Success"
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_get_donationid_by_params_http_error(self, mock_get, donation_client):
        """Test donation lookup with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="HTTP 404"):
            
            params = {"succeeded_at": "2024-01-15"}
            donation_id, success, message = donation_client.get_donationid_by_params(params, "CHECK-123")
            
            assert donation_id is None
            assert success is False
            assert message == "HTTP 404"
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_get_donationid_by_params_json_error(self, mock_get, donation_client):
        """Test donation lookup with JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"):
            
            params = {"succeeded_at": "2024-01-15"}
            donation_id, success, message = donation_client.get_donationid_by_params(params, "CHECK-123")
            
            assert donation_id is None
            assert success is False
            assert "JSON parsing error" in message
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_get_donationid_by_params_key_error(self, mock_get, donation_client):
        """Test donation lookup with KeyError in response parsing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = KeyError("results")
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"):
            
            params = {"succeeded_at": "2024-01-15"}
            donation_id, success, message = donation_client.get_donationid_by_params(params, "CHECK-123")
            
            assert donation_id is None
            assert success is False
            assert "JSON parsing error" in message
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.post')
    def test_create_donation_success_201(self, mock_post, donation_client):
        """Test successful donation creation with 201 status code."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "donation": {"id": 12345, "amount_in_cents": 2500}
        }
        mock_post.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Created"):
            
            donation_data = {
                "amount_in_cents": 2500,
                "succeeded_at": "2024-01-15T10:00:00Z",
                "check_number": "DONATE-123"
            }
            
            donation_id, success, message = donation_client.create_donation(donation_data)
            
            assert donation_id == 12345
            assert success is True
            assert message == "Created"
            
            # Verify API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]['json'] == {"donation": donation_data}
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.post')
    def test_create_donation_success_200(self, mock_post, donation_client):
        """Test successful donation creation with 200 status code."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "donation": {"id": 54321, "amount_in_cents": 5000}
        }
        mock_post.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"):
            
            donation_data = {
                "amount_in_cents": 5000,
                "succeeded_at": "2024-01-15T10:00:00Z"
            }
            
            donation_id, success, message = donation_client.create_donation(donation_data)
            
            assert donation_id == 54321
            assert success is True
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.post')
    def test_create_donation_missing_id_in_response(self, mock_post, donation_client):
        """Test donation creation with missing ID in response."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "donation": {}  # Missing ID
        }
        mock_post.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Created"):
            
            donation_data = {"amount_in_cents": 2500}
            donation_id, success, message = donation_client.create_donation(donation_data)
            
            assert donation_id is None
            assert success is False
            assert message == "Missing donation ID in response"
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.post')
    def test_create_donation_failure(self, mock_post, donation_client):
        """Test donation creation failure."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Bad request"):
            
            donation_data = {"invalid": "data"}
            donation_id, success, message = donation_client.create_donation(donation_data)
            
            assert donation_id is None
            assert success is False
            assert message == "Bad request"
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.post')
    def test_create_donation_json_error(self, mock_post, donation_client):
        """Test donation creation with JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Created"):
            
            donation_data = {"amount_in_cents": 2500}
            donation_id, success, message = donation_client.create_donation(donation_data)
            
            assert donation_id is None
            assert success is False
            assert "JSON parsing error" in message
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_detect_custom_donation_fields_success_with_fields(self, mock_get, donation_client):
        """Test successful custom field detection with fields present."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 1,
                    "amount_in_cents": 2500,
                    "import_job_id": "job123",
                    "import_job_source": "canadahelps"
                    # Note: missing custom fields would not be present in response
                }
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.donation_api.logger') as mock_logger:
            
            result = donation_client.detect_custom_donation_fields()
            
            assert result == {
                "import_job_id": True,
                "import_job_source": True
            }
            mock_logger.debug.assert_called_with("Custom field detection: {'import_job_id': True, 'import_job_source': True}")
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_detect_custom_donation_fields_success_without_fields(self, mock_get, donation_client):
        """Test custom field detection with fields not present."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 1,
                    "amount_in_cents": 2500
                    # Note: custom fields not present
                }
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.donation_api.logger') as mock_logger:
            
            result = donation_client.detect_custom_donation_fields()
            
            assert result == {
                "import_job_id": False,
                "import_job_source": False
            }
            mock_logger.debug.assert_called_with("Custom field detection: {'import_job_id': False, 'import_job_source': False}")
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_detect_custom_donation_fields_custom_field_list(self, mock_get, donation_client):
        """Test custom field detection with custom field list."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": 1,
                    "amount_in_cents": 2500,
                    "custom_field_1": "value1"
                    # custom_field_2 not present
                }
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"):
            
            custom_fields = ["custom_field_1", "custom_field_2", "custom_field_3"]
            result = donation_client.detect_custom_donation_fields(custom_fields)
            
            assert result == {
                "custom_field_1": True,
                "custom_field_2": False,
                "custom_field_3": False
            }
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_detect_custom_donation_fields_no_donations(self, mock_get, donation_client):
        """Test custom field detection with no donations available."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.donation_api.logger') as mock_logger:
            
            result = donation_client.detect_custom_donation_fields()
            
            assert result == {
                "import_job_id": False,
                "import_job_source": False
            }
            mock_logger.warning.assert_called_with("No donations found for field detection - assuming fields don't exist")
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_detect_custom_donation_fields_http_error(self, mock_get, donation_client):
        """Test custom field detection with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="HTTP 403"), \
             patch('cdflow_cli.adapters.nationbuilder.donation_api.logger') as mock_logger:
            
            result = donation_client.detect_custom_donation_fields()
            
            assert result == {
                "import_job_id": False,
                "import_job_source": False
            }
            mock_logger.warning.assert_called_with("Failed to detect custom fields: HTTP 403")
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.get')
    def test_detect_custom_donation_fields_exception(self, mock_get, donation_client):
        """Test custom field detection with exception during request."""
        mock_get.side_effect = Exception("Network error")
        
        with patch.object(donation_client, '_update_headers'), \
             patch('cdflow_cli.adapters.nationbuilder.donation_api.logger') as mock_logger:
            
            result = donation_client.detect_custom_donation_fields()
            
            assert result == {
                "import_job_id": False,
                "import_job_source": False
            }
            mock_logger.warning.assert_called_with("Error detecting custom donation fields: Network error")
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.delete')
    def test_delete_donation_success_200(self, mock_delete, donation_client):
        """Test successful donation deletion with 200 status code."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Deleted"):
            
            donation_id, success, message = donation_client.delete_donation(12345)
            
            assert donation_id == 12345
            assert success is True
            assert message == "Deleted"
            
            # Verify API call
            mock_delete.assert_called_once()
            call_args = mock_delete.call_args
            assert "/12345" in call_args[1]['url']
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.delete')
    def test_delete_donation_success_204(self, mock_delete, donation_client):
        """Test successful donation deletion with 204 status code."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="No content"):
            
            donation_id, success, message = donation_client.delete_donation(54321)
            
            assert donation_id == 54321
            assert success is True
            assert message == "No content"
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.delete')
    def test_delete_donation_failure(self, mock_delete, donation_client):
        """Test donation deletion failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Not found"):
            
            donation_id, success, message = donation_client.delete_donation(99999)
            
            assert donation_id == 99999
            assert success is False
            assert message == "Not found"
    
    @patch('cdflow_cli.adapters.nationbuilder.donation_api.requests.delete')
    def test_delete_donation_exception_handling(self, mock_delete, donation_client):
        """Test donation deletion with exception handling."""
        mock_response = Mock()
        # Make status_code access raise an exception to trigger the except block
        type(mock_response).status_code = property(lambda self: exec('raise Exception("Status code error")'))
        mock_delete.return_value = mock_response
        
        with patch.object(donation_client, '_update_headers'), \
             patch.object(donation_client, '_log_response', return_value="Logged"):
            
            donation_id, success, message = donation_client.delete_donation(12345)
            
            assert donation_id == 12345
            assert success is False
            assert "Response handling error" in message
    
    def test_all_methods_use_oauth_decorator(self, donation_client):
        """Test that all API methods use the OAuth decorator."""
        # Get all methods that should have the decorator
        api_methods = [
            'get_donationid_by_params',
            'create_donation',
            'detect_custom_donation_fields',
            'delete_donation'
        ]
        
        for method_name in api_methods:
            method = getattr(donation_client, method_name)
            # Check if method has the decorator applied
            assert hasattr(method, '__wrapped__'), f"Method {method_name} should have OAuth decorator"


if __name__ == "__main__":
    pytest.main([__file__])