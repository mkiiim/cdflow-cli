# SPDX-FileCopyrightText: 2026 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""Token provider abstraction for shared NationBuilder clients."""

from typing import Optional

from .token_client import NationBuilderTokenClient
from .token_state import InMemoryTokenState


class NationBuilderTokenProvider:
    """Provide a valid NationBuilder access token using instance-scoped state."""

    def __init__(self, token_state: InMemoryTokenState, token_client: NationBuilderTokenClient):
        self.token_state = token_state
        self.token_client = token_client

    def get_access_token(self) -> Optional[str]:
        """Return a currently valid access token, refreshing if needed."""
        if not self.token_state.has_tokens():
            return None

        if self.token_state.is_expired():
            if not self.token_state.refresh_token:
                return None
            refreshed = self.token_client.refresh_token(self.token_state.refresh_token)
            self.token_state.set_tokens(refreshed)
            return refreshed.access_token

        if self.token_state.needs_refresh():
            refreshed = self.token_client.refresh_token(self.token_state.refresh_token)
            self.token_state.set_tokens(refreshed)
            return refreshed.access_token

        return self.token_state.access_token
