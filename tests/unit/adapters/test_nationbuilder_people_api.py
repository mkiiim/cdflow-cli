"""
Comprehensive tests for NationBuilder People API client.

Tests all methods in NBPeople class with comprehensive edge case coverage.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
import json
from cdflow_cli.adapters.nationbuilder.people_api import NBPeople
from cdflow_cli.adapters.nationbuilder.oauth import NationBuilderOAuth


@patch('cdflow_cli.adapters.nationbuilder.oauth.NationBuilderOAuth.ensure_valid_nb_jwt', lambda x: x)
class TestNBPeople:
    """Test NationBuilder People API client."""
    
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
    def people_client(self, mock_oauth):
        """Create NBPeople client with mocked OAuth."""
        return NBPeople(mock_oauth)
    
    def test_init_sets_base_url(self, people_client):
        """Test that initialization sets correct base URL."""
        assert "people" in people_client.base_url
        assert people_client.base_url.endswith("/people")
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_email_success(self, mock_get, people_client):
        """Test successful person lookup by email."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "person": {"id": 12345}
        }
        mock_get.return_value = mock_response
        
        # Mock the decorator and logging
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_email("test@example.com")
            
            assert person_id == 12345
            assert success is True
            assert message == "Success"
            
            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "match?email=" in call_args[1]['url']
            assert "test" in call_args[1]['url']  # Email is in URL
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_email_not_found_empty_response(self, mock_get, people_client):
        """Test person not found by email - empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Empty response, no person key
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_email("notfound@example.com")
            
            assert person_id is None
            assert success is False
            assert message == "Person not found"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_email_not_found_person_no_id(self, mock_get, people_client):
        """Test person not found by email - person object without ID."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"person": {}}  # Person exists but no ID
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_email("noid@example.com")
            
            assert person_id is None
            assert success is False
            assert message == "Person not found"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_email_not_found_none_data(self, mock_get, people_client):
        """Test person not found by email - None data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = None  # None response
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_email("none@example.com")
            
            assert person_id is None
            assert success is False
            assert message == "Person not found"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_email_person_with_none_id(self, mock_get, people_client):
        """Test person with None ID."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"person": {"id": None}}  # Person with None ID
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_email("noneid@example.com")
            
            assert person_id is None
            assert success is False
            assert message == "Person not found"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_email_http_error(self, mock_get, people_client):
        """Test HTTP error response."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="HTTP 404"):
            
            person_id, success, message = people_client.get_personid_by_email("test@example.com")
            
            assert person_id is None
            assert success is False
            assert message == "HTTP 404"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_email_json_error(self, mock_get, people_client):
        """Test JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_email("test@example.com")
            
            assert person_id is None
            assert success is False
            assert "JSON parsing error" in message
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_email_key_error(self, mock_get, people_client):
        """Test KeyError in response parsing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = KeyError("person")
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_email("test@example.com")
            
            assert person_id is None
            assert success is False
            assert "JSON parsing error" in message
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_phone_http_error(self, mock_get, people_client):
        """Test person lookup by phone with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="HTTP 500"):
            
            person_id, success, message = people_client.get_personid_by_phone("555-123-4567")
            
            assert person_id is None
            assert success is False
            assert message == "HTTP 500"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_phone_json_error(self, mock_get, people_client):
        """Test person lookup by phone with JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_phone("555-123-4567")
            
            assert person_id is None
            assert success is False
            assert "JSON parsing error" in message

    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_phone_success(self, mock_get, people_client):
        """Test successful person lookup by phone."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "person": {"id": 54321}
        }
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, success, message = people_client.get_personid_by_phone("555-123-4567")
            
            assert person_id == 54321
            assert success is True
            assert message == "Success"
            
            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "match?phone=555-123-4567" in call_args[1]['url']
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_persons_by_params_success(self, mock_get, people_client):
        """Test successful person search by parameters."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"id": 1, "first_name": "John", "last_name": "Doe"},
                {"id": 2, "first_name": "Jane", "last_name": "Smith"}
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            params = {"first_name": "John", "last_name": "Doe"}
            results, success, message = people_client.get_persons_by_params(params, "id")
            
            assert len(results) == 2
            assert success is True
            assert message == "Success"
            
            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "search?" in call_args[1]['url']
            assert "first_name=John" in call_args[1]['url']
            assert "last_name=Doe" in call_args[1]['url']
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_persons_by_params_http_error(self, mock_get, people_client):
        """Test person search with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="HTTP 403"):
            
            params = {"first_name": "John"}
            results, success, message = people_client.get_persons_by_params(params, "id")
            
            assert results is None
            assert success is False
            assert message == "HTTP 403"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_persons_by_params_json_error(self, mock_get, people_client):
        """Test person search with JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = KeyError("results")
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            params = {"first_name": "John"}
            results, success, message = people_client.get_persons_by_params(params, "id")
            
            assert results is None
            assert success is False
            assert "JSON parsing error" in message

    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_persons_by_params_no_results(self, mock_get, people_client):
        """Test person search with no results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": []
        }
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="No results"):
            
            params = {"email": "notfound@example.com"}
            results, success, message = people_client.get_persons_by_params(params, "id")
            
            assert results == []
            assert success is True
            assert message == "No results"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_extid_success_single_result(self, mock_get, people_client):
        """Test successful external ID lookup with single result."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"id": 99999, "email": "found@example.com"}]
        }
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.people_api.logger') as mock_logger:
            
            person_id, email, success, message = people_client.get_personid_by_extid("EXT123")
            
            assert person_id == 99999
            assert email == "found@example.com"
            assert success is True
            assert "99999" in message
            mock_logger.debug.assert_called()
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_extid_no_results(self, mock_get, people_client):
        """Test external ID lookup with no results."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": []
        }
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.people_api.logger') as mock_logger:
            
            person_id, email, success, message = people_client.get_personid_by_extid("NOTFOUND")
            
            assert person_id is None
            assert email is None
            assert success is False
            assert "No records found" in message
            mock_logger.debug.assert_called()
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_extid_http_error(self, mock_get, people_client):
        """Test external ID lookup with HTTP error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="HTTP 401"), \
             patch('cdflow_cli.adapters.nationbuilder.people_api.logger') as mock_logger:
            
            person_id, email, success, message = people_client.get_personid_by_extid("EXT123")
            
            assert person_id is None
            assert email is None
            assert success is False
            assert message == "HTTP 401"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_extid_json_error(self, mock_get, people_client):
        """Test external ID lookup with JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_id, email, success, message = people_client.get_personid_by_extid("EXT123")
            
            assert person_id is None
            assert email is None
            assert success is False
            assert "JSON parsing error" in message

    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_personid_by_extid_multiple_results(self, mock_get, people_client):
        """Test external ID lookup with multiple results (error)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {"id": 1, "email": "one@example.com"},
                {"id": 2, "email": "two@example.com"}
            ]
        }
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"), \
             patch('cdflow_cli.adapters.nationbuilder.people_api.logger') as mock_logger:
            
            person_id, email, success, message = people_client.get_personid_by_extid("DUPLICATE")
            
            assert person_id is None
            assert email is None
            assert success is False
            assert "Multiple records found" in message
            mock_logger.debug.assert_called()
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_person_by_id_success(self, mock_get, people_client):
        """Test successful person retrieval by ID."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "person": {
                "first_name": "John",
                "last_name": "Doe", 
                "email": "john.doe@example.com"
            }
        }
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            first_name, last_name, email, success, message = people_client.get_person_by_id(12345)
            
            assert first_name == "John"
            assert last_name == "Doe"
            assert email == "john.doe@example.com"
            assert success is True
            assert message == "Success"
            
            # Verify API call
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/12345" in call_args[1]['url']
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_person_by_id_json_error(self, mock_get, people_client):
        """Test person retrieval by ID with JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = KeyError("person")
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            first_name, last_name, email, success, message = people_client.get_person_by_id(12345)
            
            assert first_name is None
            assert last_name is None
            assert email is None
            assert success is False
            assert "JSON parsing error" in message

    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.get')
    def test_get_person_by_id_not_found(self, mock_get, people_client):
        """Test person not found by ID."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Not found"):
            
            first_name, last_name, email, success, message = people_client.get_person_by_id(99999)
            
            assert first_name is None
            assert last_name is None
            assert email is None
            assert success is False
            assert message == "Not found"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.post')
    def test_create_person_success(self, mock_post, people_client):
        """Test successful person creation."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "person": {"id": 55555}
        }
        mock_post.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Created"):
            
            person_data = {
                "first_name": "New",
                "last_name": "Person",
                "email": "new@example.com"
            }
            
            person_id, success, message = people_client.create_person(person_data)
            
            assert person_id == 55555
            assert success is True
            assert message == "Created"
            
            # Verify API call
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[1]['json'] == {"person": person_data}
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.post')
    def test_create_person_success_200(self, mock_post, people_client):
        """Test successful person creation with 200 status code."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "person": {"id": 66666}
        }
        mock_post.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_data = {"email": "test@example.com"}
            person_id, success, message = people_client.create_person(person_data)
            
            assert person_id == 66666
            assert success is True
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.post')
    def test_create_person_missing_id_in_response(self, mock_post, people_client):
        """Test person creation with missing ID in response."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "person": {}  # Missing ID
        }
        mock_post.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Created"):
            
            person_data = {"email": "test@example.com"}
            person_id, success, message = people_client.create_person(person_data)
            
            assert person_id is None
            assert success is False
            assert message == "Missing person ID in response"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.post')
    def test_create_person_json_error(self, mock_post, people_client):
        """Test person creation with JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Created"):
            
            person_data = {"email": "test@example.com"}
            person_id, success, message = people_client.create_person(person_data)
            
            assert person_id is None
            assert success is False
            assert "JSON parsing error" in message

    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.post')
    def test_create_person_failure(self, mock_post, people_client):
        """Test person creation failure."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_post.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Bad request"):
            
            person_data = {"invalid": "data"}
            person_id, success, message = people_client.create_person(person_data)
            
            assert person_id is None
            assert success is False
            assert message == "Bad request"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.put')
    def test_update_person_success(self, mock_put, people_client):
        """Test successful person update."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "person": {"id": 12345}
        }
        mock_put.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Updated"):
            
            person_data = {"first_name": "Updated"}
            person_id, success, message = people_client.update_person(12345, person_data)
            
            assert person_id == 12345
            assert success is True
            assert message == "Updated"
            
            # Verify API call
            mock_put.assert_called_once()
            call_args = mock_put.call_args
            assert "/12345" in call_args[1]['url']
            assert call_args[1]['json'] == {"person": person_data}
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.put')
    def test_update_person_success_201(self, mock_put, people_client):
        """Test successful person update with 201 status code."""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "person": {"id": 12345}
        }
        mock_put.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Updated"):
            
            person_data = {"last_name": "NewName"}
            person_id, success, message = people_client.update_person(12345, person_data)
            
            assert person_id == 12345
            assert success is True
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.put')
    def test_update_person_failure(self, mock_put, people_client):
        """Test person update failure."""
        mock_response = Mock()
        mock_response.status_code = 422
        mock_put.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Unprocessable Entity"):
            
            person_data = {"invalid": "data"}
            person_id, success, message = people_client.update_person(12345, person_data)
            
            assert person_id is None
            assert success is False
            assert message == "Unprocessable Entity"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.put')
    def test_update_person_json_error(self, mock_put, people_client):
        """Test person update with JSON parsing error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = KeyError("person")
        mock_put.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Success"):
            
            person_data = {"first_name": "Updated"}
            person_id, success, message = people_client.update_person(12345, person_data)
            
            assert person_id is None
            assert success is False
            assert "JSON parsing error" in message

    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.put')
    def test_update_person_missing_id_in_response(self, mock_put, people_client):
        """Test person update with missing ID in response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "person": {}  # Missing ID
        }
        mock_put.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Updated"):
            
            person_data = {"email": "new@example.com"}
            person_id, success, message = people_client.update_person(12345, person_data)
            
            assert person_id is None
            assert success is False
            assert message == "Missing person ID in response"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.delete')
    def test_delete_person_success_200(self, mock_delete, people_client):
        """Test successful person deletion with 200 status code."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_delete.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Deleted"):
            
            success, message = people_client.delete_person(12345)
            
            assert success is True
            assert message == "Deleted"
            
            # Verify API call
            mock_delete.assert_called_once()
            call_args = mock_delete.call_args
            assert "/12345" in call_args[1]['url']
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.delete')
    def test_delete_person_success_204(self, mock_delete, people_client):
        """Test successful person deletion with 204 status code."""
        mock_response = Mock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="No content"):
            
            success, message = people_client.delete_person(12345)
            
            assert success is True
            assert message == "No content"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.delete')
    def test_delete_person_failure(self, mock_delete, people_client):
        """Test person deletion failure."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_delete.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Not found"):
            
            success, message = people_client.delete_person(99999)
            
            assert success is False
            assert message == "Not found"
    
    @patch('cdflow_cli.adapters.nationbuilder.people_api.requests.delete')
    def test_delete_person_exception_handling(self, mock_delete, people_client):
        """Test person deletion with exception handling."""
        mock_response = Mock()
        # Make status_code access raise an exception to trigger the except block
        type(mock_response).status_code = property(lambda self: exec('raise Exception("Status code error")'))
        mock_delete.return_value = mock_response
        
        with patch.object(people_client, '_update_headers'), \
             patch.object(people_client, '_log_response', return_value="Logged"):
            
            success, message = people_client.delete_person(12345)
            
            assert success is False
            assert "Response handling error" in message
    
    def test_all_methods_use_oauth_decorator(self, people_client):
        """Test that all API methods use the OAuth decorator."""
        # Get all methods that should have the decorator
        api_methods = [
            'get_personid_by_email',
            'get_personid_by_phone', 
            'get_persons_by_params',
            'get_personid_by_extid',
            'get_person_by_id',
            'create_person',
            'update_person',
            'delete_person'
        ]
        
        for method_name in api_methods:
            method = getattr(people_client, method_name)
            # Check if method has the decorator applied
            assert hasattr(method, '__wrapped__'), f"Method {method_name} should have OAuth decorator"


if __name__ == "__main__":
    pytest.main([__file__])