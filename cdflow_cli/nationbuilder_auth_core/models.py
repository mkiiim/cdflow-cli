# SPDX-FileCopyrightText: 2026 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""Shared models for runtime-neutral NationBuilder auth flows."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OAuthConfig:
    """Configuration needed to perform NationBuilder OAuth token operations."""

    slug: str
    client_id: str
    client_secret: str
    redirect_uri: str


@dataclass(frozen=True)
class TokenSet:
    """Normalized NationBuilder token response."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    created_at: Optional[float] = None
