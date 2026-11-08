"""
The two functions the package's docstring shows can be called the way it
shows them.

``lint_file(path)`` raised ``TypeError`` under a doctest marked ``+SKIP``, so
the suite never saw it.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import lint_markdown as lm  # noqa: E402
import md_to_html as mh  # noqa: E402


def test_lint_file_takes_a_path_and_nothing_else(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text("# Page\n\n### Skipped\n", encoding="utf-8")

    findings, notes = lm.lint_file(page)

    assert [f.rule for f in findings] == ["MD001"]
    assert notes == []


def test_convert_one_takes_two_paths_and_nothing_else(tmp_path: Path) -> None:
    source = tmp_path / "page.md"
    source.write_text("# Page\n\nSome words on the page.\n", encoding="utf-8")

    mh.convert_one(source, tmp_path / "out")

    assert (tmp_path / "out" / "page.html").is_file()
