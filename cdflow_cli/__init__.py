# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""DonationFlow CLI Tools."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("cdflow-cli")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"