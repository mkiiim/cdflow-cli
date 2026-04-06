# SPDX-FileCopyrightText: 2026 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""Authenticated header/session helpers for NationBuilder API clients."""

from typing import Dict

from .token_provider import NationBuilderTokenProvider


class NationBuilderAuthorizedSession:
    """Small helper to build authorization headers from a token provider."""

    def __init__(self, token_provider: NationBuilderTokenProvider):
        self.token_provider = token_provider

    def get_auth_headers(self) -> Dict[str, str]:
        """Return bearer auth headers using a currently valid access token."""
        access_token = self.token_provider.get_access_token()
        if not access_token:
            return {}
        return {"Authorization": f"Bearer {access_token}"}
