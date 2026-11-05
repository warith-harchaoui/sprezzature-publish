"""
The release-notes feed is written into the hub's site by default.

``changelog_feed`` was extracted from the hub with ``parents[2]`` still meaning
"the hub". From ``sprezzature-publish/scripts/`` it means the folder holding
the clones, so a bare ``sprezzature-publish-changelog`` wrote ``~/web`` — on
this machine, a different site.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from pathlib import Path

import changelog_feed

REPO = Path(__file__).resolve().parents[1]


def test_the_default_root_is_the_hub_beside_this_clone() -> None:
    assert changelog_feed._DEFAULT_ROOT == REPO.parent / "sprezzature"
