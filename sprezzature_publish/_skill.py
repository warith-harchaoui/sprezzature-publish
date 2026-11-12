"""
The skill this package ships, and the command that puts it where an agent reads.

A skill is the folder an agent reads to know when to reach for a tool, what
the house rules are and which command to run: a ``SKILL.md`` whose front
matter carries the description the agent routes on, beside the reference
documents it opens once it has chosen (the format is Anthropic's, *The
Complete Guide to Building Skills for Claude*). Claude Code reads skills from
``~/.claude/skills/``, OpenCode from ``~/.opencode/skills/``.

Until 2026-11-12 the skills of this suite lived only in the ``sprezzature``
hub. ``pip install sprezzature-maps`` gave a library, a command line, an HTTP
API and an MCP server, and no skill: the one surface written for an agent was
the one that did not travel with the package. Each brick now carries its own,
inside the package, so a wheel holds all five surfaces and the hub only
gathers them.

This file is shared verbatim by the ten bricks and kept in step by the hub's
``scripts/sync_helpers.py``; nothing in it names a brick. The skill's name is
the package's, hyphenated -- ``sprezzature_maps`` ships ``sprezzature-maps``
-- because a Python package cannot carry a hyphen and a skill folder is read
under the hyphenated name.

::

    sprezzature-maps-skill                  # report: installed copy in step?
    sprezzature-maps-skill --install        # copy it into ~/.claude/skills
    sprezzature-maps-skill --install --agent opencode
    sprezzature-maps-skill --path           # where pip put it

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import filecmp
import shutil
from pathlib import Path

import click

#: The package this copy sits in; the skill folder is inside it.
PACKAGE_DIR: Path = Path(__file__).resolve().parent

#: The folder name an agent reads the skill under: the package's, hyphenated.
SKILL_NAME: str = PACKAGE_DIR.name.replace("_", "-")

#: Where each agent looks for skills, relative to the user's home directory.
AGENT_DIRS: dict[str, str] = {
    "claude": ".claude/skills",
    "opencode": ".opencode/skills",
}


def skill_path() -> Path:
    """
    The folder of the skill this package ships.

    Returns
    -------
    pathlib.Path
        The directory holding ``SKILL.md`` and its ``references/``.
    """
    return PACKAGE_DIR / "skill"


def differences(source: Path, installed: Path) -> list[str]:
    """
    Files that differ between the shipped skill and an installed copy.

    Parameters
    ----------
    source : pathlib.Path
        The skill folder inside this package.
    installed : pathlib.Path
        The folder under the agent's skills directory.

    Returns
    -------
    list of str
        Relative paths that differ, are missing, or are extra. Empty when the
        two folders hold the same bytes.
    """
    if not installed.is_dir():
        return ["(not installed)"]
    out: list[str] = []
    shipped: set[Path] = set()
    for path in sorted(source.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(source)
        shipped.add(rel)
        other = installed / rel
        if not other.is_file():
            out.append(f"missing: {rel}")
        elif not filecmp.cmp(path, other, shallow=False):
            out.append(f"differs: {rel}")
    # A file the installed copy holds and the package no longer ships is
    # still read by the agent: a reference deleted upstream lives on there.
    for path in sorted(installed.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            rel = path.relative_to(installed)
            if rel not in shipped:
                out.append(f"extra: {rel}")
    return out


def install(source: Path, target: Path) -> Path | None:
    """
    Copy `source` over `target`, moving any existing copy aside first.

    Returns
    -------
    pathlib.Path or None
        Where the previous copy was moved, or None if there was none. The
        backup lands beside the skills directory rather than inside it: a
        folder left within it is itself read as a skill, which is how a
        superseded copy comes back to life.
    """
    moved: Path | None = None
    if target.exists():
        backups = target.parent.parent / "skills-superseded"
        backups.mkdir(parents=True, exist_ok=True)
        moved = backups / target.name
        if moved.exists():
            shutil.rmtree(moved)
        shutil.move(str(target), str(moved))
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return moved


def run(do_install: bool, agent: str, show_path: bool, home: Path | None = None) -> int:
    """
    Report whether the installed skill is in step; with `do_install`, refresh it.

    Parameters
    ----------
    do_install : bool
        Copy the shipped skill over the installed one when they differ.
    agent : str
        A key of :data:`AGENT_DIRS`.
    show_path : bool
        Print where pip put the skill, and stop.
    home : pathlib.Path, optional
        The directory the agent's skills folder hangs from. Defaults to the
        user's home; tests pass a temporary one.

    Returns
    -------
    int
        Process exit code: 0, or 1 when the package ships no skill (a broken
        build, not a state to report as "in step").
    """
    source = skill_path()
    if show_path:
        click.echo(source)
        return 0
    if not (source / "SKILL.md").is_file():
        click.echo(f"{SKILL_NAME}: this build ships no skill (looked in {source}).", err=True)
        return 1

    target = (home or Path.home()) / AGENT_DIRS[agent] / SKILL_NAME
    diffs = differences(source, target)
    if not diffs:
        click.echo(f"{SKILL_NAME}: in step with {target}")
        return 0
    head = diffs[0] if len(diffs) == 1 else f"{len(diffs)} files differ"
    click.echo(f"{SKILL_NAME}: {head} ({target})")
    if not do_install:
        click.echo("Pass --install to copy the shipped skill there.")
        return 0
    moved = install(source, target)
    where = f"; the previous copy is at {moved}" if moved else ""
    click.echo(f"{SKILL_NAME}: installed{where}")
    return 0


@click.command(
    name="skill",
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        f"Report whether the {SKILL_NAME} skill an agent reads is in step with "
        "this package, and with --install copy it into the agent's skills "
        "folder (~/.claude/skills by default)."
    ),
    epilog="Reports by default. --install writes under your home directory, "
    "which changes what every future agent session reads.",
)
@click.option("--install", "do_install", is_flag=True,
              help="Copy the shipped skill into the agent's skills folder.")
@click.option("--agent", default="claude", show_default=True,
              type=click.Choice(sorted(AGENT_DIRS)),
              help="Which agent's skills folder to use.")
@click.option("--path", "show_path", is_flag=True,
              help="Print where pip installed the skill, and stop.")
def skill_command(do_install: bool, agent: str, show_path: bool) -> None:
    """Report, or refresh, the installed skill."""
    raise SystemExit(run(do_install, agent, show_path))


def main(argv: list[str] | None = None) -> int:
    """Console-script entry point, ``sprezzature-<brick>-skill``."""
    try:
        skill_command.main(args=argv, prog_name=f"{SKILL_NAME}-skill", standalone_mode=False)
    except SystemExit as exc:
        return int(exc.code or 0)
    except click.exceptions.UsageError as exc:
        exc.show()
        return 2
    except click.exceptions.Exit as exc:
        return exc.exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
