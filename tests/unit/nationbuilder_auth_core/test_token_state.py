from cdflow_cli.nationbuilder_auth_core.models import TokenSet
from cdflow_cli.nationbuilder_auth_core.token_state import InMemoryTokenState


class TestInMemoryTokenState:
    def test_empty_state_has_no_tokens_and_is_expired(self):
        state = InMemoryTokenState(now_fn=lambda: 1000)

        assert state.has_tokens() is False
        assert state.access_token is None
        assert state.refresh_token is None
        assert state.is_expired() is True
        assert state.needs_refresh() is False

    def test_token_with_metadata_computes_expiry(self):
        state = InMemoryTokenState(now_fn=lambda: 1050)
        state.set_tokens(
            TokenSet(
                access_token="access",
                refresh_token="refresh",
                created_at=1000,
                expires_in=100,
            )
        )

        assert state.expires_at == 1100
        assert state.is_expired() is False
        assert state.needs_refresh() is True

    def test_token_is_expired_after_expiry_time(self):
        state = InMemoryTokenState(now_fn=lambda: 1200)
        state.set_tokens(
            TokenSet(
                access_token="access",
                refresh_token="refresh",
                created_at=1000,
                expires_in=100,
            )
        )

        assert state.is_expired() is True

    def test_token_without_metadata_is_treated_as_present_not_refreshable(self):
        state = InMemoryTokenState(now_fn=lambda: 1000)
        state.set_tokens(TokenSet(access_token="access", refresh_token="refresh"))

        assert state.has_tokens() is True
        assert state.is_expired() is False
        assert state.needs_refresh() is False

    def test_clear_resets_state(self):
        state = InMemoryTokenState(now_fn=lambda: 1000)
        state.set_tokens(TokenSet(access_token="access", refresh_token="refresh"))

        state.clear()

        assert state.token_set is None
        assert state.has_tokens() is False
