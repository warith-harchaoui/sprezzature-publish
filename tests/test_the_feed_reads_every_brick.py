"""
The release-notes feed reads every brick the suite ships.

Its package list was written by hand when the suite had seven bricks, and ui,
publish and video, added after, never had a single entry in the feed. The list
now comes from the hub's ``SKILLS.txt``.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import changelog_feed


def test_a_brick_named_in_the_manifest_reaches_the_feed(tmp_path) -> None:
    hub = tmp_path / "sprezzature"
    hub.mkdir()
    (hub / "SKILLS.txt").write_text(
        "# the manifest\n\nsprezzature-ui\nsprezzature-new-brick\nsprezzature-local\n",
        "utf-8",
    )
    assert changelog_feed.package_repos(tmp_path) == (
        "sprezzature-ui",
        "sprezzature-new-brick",
        "sprezzature",
    )


def test_without_a_hub_the_fallback_still_names_the_three_late_bricks(tmp_path) -> None:
    repos = changelog_feed.package_repos(tmp_path)
    for brick in ("sprezzature-ui", "sprezzature-publish", "sprezzature-video"):
        assert brick in repos
