"""
Focused tests for NationBuilder Signups API client.

This suite validates the token-provider-only constructor contract and a
representative request path for the v2 signups adapter.
"""
import pytest
from unittest.mock import Mock, patch

from cdflow_cli.adapters.nationbuilder.signups_api import NBSignups
from cdflow_cli.nationbuilder_auth_core.models import OAuthConfig, TokenSet
from cdflow_cli.nationbuilder_auth_core.token_client import NationBuilderTokenClient
from cdflow_cli.nationbuilder_auth_core.token_provider import NationBuilderTokenProvider
from cdflow_cli.nationbuilder_auth_core.token_state import InMemoryTokenState


class TestNBSignups:
    @pytest.fixture
    def token_provider(self):
        state = InMemoryTokenState(now_fn=lambda: 1000)
        state.set_tokens(TokenSet(access_token="test-jwt-token", created_at=1000, expires_in=3600))
        return NationBuilderTokenProvider(
            state,
            NationBuilderTokenClient(
                OAuthConfig(
                    slug="test-nation",
                    client_id="client-id",
                    client_secret="client-secret",
                    redirect_uri="http://127.0.0.1:8801/callback",
                ),
                session=Mock(),
            ),
        )

    @pytest.fixture
    def signups_client(self, token_provider):
        return NBSignups(token_provider=token_provider)

    def test_init_sets_signups_base_url(self, signups_client):
        assert signups_client.base_url.endswith("/signups")
        assert signups_client.nation_slug == "test-nation"
        assert signups_client.headers == {"Authorization": "Bearer test-jwt-token"}

    @patch('cdflow_cli.adapters.nationbuilder.signups_api.requests.get')
    def test_get_personid_by_email_success(self, mock_get, signups_client):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [{"id": "12345"}]}
        mock_get.return_value = mock_response

        with patch.object(signups_client, '_update_headers'), \
             patch.object(signups_client, '_log_response', return_value="Success"):
            person_id, success, message = signups_client.get_personid_by_email("test@example.com")

        assert person_id == "12345"
        assert success is True
        assert message == "Success"
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert "filter[with_email_address]=eq:test@example.com" in call_args.kwargs['url']

    def test_get_personid_by_phone_reports_not_supported(self, signups_client):
        person_id, success, message = signups_client.get_personid_by_phone("555-123-4567")
        assert person_id is None
        assert success is False
        assert "No phone number filter available" in message
