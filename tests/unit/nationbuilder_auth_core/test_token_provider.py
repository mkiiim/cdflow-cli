from unittest.mock import Mock

from cdflow_cli.nationbuilder_auth_core.models import OAuthConfig, TokenSet
from cdflow_cli.nationbuilder_auth_core.token_client import NationBuilderTokenClient
from cdflow_cli.nationbuilder_auth_core.token_provider import NationBuilderTokenProvider
from cdflow_cli.nationbuilder_auth_core.token_state import InMemoryTokenState
from cdflow_cli.nationbuilder_auth_core.session import NationBuilderAuthorizedSession


class TestNationBuilderTokenProvider:
    def build_client(self):
        return NationBuilderTokenClient(
            OAuthConfig(
                slug="test-nation",
                client_id="client-id",
                client_secret="client-secret",
                redirect_uri="http://127.0.0.1:8801/callback",
            ),
            session=Mock(),
        )

    def test_returns_none_when_no_tokens_exist(self):
        provider = NationBuilderTokenProvider(InMemoryTokenState(now_fn=lambda: 1000), self.build_client())

        assert provider.get_access_token() is None

    def test_returns_existing_valid_token_without_refresh(self):
        state = InMemoryTokenState(now_fn=lambda: 1000)
        state.set_tokens(TokenSet(access_token="access", refresh_token="refresh", created_at=1000, expires_in=600))
        client = self.build_client()
        client.refresh_token = Mock()
        provider = NationBuilderTokenProvider(state, client)

        assert provider.get_access_token() == "access"
        client.refresh_token.assert_not_called()

    def test_refreshes_expiring_token(self):
        state = InMemoryTokenState(now_fn=lambda: 1055)
        state.set_tokens(TokenSet(access_token="old-access", refresh_token="refresh", created_at=1000, expires_in=100))
        client = self.build_client()
        client.refresh_token = Mock(return_value=TokenSet(access_token="new-access", refresh_token="new-refresh", created_at=1055, expires_in=300))
        provider = NationBuilderTokenProvider(state, client)

        assert provider.get_access_token() == "new-access"
        assert state.access_token == "new-access"
        assert state.refresh_token == "new-refresh"

    def test_returns_none_for_expired_token_without_refresh_token(self):
        state = InMemoryTokenState(now_fn=lambda: 1200)
        state.set_tokens(TokenSet(access_token="old-access", created_at=1000, expires_in=100))
        provider = NationBuilderTokenProvider(state, self.build_client())

        assert provider.get_access_token() is None

    def test_authorized_session_builds_headers(self):
        state = InMemoryTokenState(now_fn=lambda: 1000)
        state.set_tokens(TokenSet(access_token="access", refresh_token="refresh", created_at=1000, expires_in=600))
        provider = NationBuilderTokenProvider(state, self.build_client())
        session = NationBuilderAuthorizedSession(provider)

        assert session.get_auth_headers() == {"Authorization": "Bearer access"}
