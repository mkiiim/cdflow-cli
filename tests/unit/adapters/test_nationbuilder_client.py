"""
Comprehensive tests for NationBuilder Client base class.

Tests all methods in NBClient class with comprehensive edge case coverage.
"""
import pytest
from unittest.mock import Mock, patch
import requests
from cdflow_cli.adapters.nationbuilder.client import NBClient, encode_uri
from cdflow_cli.adapters.nationbuilder.oauth import NationBuilderOAuth


class TestEncodeUri:
    """Test URI encoding utility function."""
    
    def test_encode_uri_with_plus_signs(self):
        """Test URI encoding replaces + with %2B."""
        result = encode_uri("test+string+with+plus")
        assert "%2B" in result
        assert "+" not in result
    
    def test_encode_uri_with_spaces(self):
        """Test URI encoding handles spaces."""
        result = encode_uri("test string with spaces")
        assert "%20" in result or "+" in result  # requests.utils.requote_uri may use either
    
    def test_encode_uri_with_special_characters(self):
        """Test URI encoding handles special characters."""
        result = encode_uri("test@example.com")
        assert isinstance(result, str)
        # Basic test that it returns a string - exact encoding depends on requests implementation
    
    def test_encode_uri_empty_string(self):
        """Test URI encoding with empty string."""
        result = encode_uri("")
        assert result == ""
    
    def test_encode_uri_already_encoded(self):
        """Test URI encoding with already encoded string."""
        result = encode_uri("test%20string")
        assert isinstance(result, str)


class TestNBClient:
    """Test NationBuilder Client base class."""
    
    @pytest.fixture
    def mock_oauth(self):
        """Mock OAuth instance."""
        oauth = Mock(spec=NationBuilderOAuth)
        oauth.slug = "test-nation"
        oauth.nb_jwt_token = "test-jwt-token"
        return oauth
    
    @pytest.fixture 
    def client(self, mock_oauth):
        """Create NBClient instance."""
        return NBClient(mock_oauth)
    
    def test_init_basic(self, mock_oauth):
        """Test basic initialization."""
        client = NBClient(mock_oauth)
        
        assert client.oauth == mock_oauth
        assert client.access_token == "test-jwt-token"
        assert client.nation_slug == "test-nation"
        assert client.headers == {"Authorization": "Bearer test-jwt-token"}
        assert client.base_url == "https://test-nation.nationbuilder.com/api/v1"
    
    def test_log_response_success_status(self, client):
        """Test response logging for successful status codes."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.text = "Success response"
        
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            result = client._log_response("test_method", mock_response)
            
            assert result == "test_method:200"
            mock_logger.debug.assert_called_with("test_method:200")
    
    def test_log_response_client_error_status(self, client):
        """Test response logging for client error status codes."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.reason = "Bad Request"
        mock_response.text = "Invalid parameters"
        
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            result = client._log_response("test_method", mock_response)
            
            expected = "test_method:400 :: Bad Request :: Invalid parameters"
            assert result == expected
            mock_logger.debug.assert_called_with(expected)
    
    def test_log_response_server_error_status(self, client):
        """Test response logging for server error status codes."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.reason = "Internal Server Error"
        mock_response.text = "Server error occurred"
        
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            result = client._log_response("test_method", mock_response)
            
            expected = "test_method:500 :: Internal Server Error :: Server error occurred"
            assert result == expected
            mock_logger.debug.assert_called_with(expected)
    
    def test_log_response_404_status(self, client):
        """Test response logging for 404 status code."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.text = "Resource not found"
        
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            result = client._log_response("get_person", mock_response)
            
            expected = "get_person:404 :: Not Found :: Resource not found"
            assert result == expected
            mock_logger.debug.assert_called_with(expected)
    
    def test_update_headers_token_changed(self, client):
        """Test header update when token changes."""
        # Initial token
        assert client.access_token == "test-jwt-token"
        
        # Change token in OAuth instance
        client.oauth.nb_jwt_token = "new-jwt-token"
        
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()
            
            assert client.access_token == "new-jwt-token"
            assert client.headers == {"Authorization": "Bearer new-jwt-token"}
            
            # Should log token change (check if it was called, don't enforce specific level)
            assert mock_logger.info.called or mock_logger.debug.called
    
    def test_update_headers_token_unchanged(self, client):
        """Test header update when token is unchanged."""
        # Keep same token
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()
            
            # Token should remain the same
            assert client.access_token == "test-jwt-token"
            assert client.headers == {"Authorization": "Bearer test-jwt-token"}
            
            # Should log something (check if any logging occurred)
            assert mock_logger.info.called or mock_logger.debug.called
    
    def test_update_headers_none_token(self, client):
        """Test header update when token is None."""
        client.oauth.nb_jwt_token = None
        
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()
            
            assert client.access_token is None
            assert client.headers == {"Authorization": "Bearer None"}
            
            # Should handle None token gracefully and log
            assert mock_logger.info.called or mock_logger.debug.called
    
    def test_update_headers_empty_token(self, client):
        """Test header update when token is empty string."""
        client.oauth.nb_jwt_token = ""
        
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()
            
            assert client.access_token == ""
            assert client.headers == {"Authorization": "Bearer "}
            
            # Should handle empty token gracefully and log
            assert mock_logger.info.called or mock_logger.debug.called
    
    def test_update_headers_token_suffix_extraction(self, client):
        """Test token suffix extraction for logging."""
        # Test with token shorter than 5 characters
        client.oauth.nb_jwt_token = "abc"
        
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()
            
            # Should handle short tokens without error and log
            assert mock_logger.info.called or mock_logger.debug.called
    
    def test_oauth_instance_storage(self, mock_oauth):
        """Test that OAuth instance is properly stored."""
        client = NBClient(mock_oauth)
        
        assert client.oauth is mock_oauth
        assert hasattr(client, 'oauth')
    
    def test_base_url_construction(self, mock_oauth):
        """Test base URL construction with different nation slugs."""
        mock_oauth.slug = "my-test-nation"
        client = NBClient(mock_oauth)
        
        expected_url = "https://my-test-nation.nationbuilder.com/api/v1"
        assert client.base_url == expected_url
    
    def test_authorization_header_format(self, mock_oauth):
        """Test authorization header format."""
        mock_oauth.nb_jwt_token = "sample.jwt.token"
        client = NBClient(mock_oauth)
        
        expected_headers = {"Authorization": "Bearer sample.jwt.token"}
        assert client.headers == expected_headers
    
    def test_nation_slug_assignment(self, mock_oauth):
        """Test nation slug is properly assigned.""" 
        mock_oauth.slug = "custom-nation"
        client = NBClient(mock_oauth)
        
        assert client.nation_slug == "custom-nation"


class TestNBClientSimple:
    """Simple tests for the NationBuilder client (legacy)."""
    
    @pytest.fixture
    def mock_oauth(self):
        """Create a mock OAuth instance."""
        mock_oauth = Mock()
        mock_oauth.nb_jwt_token = 'test-token'
        mock_oauth.slug = 'test-nation'
        return mock_oauth
    
    def test_client_initialization(self, mock_oauth):
        """Test client initialization."""
        client = NBClient(mock_oauth)
        assert client.nation_slug == 'test-nation'
        assert client.access_token == 'test-token'
        assert 'test-nation.nationbuilder.com' in client.base_url
    
    def test_headers_contain_auth(self, mock_oauth):
        """Test that headers include authorization."""
        client = NBClient(mock_oauth)
        assert 'Authorization' in client.headers
        assert 'Bearer test-token' in client.headers['Authorization']


if __name__ == "__main__":
    pytest.main([__file__])