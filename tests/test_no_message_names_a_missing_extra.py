"""
No message tells a reader to install an extra this package does not declare.

The extras were folded into the base on 2026-11-01. Three import guards still
said "which is the [prose] extra", so the one sentence a reader gets when the
model client is missing named an option pip does not have. The check reads
every ``[name] extra`` in the code and holds it against
``[project.optional-dependencies]``, which is the shape of the defect rather
than the three lines it was found in.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_EXTRAS_SECTION_RE = re.compile(r"^\[project\.optional-dependencies\]\s*$(.*?)(?=^\[|\Z)", re.M | re.S)
_EXTRA_NAME_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*=", re.M)
#: ``[prose] extra``, ``the [html] extra``: a bracketed name followed by "extra".
_NAMED_EXTRA_RE = re.compile(r"\[([a-z][a-z0-9-]*)\]`? extra")


def _declared_extras() -> set[str]:
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    section = _EXTRAS_SECTION_RE.search(text)
    return set(_EXTRA_NAME_RE.findall(section.group(1))) if section else set()


def test_the_declared_extras_are_read() -> None:
    """A regex that stopped matching would make the next test pass on nothing."""
    assert "dev" in _declared_extras()


def test_every_named_extra_exists() -> None:
    declared = _declared_extras()
    named: list[str] = []
    for folder in ("scripts", "sprezzature_publish"):
        for path in sorted((REPO_ROOT / folder).glob("*.py")):
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for name in _NAMED_EXTRA_RE.findall(line):
                    if name not in declared:
                        named.append(f"{folder}/{path.name}:{lineno}: [{name}]")
    assert not named, "these name an extra pyproject.toml does not declare:\n" + "\n".join(named)
