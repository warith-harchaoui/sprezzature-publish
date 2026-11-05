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
DOCS = (
    "README.md",
    "LISEZMOI.md",
    "EXAMPLES.md",
    # The references carry the longest worked examples, and two of them named
    # commands that had been renamed (`-md-to-html`, `-narrate-post`).
    *sorted(str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "references").glob("*.md")),
)

#: A line that starts with one of this package's commands, inside a fence.
_INVOCATION = re.compile(r"^(make-site|sprezzature-publish[a-z-]*)\s+(.+)$")
_FENCE = re.compile(r"```(?:bash|sh|console)\n(.*?)```", re.S)
_FLAG = re.compile(r"(--[a-z][a-z0-9-]*)")
#: Every tool declares its flags with Click since argparse left the suite.
#: The first version of this file read only the argparse spelling, which made
#: every Click tool look like it accepted nothing. See ``_accepted_flags``.
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
    real: ``_click.sprezzature_command`` adds ``-h`` / ``--help`` and
    ``-V`` / ``--version`` to every command. Those are added here, so the set
    is the whole truth rather than most of it.
    """
    path = REPO_ROOT / "scripts" / f"{module_name}.py"
    if not path.is_file():
        return set()
    source = path.read_text(encoding="utf-8")
    return set(_CLICK_OPTION.findall(source)) | _SHARED_FLAGS


#: Flags every command gets from ``_click.sprezzature_command``.
_SHARED_FLAGS: set[str] = {"--help", "--version"}


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


def test_there_are_documented_commands_to_check() -> None:
    """A regex that stops matching would make the test below vacuous."""
    found = _documented()
    assert len(found) >= 8, [line for _f, line, _t, _fl in found]


def test_every_documented_flag_is_one_the_parser_accepts() -> None:
    """A flag in a README is an instruction, and instructions are tested."""
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


# ── The whole line, not only its flags ──────────────────────────────────────
#
# The flag check above passed on four lines that did not run. Every flag on
# them existed; the line still failed: `html README.md docs/` gave the command
# two positional arguments where it takes one, `indexes site/` gave one to a
# command that takes none, and `readalong … --narration …` with neither
# `--out` nor `--check` is refused by the tool's own body. A flag that exists
# is not a line that runs, so the line goes to the parser itself.

#: Where a documented line stops being arguments: a pipe, a redirection,
#: a comment, a backgrounding ampersand.
_LINE_END = {"|", ">", ">>", "#", "&", "&&", ";"}


def _logical_lines(block: str) -> list[str]:
    """The block's lines with shell continuations joined, as a reader types them."""
    out: list[str] = []
    pending = ""
    for raw in block.splitlines():
        line = raw.rstrip()
        if line.endswith("\\"):
            pending += line[:-1] + " "
            continue
        out.append((pending + line).strip())
        pending = ""
    if pending:
        out.append(pending.strip())
    return out


def _documented_argv() -> list[tuple[str, str, str, list[str]]]:
    """``(file, line, tool, argv)`` for every complete invocation in the docs."""
    import shlex

    out = []
    tools = _tools()
    for name in DOCS:
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        for block in _FENCE.findall(path.read_text(encoding="utf-8")):
            for line in _logical_lines(block):
                if not _INVOCATION.match(line):
                    continue
                words = shlex.split(line, comments=True)
                for i, word in enumerate(words):
                    if word in _LINE_END:
                        words = words[:i]
                        break
                head, rest = words[0], words[1:]
                if head == "make-site" or head == "sprezzature-publish":
                    if not rest or rest[0] not in tools:
                        continue
                    tool, argv = rest[0], rest[1:]
                else:
                    tool, argv = head.removeprefix("sprezzature-publish-"), rest
                if tool in tools:
                    out.append((name, line, tool, argv))
    return out


def _command(tool: str) -> tuple[object, object]:
    """The tool's module and the click command its console script runs."""
    import importlib

    import click

    module = importlib.import_module(f"sprezzature_publish_scripts.{_tools()[tool]}")
    wanted = f"sprezzature-publish-{tool}"
    for value in vars(module).values():
        if isinstance(value, click.Command) and value.name == wanted:
            return module, value
    raise AssertionError(f"no click command named {wanted} in {module.__name__}")


def _materialise(argv: list[str], root: Path) -> None:
    """Create every path the line names, so ``exists=True`` judges the line, not the disk."""
    for word in argv:
        if word.startswith("-") or "://" in word or "=" in word:
            continue
        if not ("/" in word or re.search(r"\.[A-Za-z0-9]+$", word)):
            continue
        target = root / word
        if word.endswith("/"):
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()


def test_there_are_whole_lines_to_check() -> None:
    """Continuations joined, every tool reached: a vacuous pass is not a pass."""
    found = _documented_argv()
    assert len(found) >= 30, [line for _f, line, _t, _a in found]
    assert {tool for _f, _l, tool, _a in found} >= {"html", "indexes", "readalong"}


def test_every_documented_line_is_one_the_tool_accepts(tmp_path: Path, monkeypatch: object) -> None:
    """Each line goes through the tool's own parser; nothing is run."""
    import inspect

    import click

    monkeypatch.chdir(tmp_path)  # type: ignore[attr-defined]
    wrong: list[str] = []
    for file, line, tool, argv in _documented_argv():
        module, command = _command(tool)
        _materialise(argv, tmp_path)
        try:
            ctx = command.make_context(command.name, list(argv))  # type: ignore[attr-defined]
        except click.UsageError as exc:
            wrong.append(f"{file}: `{line}`: {exc.format_message()}")
            continue
        # A requirement that depends on the mode lives in the tool's body; a
        # tool that has one says it through `usage_problem`, the same function
        # its body calls.
        check = getattr(module, "usage_problem", None)
        if check is not None:
            wanted = inspect.signature(check).parameters
            problem = check(**{k: v for k, v in ctx.params.items() if k in wanted})
            if problem:
                wrong.append(f"{file}: `{line}`: {problem}")
    assert not wrong, "these documented command lines do not run:\n  " + "\n  ".join(wrong)


def test_every_documented_command_exists() -> None:
    """A renamed command leaves its old name in the prose, where nothing parses it.

    Both checks above skip a name that is not in ``[project.scripts]``, which
    is right for ``make-site tools`` and wrong for ``sprezzature-publish-md-to-html``:
    the second is a command a reader types and the shell does not find.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    installed = set(re.findall(r"^([a-z][a-z0-9-]*)\s*=\s*\"", pyproject, re.M))
    unknown = []
    for name in DOCS:
        path = REPO_ROOT / name
        for block in _FENCE.findall(path.read_text(encoding="utf-8")):
            for line in _logical_lines(block):
                match = re.match(r"^(sprezzature-publish[a-z-]*)\b", line)
                if match and match.group(1) not in installed:
                    unknown.append(f"{name}: `{line}`")
    assert not unknown, "commands no console script installs:\n  " + "\n  ".join(unknown)
