# SPDX-FileCopyrightText: 2026-present M. Greyson Christoforo <grey@christoforo.net>
#
# SPDX-License-Identifier: MIT

"""
take package files from vcs releases and turn them into a repo that pacman can use
"""

from .libreleases2repo import Releases2Repo
from .__about__ import __version__

__all__ = [
    "Releases2Repo",
    "__version__",
]


def __dir__() -> list[str]:
    return __all__
