"""
Comprehensive tests for NationBuilder Client base class.

Tests all methods in NBClient class with comprehensive edge case coverage.
"""
import pytest
from unittest.mock import Mock, patch

from cdflow_cli.adapters.nationbuilder.client import NBClient, encode_uri
from cdflow_cli.adapters.nationbuilder.oauth import NationBuilderOAuth
from cdflow_cli.nationbuilder_auth_core.models import OAuthConfig, TokenSet
from cdflow_cli.nationbuilder_auth_core.token_client import NationBuilderTokenClient
from cdflow_cli.nationbuilder_auth_core.token_provider import NationBuilderTokenProvider
from cdflow_cli.nationbuilder_auth_core.token_state import InMemoryTokenState


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
        assert "%20" in result or "+" in result

    def test_encode_uri_with_special_characters(self):
        """Test URI encoding handles special characters."""
        result = encode_uri("test@example.com")
        assert isinstance(result, str)

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
        return NBClient(oauth=mock_oauth)

    def test_init_basic(self, mock_oauth):
        """Test basic initialization."""
        client = NBClient(oauth=mock_oauth)

        assert client.oauth == mock_oauth
        assert client.token_provider is None
        assert client.access_token == "test-jwt-token"
        assert client.nation_slug == "test-nation"
        assert client.headers == {"Authorization": "Bearer test-jwt-token"}
        assert client.base_url == "https://test-nation.nationbuilder.com/api/v1"

    def test_init_with_token_provider(self):
        """Test initialization using the new auth-core token provider."""
        state = InMemoryTokenState(now_fn=lambda: 1000)
        state.set_tokens(TokenSet(access_token="provider-token", created_at=1000, expires_in=600))
        token_provider = NationBuilderTokenProvider(
            state,
            NationBuilderTokenClient(
                OAuthConfig(
                    slug="provider-nation",
                    client_id="client-id",
                    client_secret="client-secret",
                    redirect_uri="http://127.0.0.1:8801/callback",
                ),
                session=Mock(),
            ),
        )

        client = NBClient(token_provider=token_provider)

        assert client.oauth is None
        assert client.token_provider is token_provider
        assert client.access_token == "provider-token"
        assert client.nation_slug == "provider-nation"
        assert client.headers == {"Authorization": "Bearer provider-token"}

    def test_init_requires_auth_source(self):
        """Test that either oauth or token provider is required."""
        with pytest.raises(ValueError, match="either oauth or token_provider"):
            NBClient()

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

    def test_update_headers_token_changed(self, client):
        """Test header update when token changes."""
        client.oauth.nb_jwt_token = "new-jwt-token"

        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()

            assert client.access_token == "new-jwt-token"
            assert client.headers == {"Authorization": "Bearer new-jwt-token"}
            mock_logger.debug.assert_called_with("NationBuilder client auth headers refreshed")

    def test_update_headers_token_unchanged(self, client):
        """Test header update when token is unchanged."""
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()

            assert client.access_token == "test-jwt-token"
            assert client.headers == {"Authorization": "Bearer test-jwt-token"}
            mock_logger.debug.assert_called_with("NationBuilder client auth headers refreshed")

    def test_update_headers_none_token(self, client):
        """Test header update when token is None."""
        client.oauth.nb_jwt_token = None

        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()

            assert client.access_token is None
            assert client.headers == {}
            mock_logger.debug.assert_called_with("NationBuilder client auth headers refreshed")

    def test_update_headers_empty_token(self, client):
        """Test header update when token is empty string."""
        client.oauth.nb_jwt_token = ""

        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()

            assert client.access_token == ""
            assert client.headers == {}
            mock_logger.debug.assert_called_with("NationBuilder client auth headers refreshed")

    def test_oauth_instance_storage(self, mock_oauth):
        """Test that OAuth instance is properly stored."""
        client = NBClient(oauth=mock_oauth)

        assert client.oauth is mock_oauth
        assert hasattr(client, 'oauth')

    def test_base_url_construction(self, mock_oauth):
        """Test base URL construction with different nation slugs."""
        mock_oauth.slug = "my-test-nation"
        client = NBClient(oauth=mock_oauth)

        expected_url = "https://my-test-nation.nationbuilder.com/api/v1"
        assert client.base_url == expected_url

    def test_authorization_header_format(self, mock_oauth):
        """Test authorization header format."""
        mock_oauth.nb_jwt_token = "sample.jwt.token"
        client = NBClient(oauth=mock_oauth)

        expected_headers = {"Authorization": "Bearer sample.jwt.token"}
        assert client.headers == expected_headers

    def test_nation_slug_assignment(self, mock_oauth):
        """Test nation slug is properly assigned."""
        mock_oauth.slug = "custom-nation"
        client = NBClient(oauth=mock_oauth)

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
        client = NBClient(oauth=mock_oauth)
        assert client.nation_slug == 'test-nation'
        assert client.access_token == 'test-token'
        assert 'test-nation.nationbuilder.com' in client.base_url

    def test_headers_contain_auth(self, mock_oauth):
        """Test that headers include authorization."""
        client = NBClient(oauth=mock_oauth)
        assert 'Authorization' in client.headers
        assert 'Bearer test-token' in client.headers['Authorization']


if __name__ == "__main__":
    pytest.main([__file__])
