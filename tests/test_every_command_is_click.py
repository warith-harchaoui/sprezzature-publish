"""
Every command this package installs is a click command, and nothing grows argparse back.

The suite decided on 2026-11-04 that its own command lines are click only.
The front door had been click since 2026-10-25, but the per-tool console
scripts and the MCP server still built argparse parsers, so a reader got two
help layouts from one package and a contributor had two ways to declare a
flag. Converting them is half the job; this file is the other half, because a
parser that grows back produces no error, only a ``usage:`` line in lower case.

Two checks, and they look at different things on purpose:

* every ``[project.scripts]`` entry answers ``--help`` with exit 0 and click's
  ``Usage:`` line. Run, not read: a source that never mentions argparse can
  still reach it through a helper;
* no module of the package imports argparse. Read, not run: a module that
  imports it for a code path ``--help`` never takes would pass the first check.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10, tomllib landed in 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
CONSOLE_SCRIPTS: dict[str, str] = tomllib.loads(
    (ROOT / "pyproject.toml").read_text(encoding="utf-8")
)["project"]["scripts"]

#: ``import argparse`` or ``from argparse import ...``, at any indentation:
#: the MCP server imported it inside ``main``, where a top-level-only pattern
#: would not have seen it.
_IMPORTS_ARGPARSE = re.compile(r"^\s*(?:import\s+argparse\b|from\s+argparse\s+import\b)", re.M)


@pytest.mark.parametrize("command", sorted(CONSOLE_SCRIPTS))
def test_every_console_script_answers_help_the_click_way(command: str) -> None:
    """``--help`` exits 0 and prints click's ``Usage:``, never argparse's ``usage:``.

    Called through the entry point's own target rather than through ``PATH``,
    so a stale editable install that never wrote the script cannot make the
    check pass or fail for a reason that is not the code.
    """
    module, _, attribute = CONSOLE_SCRIPTS[command].partition(":")
    code = (
        "import sys\n"
        f"from {module} import {attribute} as entry\n"
        f"sys.argv = [{command!r}, '--help']\n"
        "sys.exit(entry(['--help']))\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"{command} --help exited {proc.returncode}:\n{proc.stderr}"
    first = proc.stdout.lstrip().splitlines()[0] if proc.stdout.strip() else ""
    assert first.startswith("Usage:"), (
        f"{command} --help does not open with click's usage line:\n{proc.stdout[:400]}"
    )


def test_no_module_of_the_package_imports_argparse() -> None:
    """Neither the library nor the scripts it ships reach for argparse."""
    sources = sorted((ROOT / "sprezzature_publish").rglob("*.py")) + sorted(
        (ROOT / "scripts").rglob("*.py")
    )
    assert sources, "no source found: the walk itself is broken"
    offenders = [
        str(path.relative_to(ROOT))
        for path in sources
        if _IMPORTS_ARGPARSE.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"argparse is imported by: {offenders}"


def test_the_argparse_helper_is_gone() -> None:
    """``_argparse.py`` had no caller left once the last tool moved to click."""
    assert not (ROOT / "scripts" / "_argparse.py").exists()
