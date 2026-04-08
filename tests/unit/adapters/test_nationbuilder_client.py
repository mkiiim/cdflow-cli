"""
Comprehensive tests for NationBuilder Client base class.

Tests all methods in NBClient class with comprehensive edge case coverage.
"""
import pytest
from unittest.mock import Mock, patch

from cdflow_cli.adapters.nationbuilder.client import NBClient, encode_uri
from cdflow_cli.nationbuilder_auth_core.models import OAuthConfig, TokenSet
from cdflow_cli.nationbuilder_auth_core.token_client import NationBuilderTokenClient
from cdflow_cli.nationbuilder_auth_core.token_provider import NationBuilderTokenProvider
from cdflow_cli.nationbuilder_auth_core.token_state import InMemoryTokenState


def make_token_provider(access_token="provider-token", slug="provider-nation"):
    state = InMemoryTokenState(now_fn=lambda: 1000)
    state.set_tokens(TokenSet(access_token=access_token, created_at=1000, expires_in=600))
    return NationBuilderTokenProvider(
        state,
        NationBuilderTokenClient(
            OAuthConfig(
                slug=slug,
                client_id="client-id",
                client_secret="client-secret",
                redirect_uri="http://127.0.0.1:8801/callback",
            ),
            session=Mock(),
        ),
    )


class TestEncodeUri:
    def test_encode_uri_with_plus_signs(self):
        result = encode_uri("test+string+with+plus")
        assert "%2B" in result
        assert "+" not in result

    def test_encode_uri_with_spaces(self):
        result = encode_uri("test string with spaces")
        assert "%20" in result or "+" in result

    def test_encode_uri_with_special_characters(self):
        result = encode_uri("test@example.com")
        assert isinstance(result, str)

    def test_encode_uri_empty_string(self):
        result = encode_uri("")
        assert result == ""

    def test_encode_uri_already_encoded(self):
        result = encode_uri("test%20string")
        assert isinstance(result, str)


class TestNBClient:
    @pytest.fixture
    def token_provider(self):
        return make_token_provider()

    @pytest.fixture
    def client(self, token_provider):
        return NBClient(token_provider=token_provider)

    def test_init_basic(self, token_provider):
        client = NBClient(token_provider=token_provider)
        assert client.token_provider is token_provider
        assert client.access_token == "provider-token"
        assert client.nation_slug == "provider-nation"
        assert client.headers == {"Authorization": "Bearer provider-token"}
        assert client.base_url == "https://provider-nation.nationbuilder.com/api/v1"

    def test_init_requires_token_provider(self):
        with pytest.raises(ValueError, match="requires token_provider"):
            NBClient(None)

    def test_log_response_success_status(self, client):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.reason = "OK"
        mock_response.text = "Success response"
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            result = client._log_response("test_method", mock_response)
            assert result == "test_method:200"
            mock_logger.debug.assert_called_with("test_method:200")

    def test_log_response_client_error_status(self, client):
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
        client.token_provider.token_state.set_tokens(TokenSet(access_token="new-token", created_at=1000, expires_in=600))
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()
            assert client.access_token == "new-token"
            assert client.headers == {"Authorization": "Bearer new-token"}
            mock_logger.debug.assert_called_with("NationBuilder client auth headers refreshed")

    def test_update_headers_none_token(self, client):
        client.token_provider.token_state.clear()
        with patch('cdflow_cli.adapters.nationbuilder.client.logger') as mock_logger:
            client._update_headers()
            assert client.access_token is None
            assert client.headers == {}
            mock_logger.debug.assert_called_with("NationBuilder client auth headers refreshed")

    def test_nation_slug_assignment(self, token_provider):
        client = NBClient(token_provider=token_provider)
        assert client.nation_slug == "provider-nation"


class TestNBClientSimple:
    def test_client_initialization(self):
        client = NBClient(token_provider=make_token_provider(access_token='test-token', slug='test-nation'))
        assert client.nation_slug == 'test-nation'
        assert client.access_token == 'test-token'
        assert 'test-nation.nationbuilder.com' in client.base_url

    def test_headers_contain_auth(self):
        client = NBClient(token_provider=make_token_provider(access_token='test-token', slug='test-nation'))
        assert 'Authorization' in client.headers
        assert 'Bearer test-token' in client.headers['Authorization']


if __name__ == "__main__":
    pytest.main([__file__])
