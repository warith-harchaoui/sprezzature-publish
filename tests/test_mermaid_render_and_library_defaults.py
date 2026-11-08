"""
A Mermaid block reported as rendered has a file behind it, and the two
functions the package's docstring shows can be called the way it shows them.

Both defects passed the suite because nothing looked at the result:
``mmdc.render`` returned a lazy diagram and ignored ``output_path=``, so every
block was "rendered" and no PNG ever existed; and ``lint_file(path)`` raised
``TypeError`` under a doctest marked ``+SKIP``.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import lint_markdown as lm  # noqa: E402
import md_to_html as mh  # noqa: E402

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_a_rendered_block_exists_on_disk(tmp_path: Path) -> None:
    """The real renderer, because a stand-in would repeat the wrong API."""
    target = tmp_path / "deep" / "diagram.png"

    ok, message = lm.render_mermaid_block("graph TD; A-->B;", target)

    assert ok, message
    assert target.read_bytes().startswith(PNG_MAGIC)


def test_an_empty_render_is_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Success is the bytes, not the absence of an exception."""

    class Empty:
        def png(self) -> bytes:
            return b""

    fake = types.ModuleType("mmdc")
    fake.render = lambda source: Empty()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mmdc", fake)
    monkeypatch.setattr(lm, "have_node_mmdc", lambda: False)
    target = tmp_path / "diagram.png"

    ok, _message = lm.render_mermaid_block("graph TD; A-->B;", target)

    assert not ok
    assert not target.exists()


def test_the_inserted_reference_finds_the_png_under_out_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bare file name points beside the document, and fails MD050 next run."""

    def fake_render(_source: str, out_png: Path) -> tuple[bool, str]:
        out_png.parent.mkdir(parents=True, exist_ok=True)
        out_png.write_bytes(PNG_MAGIC)
        return True, "rendered"

    monkeypatch.setattr(lm, "render_mermaid_block", fake_render)
    page = tmp_path / "page.md"
    page.write_text("# Page\n\n```mermaid\ngraph TD; A-->B;\n```\n", encoding="utf-8")

    lm.lint_file(page, render_mermaid=True, out_dir=tmp_path / "diagrams", fix=True)

    assert "](diagrams/page.mermaid-1.png)" in page.read_text(encoding="utf-8")
    findings, _notes = lm.lint_file(page)
    assert not [f for f in findings if f.rule == "MD050"]


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
