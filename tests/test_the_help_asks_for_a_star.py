"""Every command line ends its ``--help`` on the same invitation to star the repository.

One blank line, then ``⭐️ on GitHub: <url>``, as the last line of the help of
each console script the package installs (the MCP and skill servers are not
command lines).
"""

import importlib
import sys

import pytest

STAR = "⭐️ on GitHub: https://github.com/warith-harchaoui/sprezzature-publish"

# Hand-listed rather than read from pyproject.toml: tomllib does not exist on
# Python 3.10, the floor, and an installed wheel has no pyproject.toml anyway.
ENTRY_POINTS = [
    ("make-site", "sprezzature_publish.cli:main"),
    ("sprezzature-publish", "sprezzature_publish.cli:main"),
    ("sprezzature-publish-lint", "sprezzature_publish_scripts.lint_markdown:main"),
    ("sprezzature-publish-audit", "sprezzature_publish_scripts.audit_site:main"),
    ("sprezzature-publish-cta", "sprezzature_publish_scripts.cta:main"),
    ("sprezzature-publish-faq", "sprezzature_publish_scripts.faq:main"),
    ("sprezzature-publish-findable", "sprezzature_publish_scripts.findable:main"),
    ("sprezzature-publish-html", "sprezzature_publish_scripts.md_to_html:main"),
    ("sprezzature-publish-icons", "sprezzature_publish_scripts.favicons:main"),
    ("sprezzature-publish-indexes", "sprezzature_publish_scripts.site_indexes:main"),
    ("sprezzature-publish-meta", "sprezzature_publish_scripts.meta_from_ollama:main"),
    ("sprezzature-publish-plain", "sprezzature_publish_scripts.plain_language:main"),
    ("sprezzature-publish-changelog", "sprezzature_publish_scripts.changelog_feed:main"),
    ("sprezzature-publish-narrate", "sprezzature_publish_scripts.narrate_post:main"),
    ("sprezzature-publish-readalong", "sprezzature_publish_scripts.readalong:main"),
]


@pytest.mark.parametrize(("name", "target"), ENTRY_POINTS, ids=[n for n, _ in ENTRY_POINTS])
def test_the_help_ends_with_the_star_line(name, target, monkeypatch, capsys):
    module, attr = target.split(":")
    main = getattr(importlib.import_module(module), attr)
    monkeypatch.setattr(sys, "argv", [name, "--help"])
    try:
        main()
    except SystemExit as exc:
        assert exc.code in (0, None)
    lines = capsys.readouterr().out.rstrip().splitlines()
    assert lines[-1].strip() == STAR
    assert lines[-2].strip() == ""
