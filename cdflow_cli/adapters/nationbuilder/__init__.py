# SPDX-FileCopyrightText: 2025 Mark Emila (Caestudy) <https://caestudy.com>
# SPDX-License-Identifier: BSL-1.1

"""
NationBuilder API client package.
Contains classes for interacting with different parts of the NationBuilder API.
"""

from .client import NBClient, encode_uri
from .people_api import NBPeople
from .donation_api import NBDonation
from .membership_api import NBMembership
from .oauth import NationBuilderOAuth

__all__ = ["NBClient", "encode_uri", "NBPeople", "NBDonation", "NBMembership", "NationBuilderOAuth"]
