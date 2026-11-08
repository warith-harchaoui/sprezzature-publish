"""
Mermaid is reported, never drawn, and nothing here can reach for it again.

``mmdc`` computed a wrong viewBox: the diagram came out cropped and without
its labels, with no error raised. Warith HARCHAOUI's order is that the suite no
longer uses Mermaid or ``mmdc``, in favour of ``sprezzature-figures``. So a
block must not be rendered, and must not pass in silence either.

The guards read the source statically, because the failure they watch for is a
dependency coming back, and an import behind a flag would not run in any test.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lint_markdown as lm  # noqa: E402
import md_to_html as mh  # noqa: E402

BLOCK = "# Page\n\n```mermaid\nflowchart LR\n  A --> B\n```\n"

#: Where the package tells a reader what it does.
DOCS = [
    "README.md",
    "LISEZMOI.md",
    "TRIGGERS.md",
    "EXAMPLES.md",
    "CODING.md",
    "assets/how-it-works.yaml",
    ".pre-commit-hooks.yaml",
    *(str(p.relative_to(REPO_ROOT)) for p in sorted((REPO_ROOT / "references").glob("*.md"))),
]


def _mmd(tmp_path: Path, text: str):
    page = tmp_path / "page.md"
    page.write_text(text, encoding="utf-8")
    findings, _notes = lm.lint_file(page)
    return [f for f in findings if f.rule == "MMD001"]


def test_a_mermaid_block_gets_a_finding_that_says_what_to_do(tmp_path: Path) -> None:
    findings = _mmd(tmp_path, BLOCK)

    assert [f.line for f in findings] == [3]
    assert findings[0].severity == lm.WARNING
    assert "sprezzature-figures render flowchart" in findings[0].message
    assert "SVG" in findings[0].message


@pytest.mark.parametrize("info", ["Mermaid", "mermaid title=x", "{.mermaid}"])
def test_every_spelling_of_the_fence_is_seen(tmp_path: Path, info: str) -> None:
    assert _mmd(tmp_path, f"```{info}\nA-->B\n```\n")


@pytest.mark.parametrize(
    "text",
    [
        "```python\nprint('mermaid')\n```\n",
        "Mermaid named in a sentence.\n",
        # A page documenting the block shows it inside a longer fence.
        "````markdown\n```mermaid\nA-->B\n```\n````\n",
    ],
)
def test_only_a_real_block_is_reported(tmp_path: Path, text: str) -> None:
    assert not _mmd(tmp_path, text)


def test_the_finding_does_not_flip_the_exit_code(tmp_path: Path) -> None:
    page = tmp_path / "page.md"
    page.write_text(BLOCK, encoding="utf-8")

    assert lm.main([str(page)]) == 0


def test_the_render_flag_is_refused(tmp_path: Path) -> None:
    """Refused, not accepted and ignored: an option that does nothing lies."""
    page = tmp_path / "page.md"
    page.write_text(BLOCK, encoding="utf-8")

    with pytest.raises(SystemExit) as refused:
        lm.main([str(page), "--render-mermaid"])
    assert refused.value.code == 2


def test_the_converter_keeps_the_block_as_code_and_says_so(tmp_path: Path) -> None:
    source = tmp_path / "page.md"
    source.write_text(BLOCK, encoding="utf-8")
    out = tmp_path / "out"

    result = mh.convert_one(source, out)

    assert result.ok
    assert "sprezzature-figures render flowchart" in result.message
    page = (out / "page.html").read_text(encoding="utf-8")
    assert "A --&gt; B" in page
    assert not list(out.glob("*.png"))


def test_a_page_never_carries_a_mermaid_library(tmp_path: Path) -> None:
    source = tmp_path / "page.md"
    source.write_text(BLOCK, encoding="utf-8")

    mh.convert_one(source, tmp_path)

    page = (tmp_path / "page.html").read_text(encoding="utf-8").lower()
    scripts = page.split("<script")[1:]
    assert len(scripts) > 1, "the page was expected to carry its usual scripts"
    assert not [s for s in scripts if "mermaid" in s.split("</script")[0]]


def test_a_page_without_mermaid_is_just_ok(tmp_path: Path) -> None:
    source = tmp_path / "page.md"
    source.write_text("# Page\n\nWords.\n", encoding="utf-8")

    assert mh.convert_one(source, tmp_path / "out").message == "ok"


def _python_sources() -> list[Path]:
    here = Path(__file__).resolve()
    roots = ("sprezzature_publish", "scripts", "tests")
    return [
        p
        for root in roots
        for p in sorted((REPO_ROOT / root).rglob("*.py"))
        if p.resolve() != here and "fixtures" not in p.parts
    ]


def test_the_scan_sees_the_sources() -> None:
    """A scan over nothing would pass for ever."""
    names = {p.name for p in _python_sources()}
    assert {"lint_markdown.py", "md_to_html.py", "api.py"} <= names


def test_nothing_imports_or_shells_out_to_mmdc() -> None:
    offenders: list[str] = []
    for path in _python_sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            imported = []
            if isinstance(node, ast.Import):
                imported = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                imported = [node.module or ""]
            shelled = isinstance(node, ast.Constant) and node.value == "mmdc"
            if shelled or any(name.split(".")[0] == "mmdc" for name in imported):
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")
    assert not offenders, f"mmdc is back: {offenders}"


def test_no_manifest_declares_mmdc() -> None:
    """Text, not ``tomllib``: the floor is 3.10, where importing it breaks collection."""
    declared = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"mmdc' not in declared and "'mmdc" not in declared


def test_no_prompt_is_about_mermaid() -> None:
    prompts = REPO_ROOT / "scripts" / "prompts"
    assert sorted(prompts.glob("*.yaml")), "the prompts folder moved"
    assert not [p.name for p in prompts.glob("*") if "mermaid" in p.name.lower()]


@pytest.mark.parametrize("name", DOCS)
def test_a_document_mentions_mermaid_only_as_the_finding(name: str) -> None:
    """The word may stay only beside the rule, or beside what replaces it."""
    lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
    stray = [
        line
        for line in lines
        if "mermaid" in line.lower() and not ("MMD001" in line or "sprezzature-figures" in line)
    ]
    assert not stray, f"{name} still proposes Mermaid: {stray}"
