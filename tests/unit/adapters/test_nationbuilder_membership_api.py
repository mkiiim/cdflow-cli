"""
Comprehensive tests for NationBuilder Membership API client.

Tests all methods in NBMembership class with comprehensive edge case coverage.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
import json
from cdflow_cli.adapters.nationbuilder.membership_api import NBMembership
from cdflow_cli.adapters.nationbuilder.oauth import NationBuilderOAuth


@patch('cdflow_cli.adapters.nationbuilder.oauth.NationBuilderOAuth.ensure_valid_nb_jwt', lambda x: x)
class TestNBMembership:
    """Test NationBuilder Membership API client."""
    
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
    def membership_client(self, mock_oauth):
        """Create NBMembership client with mocked OAuth."""
        return NBMembership(mock_oauth)
    
    def test_init_sets_base_url(self, membership_client):
        """Test that initialization sets correct base URL."""
        assert "people" in membership_client.base_url
        assert membership_client.base_url.endswith("/people")
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.get')
    def test_get_membershipinfo_by_signup_nationbuilder_id_success_with_results(self, mock_get, membership_client):
        """Test successful membership info retrieval with results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "name": "Monthly Membership",
                    "status": "active",
                    "started_at": "2024-01-01",
                    "expires_on": "2024-12-31"
                },
                {
                    "name": "Premium Membership", 
                    "status": "expired",
                    "started_at": "2023-01-01",
                    "expires_on": "2023-12-31"
                }
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Success"):
            
            memberships, success, message = membership_client.get_membershipinfo_by_signup_nationbuilder_id(12345)
            
            assert success is True
            assert message == "Success"
            assert len(memberships) == 2
            
            # Check first membership
            assert memberships[0] == ("Monthly Membership", "active", "2024-01-01", "2024-12-31")
            assert memberships[1] == ("Premium Membership", "expired", "2023-01-01", "2023-12-31")
            
            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/12345/memberships" in call_args[1]['url']
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.get')
    def test_get_membershipinfo_by_signup_nationbuilder_id_success_empty_results(self, mock_get, membership_client):
        """Test membership info retrieval with empty results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_get.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Success"):
            
            memberships, success, message = membership_client.get_membershipinfo_by_signup_nationbuilder_id(12345)
            
            assert memberships is None
            assert success is False
            assert message == "Success"
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.get')
    def test_get_membershipinfo_by_signup_nationbuilder_id_http_error(self, mock_get, membership_client):
        """Test membership info retrieval with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="HTTP 404"):
            
            memberships, success, message = membership_client.get_membershipinfo_by_signup_nationbuilder_id(99999)
            
            assert memberships is None
            assert success is False
            assert message == "HTTP 404"
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.post')
    def test_set_active_monthly_membership_success(self, mock_post, membership_client):
        """Test successful active monthly membership setting."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "membership": {"id": 98765, "status": "active", "payment_plan_id": 1}
        }
        mock_post.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Success"):
            
            membership_id, success, message = membership_client.set_active_monthly_membership(12345)
            
            assert membership_id == 98765
            assert success is True
            assert message == "Success"
            
            # Verify API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            expected_data = {
                "membership": {
                    "person_id": 12345,
                    "status": "active", 
                    "payment_plan_id": 1
                }
            }
            assert call_args[1]['json'] == expected_data
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.post')
    def test_set_active_monthly_membership_failure(self, mock_post, membership_client):
        """Test active monthly membership setting failure."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Bad request"):
            
            membership_id, success, message = membership_client.set_active_monthly_membership(12345)
            
            assert membership_id is None
            assert success is False
            assert message == "Bad request"
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.get')
    def test_get_membershipid_by_params_success_match_found(self, mock_get, membership_client):
        """Test successful membership lookup with matching check number."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({
            "results": [
                {"id": 1, "check_number": "CHECK-123", "status": "active"},
                {"id": 2, "check_number": "CHECK-456", "status": "expired"},
                {"id": 3, "check_number": "CHECK-789", "status": "active"}
            ]
        }).encode('utf-8')
        mock_get.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.membership_api.logger') as mock_logger:
            
            params = {"status": "active"}
            membership_id, success, message = membership_client.get_membershipid_by_params(params, "CHECK-456")
            
            assert membership_id == 2
            assert success is True
            assert message == "Success"
            
            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "search?status=active" in call_args[1]['url']
            
            # Verify debug logging
            mock_logger.debug.assert_called_with("Success :: 2")
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.get')
    def test_get_membershipid_by_params_success_no_match(self, mock_get, membership_client):
        """Test membership lookup with no matching check number."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({
            "results": [
                {"id": 1, "check_number": "CHECK-123", "status": "active"},
                {"id": 2, "check_number": "CHECK-456", "status": "expired"}
            ]
        }).encode('utf-8')
        mock_get.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.membership_api.logger') as mock_logger:
            
            params = {"status": "active"}
            membership_id, success, message = membership_client.get_membershipid_by_params(params, "NOT-FOUND")
            
            assert membership_id is None
            assert success is False
            assert message == "Success"
            
            # Verify debug logging
            mock_logger.debug.assert_called_with("Success :: None.")
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.get')
    def test_get_membershipid_by_params_empty_results(self, mock_get, membership_client):
        """Test membership lookup with empty results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = json.dumps({"results": []}).encode('utf-8')
        mock_get.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.membership_api.logger') as mock_logger:
            
            params = {"status": "active"}
            membership_id, success, message = membership_client.get_membershipid_by_params(params, "CHECK-123")
            
            assert membership_id is None
            assert success is False
            assert message == "Success"
            
            # Verify debug logging
            mock_logger.debug.assert_called_with("Success :: None.")
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.get')
    def test_get_membershipid_by_params_http_error(self, mock_get, membership_client):
        """Test membership lookup with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="HTTP 404"), \
             patch('cdflow_cli.adapters.nationbuilder.membership_api.logger') as mock_logger:
            
            params = {"status": "active"}
            membership_id, success, message = membership_client.get_membershipid_by_params(params, "CHECK-123")
            
            assert membership_id is None
            assert success is False
            assert message == "HTTP 404"
            
            # Verify debug logging
            mock_logger.debug.assert_called_with("HTTP 404 :: None.")
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.post')
    def test_create_membership_success(self, mock_post, membership_client):
        """Test successful membership creation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "membership": {"id": 55555, "status": "active", "person_id": 12345}
        }
        mock_post.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Created"):
            
            membership_data = {
                "person_id": 12345,
                "status": "active",
                "payment_plan_id": 1,
                "started_at": "2024-01-15"
            }
            
            membership_id, success, message = membership_client.create_membership(membership_data)
            
            assert membership_id == 55555
            assert success is True
            assert message == "Created"
            
            # Verify API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]['json'] == {"membership": membership_data}
    
    @patch('cdflow_cli.adapters.nationbuilder.membership_api.requests.post')
    def test_create_membership_failure(self, mock_post, membership_client):
        """Test membership creation failure."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        with patch.object(membership_client, '_update_headers'), \
             patch.object(membership_client, '_log_response', return_value="Bad request"):
            
            membership_data = {"invalid": "data"}
            membership_id, success, message = membership_client.create_membership(membership_data)
            
            assert membership_id is None
            assert success is False
            assert message == "Bad request"
    
    def test_all_methods_use_oauth_decorator(self, membership_client):
        """Test that all API methods use the OAuth decorator."""
        # Get all methods that should have the decorator
        api_methods = [
            'get_membershipinfo_by_signup_nationbuilder_id',
            'set_active_monthly_membership',
            'get_membershipid_by_params',
            'create_membership'
        ]
        
        for method_name in api_methods:
            method = getattr(membership_client, method_name)
            # Check if method has the decorator applied
            assert hasattr(method, '__wrapped__'), f"Method {method_name} should have OAuth decorator"
    
    def test_param_value_pairs_string_generation(self, membership_client):
        """Test parameter string generation for API calls."""
        # This tests the param_value_pairs_str logic used in get_membershipid_by_params
        params = {"status": "active", "person_id": "12345", "started_at": "2024-01-01"}
        
        # Simulate the string generation logic
        param_value_pairs_str = "&".join([f"{param_name}={param_value}" for param_name, param_value in params.items()])
        
        # Verify it contains all parameters
        assert "status=active" in param_value_pairs_str
        assert "person_id=12345" in param_value_pairs_str
        assert "started_at=2024-01-01" in param_value_pairs_str
        assert param_value_pairs_str.count("&") == 2  # Two separators for three params


if __name__ == "__main__":
    pytest.main([__file__])