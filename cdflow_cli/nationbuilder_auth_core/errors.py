# SPDX-FileCopyrightText: 2026 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""Error types for the runtime-neutral NationBuilder auth core."""


class AuthConfigurationError(ValueError):
    """Raised when required OAuth configuration is missing or invalid."""


class TokenExchangeError(RuntimeError):
    """Raised when an authorization code cannot be exchanged for tokens."""


class TokenRefreshError(RuntimeError):
    """Raised when a refresh token cannot obtain a new access token."""
