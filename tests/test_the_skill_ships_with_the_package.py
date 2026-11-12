"""
The skill an agent reads travels with ``pip install``, like the other four surfaces.

Until 2026-11-12 every brick's ``SKILL.md`` lived in the ``sprezzature`` hub
only: ``pip install sprezzature-maps`` gave a library, a command line, an HTTP
API and an MCP server, and nothing an agent could route on. These checks hold
the skill inside the package, declared in ``pyproject.toml`` so the wheel
carries it, and installable by the brick's own command.

Shared verbatim by the ten bricks and kept in step by the hub's
``scripts/sync_helpers.py``: nothing here names a brick; the package is found
from the ``_skill.py`` beside it.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = next(REPO_ROOT.glob("sprezzature_*/_skill.py")).parent
PACKAGE = PACKAGE_DIR.name
BRICK = PACKAGE.replace("_", "-")
skill = importlib.import_module(f"{PACKAGE}._skill")


def _front_matter() -> dict[str, str]:
    """The top-level keys of SKILL.md's front matter, folded values joined.

    Read by hand rather than with a YAML library, which not every brick
    depends on: the keys are flat, and a folded value is its indented lines.
    """
    text = (PACKAGE_DIR / "skill" / "SKILL.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), "SKILL.md must open on YAML front matter"
    out: dict[str, str] = {}
    key = ""
    for line in text.split("---\n", 2)[1].splitlines():
        top = re.match(r"([a-z_-]+):\s*(.*)$", line)
        if top:
            key = top.group(1)
            value = top.group(2)
            out[key] = "" if value in (">", ">-", "|", "|-") else value.strip("\"'")
        elif key and line.startswith(" "):
            out[key] = (out[key] + " " + line.strip()).strip()
    return out


def test_the_package_holds_a_skill_named_after_it() -> None:
    meta = _front_matter()
    assert meta["name"] == BRICK == skill.SKILL_NAME
    # The Anthropic guide caps the description an agent routes on at 1024
    # characters, and asks it to say when to use the skill, not only what.
    assert len(meta["description"]) <= 1024
    assert "Use it when" in meta["description"]


def test_the_skill_carries_its_trigger_catalogue() -> None:
    catalogue = PACKAGE_DIR / "skill" / "references" / "triggers.md"
    assert catalogue.is_file(), f"{catalogue} is what the description points the agent to"


def test_the_wheel_is_told_to_carry_the_skill() -> None:
    # Read as text: tomllib arrives with Python 3.11 and the floor is 3.10.
    project = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert re.search(rf'^"{PACKAGE}" = \[[^\]]*"skill/\*\*/\*"', project, re.M), (
        f'pyproject.toml must list "skill/**/*" under package-data for {PACKAGE}; '
        "without it the skill exists in a clone and in no wheel"
    )
    assert f'{BRICK}-skill = "{PACKAGE}._skill:main"' in project


def test_the_library_names_the_skill_folder() -> None:
    package = importlib.import_module(PACKAGE)
    assert package.skill_path() == PACKAGE_DIR / "skill"
    assert "skill_path" in package.__all__


def test_install_copies_it_and_then_reports_it_in_step(tmp_path: Path, capsys) -> None:
    assert skill.run(do_install=True, agent="claude", show_path=False, home=tmp_path) == 0
    installed = tmp_path / ".claude" / "skills" / BRICK
    assert (installed / "SKILL.md").read_bytes() == (
        PACKAGE_DIR / "skill" / "SKILL.md"
    ).read_bytes()
    capsys.readouterr()
    assert skill.run(do_install=False, agent="claude", show_path=False, home=tmp_path) == 0
    assert "in step" in capsys.readouterr().out


def test_a_file_left_behind_in_the_installed_copy_is_reported(tmp_path: Path) -> None:
    installed = tmp_path / BRICK
    skill.install(skill.skill_path(), installed)
    (installed / "references" / "retired.md").write_text("gone upstream\n", encoding="utf-8")
    assert skill.differences(skill.skill_path(), installed) == ["extra: references/retired.md"]


def test_a_reinstall_moves_the_old_copy_out_of_the_skills_folder(tmp_path: Path) -> None:
    skills = tmp_path / ".claude" / "skills"
    skill.install(skill.skill_path(), skills / BRICK)
    moved = skill.install(skill.skill_path(), skills / BRICK)
    # A backup left inside the skills folder would itself be read as a skill.
    assert moved is not None and skills not in moved.parents


def test_the_module_loads_without_a_command_line_library() -> None:
    # The package's __init__ exports skill_path from _skill.py, so a click
    # import here would make `import sprezzature_<brick>` load click -- which
    # some bricks promise it does not. Loaded alone, in a fresh interpreter.
    import subprocess
    import sys

    code = (
        "import importlib.util, sys;"
        f"spec = importlib.util.spec_from_file_location('_skill', {str(PACKAGE_DIR / '_skill.py')!r});"
        "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module);"
        "print('click' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"
