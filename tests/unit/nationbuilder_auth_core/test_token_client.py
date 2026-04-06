from unittest.mock import Mock

import pytest
import requests

from cdflow_cli.nationbuilder_auth_core import (
    AuthConfigurationError,
    NationBuilderTokenClient,
    OAuthConfig,
    TokenExchangeError,
    TokenRefreshError,
)


class TestNationBuilderTokenClient:
    def build_config(self):
        return OAuthConfig(
            slug="test-nation",
            client_id="client-id",
            client_secret="client-secret",
            redirect_uri="http://127.0.0.1:8801/callback",
        )

    def test_exchange_code_success(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "access_token": "access-123",
            "refresh_token": "refresh-123",
            "expires_in": 3600,
            "created_at": 1234567890,
        }
        response.raise_for_status.return_value = None
        session.post.return_value = response

        client = NationBuilderTokenClient(self.build_config(), session=session)
        token_set = client.exchange_code("auth-code")

        assert token_set.access_token == "access-123"
        assert token_set.refresh_token == "refresh-123"
        assert token_set.expires_in == 3600
        assert token_set.created_at == 1234567890
        session.post.assert_called_once()

    def test_refresh_token_success(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 1800,
            "created_at": 1234567999,
        }
        response.raise_for_status.return_value = None
        session.post.return_value = response

        client = NationBuilderTokenClient(self.build_config(), session=session)
        token_set = client.refresh_token("refresh-123")

        assert token_set.access_token == "new-access"
        assert token_set.refresh_token == "new-refresh"
        assert token_set.expires_in == 1800
        assert token_set.created_at == 1234567999

    def test_exchange_code_raises_on_timeout(self):
        session = Mock()
        session.post.side_effect = requests.exceptions.Timeout("timeout")
        client = NationBuilderTokenClient(self.build_config(), session=session)

        with pytest.raises(TokenExchangeError, match="timed out"):
            client.exchange_code("auth-code")

    def test_refresh_token_raises_on_request_failure(self):
        session = Mock()
        response = Mock()
        response.text = "bad refresh"
        error = requests.exceptions.HTTPError("boom")
        error.response = response
        session.post.side_effect = error
        client = NationBuilderTokenClient(self.build_config(), session=session)

        with pytest.raises(TokenRefreshError, match="bad refresh"):
            client.refresh_token("refresh-123")

    def test_exchange_code_uses_explicit_timeout(self):
        session = Mock()
        response = Mock()
        response.json.return_value = {"access_token": "access-123"}
        response.raise_for_status.return_value = None
        session.post.return_value = response

        client = NationBuilderTokenClient(self.build_config(), timeout=(1.0, 2.0), session=session)
        client.exchange_code("auth-code")

        assert session.post.call_args.kwargs["timeout"] == (1.0, 2.0)

    def test_missing_required_oauth_config_raises(self):
        with pytest.raises(AuthConfigurationError, match="client_id"):
            NationBuilderTokenClient(
                OAuthConfig(
                    slug="test-nation",
                    client_id="",
                    client_secret="client-secret",
                    redirect_uri="http://127.0.0.1:8801/callback",
                )
            )
