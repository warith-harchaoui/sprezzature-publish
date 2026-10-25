"""
README.md is this package's long description, so it is read on PyPI as often
as on GitHub — and PyPI has no repository to resolve a relative target
against. ``[EXAMPLES.md](EXAMPLES.md)`` renders there as a link to
``pypi.org/project/sprezzature-publish/EXAMPLES.md``, a 404, and a relative image
source is a broken image on the page a reader lands on.

Every link and every image therefore has to be absolute, or an anchor into
the page itself. Those two forms are the only ones that survive both
renderings. Markdown and inline HTML are both checked: a README that uses
``<img src="assets/logo.png">`` fails the same way.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: ``[text](target)`` — and ``![alt](source)``, which ends the same way.
_MD_TARGET_RE = re.compile(r"\]\(([^)\s]+)\)")

#: ``src="…"`` / ``href="…"`` in the inline HTML a README may carry.
_HTML_TARGET_RE = re.compile(r'(?i)\b(?:src|href)="([^"]+)"')

#: Forms that render correctly wherever the README is shown.
_PORTABLE_PREFIXES = ("https://", "http://", "#", "mailto:", "data:")


#: A fenced code block, including its fence lines.
_FENCE_RE = re.compile(r"^```.*?^```", re.M | re.S)


def _prose(text: str) -> str:
    """The README with its fenced code blocks removed.

    A rule about links has to look only where links are rendered. The usage
    example in this package's README audits ``'<a href="/">x</a>' * 12`` — a
    string of sample markup, inside a ``python`` fence, that nobody can click
    — and the first version of this check read that ``/`` as a relative link
    and failed the build for it. Narrowing the rule is the fix; weakening it
    by allow-listing ``/`` would have let a real relative link through.
    """
    return _FENCE_RE.sub("", text)


def test_readme_targets_are_absolute() -> None:
    """No link or image in README.md needs a git checkout to resolve."""
    readme = REPO_ROOT / "README.md"
    text = _prose(readme.read_text(encoding="utf-8"))
    targets = _MD_TARGET_RE.findall(text) + _HTML_TARGET_RE.findall(text)
    relative = sorted({t for t in targets if not t.startswith(_PORTABLE_PREFIXES)})
    assert not relative, (
        "README.md is the PyPI long description, where a relative target 404s. "
        "Point these at https://github.com/warith-harchaoui/sprezzature/blob/main/… "
        "instead:\n  " + "\n  ".join(relative)
    )


def test_a_relative_link_in_prose_still_fails() -> None:
    """Narrowing the rule must not be the same as removing it.

    Checked directly on the helper rather than by editing README.md, so the
    guard is exercised on every run and not only on the day somebody
    remembers to try it.
    """
    with_fence = '```python\nhref="/"\n```\n\n[docs](EXAMPLES.md)\n'
    prose = _prose(with_fence)
    assert 'href="/"' not in prose, "the fence should have been stripped"
    assert "EXAMPLES.md" in prose, "prose outside the fence must survive"
    targets = _MD_TARGET_RE.findall(prose) + _HTML_TARGET_RE.findall(prose)
    relative = [t for t in targets if not t.startswith(_PORTABLE_PREFIXES)]
    assert relative == ["EXAMPLES.md"]
