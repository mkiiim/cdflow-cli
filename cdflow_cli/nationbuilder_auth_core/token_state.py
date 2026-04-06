# SPDX-FileCopyrightText: 2026 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""Instance-scoped NationBuilder token state and validity rules."""

import time
from dataclasses import dataclass, field
from typing import Optional

from .models import TokenSet

DEFAULT_REFRESH_WINDOW_SECONDS = 60


@dataclass
class InMemoryTokenState:
    """Instance-scoped token state for NationBuilder auth flows."""

    token_set: Optional[TokenSet] = None
    refresh_window_seconds: int = DEFAULT_REFRESH_WINDOW_SECONDS
    now_fn: callable = field(default=time.time, repr=False)

    def set_tokens(self, token_set: TokenSet) -> None:
        """Replace the current token state."""
        self.token_set = token_set

    def clear(self) -> None:
        """Remove any current token state."""
        self.token_set = None

    @property
    def access_token(self) -> Optional[str]:
        """Current access token, if present."""
        return self.token_set.access_token if self.token_set else None

    @property
    def refresh_token(self) -> Optional[str]:
        """Current refresh token, if present."""
        return self.token_set.refresh_token if self.token_set else None

    @property
    def expires_at(self) -> Optional[float]:
        """Absolute token expiry timestamp, if metadata is available."""
        if not self.token_set:
            return None
        if self.token_set.created_at is None or self.token_set.expires_in is None:
            return None
        return self.token_set.created_at + self.token_set.expires_in

    def has_tokens(self) -> bool:
        """Whether an access token is currently present."""
        return bool(self.token_set and self.token_set.access_token)

    def is_expired(self) -> bool:
        """Whether the current token is expired."""
        if not self.token_set or not self.token_set.access_token:
            return True

        expires_at = self.expires_at
        if expires_at is None:
            return False
        return self.now_fn() >= expires_at

    def needs_refresh(self) -> bool:
        """Whether the token should be refreshed before use."""
        if not self.token_set or not self.token_set.access_token:
            return False
        if not self.token_set.refresh_token:
            return False

        expires_at = self.expires_at
        if expires_at is None:
            return False

        return (expires_at - self.now_fn()) <= self.refresh_window_seconds
