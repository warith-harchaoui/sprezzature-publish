"""
Three tools promise click and the standard library, and nothing else.

``CODING.md`` makes the promise for ``lint_markdown``, ``site_indexes`` and
``audit_site``: the lint is worth a pre-commit hook because it runs in
milliseconds with nothing heavy behind it, the indexes are text, and the
audit reads somebody else's site on a machine that has nothing else. Since
2026-11-01 every heavier dependency is in the base install, so nothing at
install time catches an ``import markdown`` slipped into one of them any more:
the import would simply work, and the promise would be gone in silence.

Read statically, at module level only. The lint's optional halves
(``--render-mermaid``, ``--ai``) import ``mmdc`` and a model client inside a
function or a ``try``, which is exactly the shape the promise allows.

Author
------
Warith HARCHAOUI <warithmetics@deraison.ai>
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"

#: The tools under the promise, and the siblings each may import because
#: they are themselves click and the standard library.
LIGHT = {
    "lint_markdown": {"_click"},
    "site_indexes": {"_click"},
    "audit_site": {"_click", "site_indexes"},
}


def _top_level_imports(path: Path) -> set[str]:
    """First segment of every import statement that runs when the module loads."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("tool", sorted(LIGHT))
def test_a_light_tool_imports_click_and_the_standard_library_only(tool: str) -> None:
    allowed = set(sys.stdlib_module_names) | {"__future__", "click"} | LIGHT[tool]
    extra = sorted(_top_level_imports(SCRIPTS / f"{tool}.py") - allowed)
    assert not extra, (
        f"{tool}.py imports {extra} at module level; CODING.md promises click and "
        f"the standard library only. Import it lazily behind the flag that needs it."
    )


def test_the_check_sees_imports_at_all() -> None:
    """A parser that found nothing would pass every tool."""
    assert {"click", "re", "sys"} <= _top_level_imports(SCRIPTS / "lint_markdown.py")
