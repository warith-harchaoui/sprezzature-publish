"""
Every command line in the README has to be one the parser accepts.

Found by running the published wheels end to end rather than by reading:
`make-site html README.md --out-dir site/` is what both READMEs told a reader
to type, and the command takes `--out`. Four lines across the two files were
in that state — `html` and `icons` in each — so anyone who copied them got an
argparse usage error. `narrate` really does take `--out-dir`, which is how the
drift survived: two of the three were right, and the wrong ones looked like
the right ones.

This is the same defect as a console script nobody installs, one level down:
the command exists, and the flag beside it does not.

Two tools declare their flags with Click rather than argparse, and the first
version of this check read only ``add_argument``. Their real flags therefore
looked unknown, and the escape hatch written for exactly that case did not
fire: it asked whether the accepted set was empty, and the set is seeded with
``--help`` and ``--version``, so it never is. Both are fixed here. The hatch
now asks whether anything was found *beyond* that seed, which is the question
it meant to ask. Nothing in the docs exercised a Click tool until EXAMPLES.md
was written, which is why the hole stayed invisible.

The check parses the fenced bash blocks and asks each parser what it accepts.
Nothing is executed — a README's examples write files and call models, and a
test suite should not do either to find out whether a flag is spelled right.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS = ("README.md", "LISEZMOI.md", "EXAMPLES.md")

#: A line that starts with one of this package's commands, inside a fence.
_INVOCATION = re.compile(r"^(make-site|sprezzature-publish[a-z-]*)\s+(.+)$")
_FENCE = re.compile(r"```(?:bash|sh|console)\n(.*?)```", re.S)
_FLAG = re.compile(r"(--[a-z][a-z0-9-]*)")
_ADD_ARGUMENT = re.compile(r'add_argument\(\s*\n?\s*"(--[a-z][a-z0-9-]*)"')
#: Half the tools declare their flags with Click, not argparse. Same job,
#: different spelling, and the first version of this file read only the
#: argparse one. See ``_accepted_flags``.
_CLICK_OPTION = re.compile(r'@click\.option\(\s*\n?\s*"(--[a-z][a-z0-9-]*)"')


_ENTRY_POINT = re.compile(
    r'^sprezzature-publish-([a-z-]+)\s*=\s*"sprezzature_publish_scripts\.([a-z_]+):',
    re.M,
)


def _tools() -> dict[str, str]:
    """``make-site`` sub-command -> module name under ``scripts/``.

    Read from ``[project.scripts]`` rather than by importing
    ``sprezzature_publish.cli``. That import needs the
    ``sprezzature_publish_scripts`` package, which exists only in an
    installed copy — in a checkout the files are in ``scripts/`` under no
    package name at all. The first version of this test imported it, failed
    with ModuleNotFoundError inside a helper, and the suite reported the
    tests as passing: a guard that cannot run looks exactly like a guard with
    nothing to report.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    return dict(_ENTRY_POINT.findall(pyproject))


def _accepted_flags(module_name: str) -> set[str]:
    """Flags a tool's parser declares, read from its source.

    Statically, and the first two versions were not. One imported
    ``sprezzature_publish.cli``, which needs the
    ``sprezzature_publish_scripts`` package — present in a wheel, absent from
    a checkout. The next loaded each module by path, and the modules hold
    dataclasses that resolve their field types through
    ``sys.modules[cls.__module__]``, so six of the nine died inside
    ``dataclasses`` with a message naming neither the module nor the cause.

    Both failures had the same shape: the helper called ``pytest.skip``, the
    first tool in the list could not be read, and **the whole test skipped**
    — so the check never ran while the suite said "2 passed, 1 skipped". A
    guard that cannot run looks exactly like a guard with nothing to report,
    which is the class of defect this file exists to catch.

    Reading the source cannot be defeated that way. The objection to it is
    that a flag added through a shared helper would be invisible, and that is
    real: ``_argparse.make_parser`` adds ``-h`` and ``--version`` to every
    parser. Those are read from the helper and added here, so the set is the
    whole truth rather than most of it.
    """
    path = REPO_ROOT / "scripts" / f"{module_name}.py"
    if not path.is_file():
        return set()
    source = path.read_text(encoding="utf-8")
    # Both spellings, because the package ships both parsers on purpose and
    # a tool is free to pick either. Reading only ``add_argument`` made
    # every Click tool look like it accepted nothing but ``--help``.
    flags = set(_ADD_ARGUMENT.findall(source)) | set(_CLICK_OPTION.findall(source))
    return flags | _SHARED_FLAGS


def _shared_flags() -> set[str]:
    """Flags every parser gets from ``_argparse.make_parser``."""
    helper = REPO_ROOT / "scripts" / "_argparse.py"
    if not helper.is_file():
        return {"--help", "--version"}
    return set(_ADD_ARGUMENT.findall(helper.read_text(encoding="utf-8"))) | {
        "--help",
        "--version",
    }


_SHARED_FLAGS: set[str] = set()


def _documented() -> list[tuple[str, str, str, set[str]]]:
    """``(file, line, tool, flags)`` for every invocation in the docs."""
    out = []
    tools = _tools()
    for name in DOCS:
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        for block in _FENCE.findall(path.read_text(encoding="utf-8")):
            for raw in block.splitlines():
                line = raw.strip()
                match = _INVOCATION.match(line)
                if not match:
                    continue
                head, rest = match.group(1), match.group(2).split()
                if head == "make-site":
                    tool = rest[0] if rest and not rest[0].startswith("-") else ""
                else:
                    tool = head.removeprefix("sprezzature-publish-")
                if tool not in tools:
                    continue
                out.append((name, line, tool, set(_FLAG.findall(line))))
    return out


def _ensure_shared() -> None:
    global _SHARED_FLAGS
    if not _SHARED_FLAGS:
        _SHARED_FLAGS = _shared_flags()


def test_there_are_documented_commands_to_check() -> None:
    """A regex that stops matching would make the test below vacuous."""
    found = _documented()
    assert len(found) >= 8, [line for _f, line, _t, _fl in found]


def test_every_documented_flag_is_one_the_parser_accepts() -> None:
    """A flag in a README is an instruction, and instructions are tested."""
    _ensure_shared()
    accepted: dict[str, set[str]] = {}
    wrong: list[str] = []
    blind: set[str] = set()
    for file, line, tool, flags in _documented():
        if tool not in accepted:
            accepted[tool] = _accepted_flags(_tools()[tool])
        if accepted[tool] <= _SHARED_FLAGS:
            blind.add(tool)
            continue
        unknown = sorted(flags - accepted[tool] - {"--help"})
        if unknown:
            wrong.append(f"{file}: `{line}` uses {unknown}")
    assert not wrong, "these documented command lines do not run:\n  " + "\n  ".join(wrong)
    # Said out loud rather than passed over. A tool that stops being
    # introspectable silently removes itself from this check.
    assert not blind, (
        f"found nothing but the shared flags in the source of {sorted(blind)}, "
        f"so their documented flags went unchecked"
    )


def test_the_two_languages_document_the_same_tools() -> None:
    """A tool explained in one language and not the other is half-shipped."""
    by_file: dict[str, set[str]] = {}
    for file, _line, tool, _flags in _documented():
        by_file.setdefault(file, set()).add(tool)
    english, french = by_file.get("README.md", set()), by_file.get("LISEZMOI.md", set())
    assert english and french
    assert english == french, (
        f"only in README: {sorted(english - french)}; only in LISEZMOI: {sorted(french - english)}"
    )
