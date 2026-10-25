"""
The five surfaces must describe the same nine tools.

This package publishes one toolkit through a library, two front doors plus a
command per tool, an HTTP API, an MCP server, and a `SKILL.md` that lives in
the monorepo. The risk is never that a surface is missing; it is that they
quietly stop agreeing — a tool reachable from one front door and not the
other, an exported name no module defines, a command whose ``--help`` names
something ``pip install`` never created.

None of that is hypothetical. Packaging this turned up five commands
announcing a different name from the one installed, one of them announcing a
*module* name; four exported names that existed nowhere; and a route that
would have returned 500 on every call because it read an attribute the
renderer does not have. Each was found by checking rather than by reading.

Nothing here needs a model or a network: these read what the surfaces
declare.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 — tomllib landed in 3.11
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
CONSOLE_SCRIPTS: dict[str, str] = PYPROJECT["project"]["scripts"]


def _source_of(target: str) -> str:
    """The source file a ``[project.scripts]`` target names."""
    module = target.split(":")[0]
    if module.startswith("sprezzature_publish_scripts."):
        return (ROOT / "scripts" / f"{module.split('.')[-1]}.py").read_text(encoding="utf-8")
    return (ROOT / Path(*module.split(".")).with_suffix(".py")).read_text(encoding="utf-8")


# ── Every declared command exists, and says its own name ───────────────────


@pytest.mark.parametrize("command", sorted(CONSOLE_SCRIPTS))
def test_every_console_script_points_at_something_importable(command: str) -> None:
    """
    An entry naming a module that is not there installs without complaint and
    fails on first run, which is the worst moment to find out.
    """
    module_name, _, attribute = CONSOLE_SCRIPTS[command].partition(":")
    module = importlib.import_module(module_name)
    assert callable(getattr(module, attribute, None)), (
        f"{CONSOLE_SCRIPTS[command]} has no callable {attribute}()"
    )


@pytest.mark.parametrize("command", sorted(CONSOLE_SCRIPTS))
def test_a_command_announces_the_name_that_installs_it(command: str) -> None:
    """
    The regression this file was written for, and it fired five times.

    A reader's only way to learn a command is its ``--help``. Whatever name
    that prints has to be the name ``pip install`` actually created, or the
    instruction is worse than none: it names a command that does not exist,
    and the reader cannot tell whether they mistyped it or the tool lied.
    ``sprezzature-publish-narrate`` announced itself as ``narrate_post`` — a
    module name, which is not something anyone can type.

    The click front door is skipped: click takes its name from the installed
    entry point rather than from a literal in the source, so there is nothing
    here that could disagree.
    """
    source = _source_of(CONSOLE_SCRIPTS[command])
    declared = re.findall(r'prog\s*=\s*"([^"]+)"', source)
    if not declared:
        pytest.skip("this command takes its name from the entry point itself")
    assert command in declared, (
        f"`{command}` is the command pip installs, but its --help introduces itself as {declared!r}"
    )


def test_the_commands_are_named_for_this_package() -> None:
    """
    Every installed command is guessable from the package name.

    ``make-site`` is the one exception, and a deliberate one: it is the
    argparse front door, and the house spells those ``make-X`` —
    ``make-map``, ``make-figure``, ``make-alt``.
    """
    for command in CONSOLE_SCRIPTS:
        assert command.startswith("sprezzature-publish") or command == "make-site", command


# ── One front door, over one catalogue ─────────────────────────────────────


def test_the_command_list_is_the_catalogue() -> None:
    """
    One catalogue, one parser.

    There were two front doors until 2026-10-25, kept from drifting by sharing
    this table; the click module imported ``TOOLS`` from the argparse one, so
    neither could be removed without the other. Click is the only parser now,
    and the table is still the single source of the command list.
    """
    from sprezzature_publish._tools import TOOLS
    from sprezzature_publish.cli import main

    assert set(main.commands) - {"tools"} == set(TOOLS)


def test_the_two_spellings_are_one_callable() -> None:
    """
    ``make-site`` and ``sprezzature-publish`` must resolve to the same target.

    Two names that each had their own implementation is how the pair drifted.
    Two names pointing at one function cannot.
    """
    scripts = PYPROJECT["project"]["scripts"]
    assert scripts["make-site"] == scripts["sprezzature-publish"]


def test_click_is_a_base_dependency_and_no_second_parser_grows_back() -> None:
    """With argparse gone, no parser ships with Python."""
    project = PYPROJECT["project"]
    assert any(dep.startswith("click") for dep in project["dependencies"])
    assert "click" not in project.get("optional-dependencies", {})
    assert not (ROOT / "sprezzature_publish" / "cli_click.py").exists()
    assert "import argparse" not in (ROOT / "sprezzature_publish" / "cli.py").read_text(
        encoding="utf-8"
    )


def test_every_tool_in_the_catalogue_resolves() -> None:
    """A tool listed in the front door and importable from nowhere is a lie."""
    from sprezzature_publish._tools import TOOLS

    for tool, (module_name, summary) in TOOLS.items():
        path = ROOT / "scripts" / f"{module_name}.py"
        assert path.is_file(), f"{tool} names {module_name}, which is not there"
        assert len(summary.split()) >= 6, (
            f"{tool}'s one-line summary is the only thing a reader sees in "
            f"`make-site --help`; {summary!r} does not earn its place"
        )


def test_the_command_line_offers_both_parsers() -> None:
    """
    argparse *and* click, which is the house contract (``SURFACES.md``).

    Not one or the other: argparse is in the standard library, so the front
    door works anywhere Python does; click carries the richer validation.
    """
    argparse_door = _source_of(CONSOLE_SCRIPTS["make-site"])
    click_door = _source_of(CONSOLE_SCRIPTS["sprezzature-publish"])
    assert "make_parser" in argparse_door or "argparse" in argparse_door
    assert "import click" in click_door


# ── The library is a library ───────────────────────────────────────────────


def test_every_exported_name_exists() -> None:
    """
    The defect this caught: four exports that no module defined.

    A library surface advertising names nothing implements is worse than a
    thin one — it fails at the moment somebody trusts it.
    """
    import sprezzature_publish

    missing = []
    for name, module_name in sprezzature_publish._EXPORTS.items():
        source = (ROOT / "scripts" / f"{module_name}.py").read_text(encoding="utf-8")
        if not re.search(rf"^def {re.escape(name)}\(", source, re.M):
            missing.append(f"{name} (claimed from {module_name})")
    assert not missing, f"exported names that do not exist: {missing}"


def test_the_library_imports_with_no_extras_at_all() -> None:
    """
    ``import sprezzature_publish`` must work after a bare ``pip install``.

    The lint has no dependencies on purpose — that is why it is worth putting
    in a pre-commit hook — and an ``__init__`` that imported a Markdown
    engine eagerly would take that away from everyone who only lints.
    """
    import sprezzature_publish

    assert callable(sprezzature_publish.lint_file)
    assert sprezzature_publish.__all__


def test_an_unknown_name_is_an_attribute_error_not_an_import_error() -> None:
    """A typo should read as a typo, not as a missing dependency."""
    import sprezzature_publish

    with pytest.raises(AttributeError):
        sprezzature_publish.definitely_not_a_tool
