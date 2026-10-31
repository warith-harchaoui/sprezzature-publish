"""
An extra that caps the Python window has to say so in the manifest.

The defect, and the one it is *not*
-----------------------------------
``requires-python = ">=3.10"`` with no upper bound is a promise. A **base**
dependency that excludes part of that window breaks ``pip install
sprezzature-audio`` outright, and that cross — manifest against the base
graph — is asserted in the hub, by
``tests/test_no_brick_promises_a_python_its_dependencies_exclude.py``. This
file does not repeat it.

What that one deliberately leaves alone is the extras, because an extra only
breaks itself: the base install staying good on 3.14 while ``pip install
"sprezzature-publish[prose]"`` does not resolve there is a legitimate
arrangement — the base is ``click`` and nothing else on purpose, and the
weight is opt-in. The defect is not the narrowing. The defect is that nobody
knows about it: before this file, ``grep -c 3.14 pyproject.toml`` returned
**0** while three of the nine extras could not be installed on it. What a
reader of the manifest gets instead is

    ERROR: Could not find a version that satisfies the requirement ...

with nothing anywhere having warned them. So the rule here is narrow and
about prose: an extra whose dependencies carry a ceiling must name that
ceiling in its own comment.

The measurement trap this file exists inside
--------------------------------------------
**A floor is not a pin.** ``speaker-helper>=0.11.0`` does not say that 0.11.0
carries ``<3.14``; it says "at least 0.11.0". Reading
``importlib.metadata`` instead — the window of whatever copy happens to be
installed — is a different question with a different answer, and it produces
false accusations: the locally resolved graph of ``[narrate]`` blames
``onnxruntime (>=3.11)`` for excluding 3.10, a transitive package three levels
down whose version nothing in this manifest names. Two neighbouring bricks
were accused the same way on the same afternoon, over ``scipy`` and
``pyproj``.

So :data:`MEASURED_AT_THEIR_FLOOR` below is a reading of the **PyPI index for
the exact floor version this manifest names**, dated, recorded, and compared
back against the manifest on every run. It is not computed from the
environment, which is why this file says the same thing on a laptop with the
whole graph installed and in a CI container that stops at Python 3.12 and
would never meet 3.14 anyway.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# `packaging` and (under 3.11) `tomli` are not declared anywhere in this
# repository and do not need to be: pytest requires `packaging>=22`
# unconditionally and `tomli>=1` on `python_version < "3.11"`, so both are
# present wherever this file can run at all.
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 — tomllib landed in 3.11
    import tomli as tomllib  # type: ignore[no-redef]

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_TEXT = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
PROJECT = tomllib.loads(PYPROJECT_TEXT)["project"]
DISTRIBUTION: str = PROJECT["name"]
EXTRAS: dict[str, list[str]] = PROJECT.get("optional-dependencies", {})

#: ``Requires-Python`` as the PyPI index declares it **for the exact version
#: each line below names**, which is the floor this manifest asks for.
#:
#: Read on 2026-10-31 off the **simple index** —
#: ``https://pypi.org/simple/<name>/`` with
#: ``Accept: application/vnd.pypi.simple.v1+json``, whose per-file
#: ``requires-python`` is the authority — not off ``importlib.metadata`` and
#: not off the JSON API. Re-read it, do not infer it.
#:
#: The uncapped readings are kept rather than omitted, because an absence that
#: was measured and an absence that was never looked at are different facts.
#: Not one entry here carries the ceiling, which is this package's whole
#: shape: its extras are light third-party libraries, and the cap arrives only
#: through the two sibling-suite dependencies in the table below.
MEASURED_AT_THEIR_FLOOR: dict[tuple[str, str], str] = {
    # Every floor this manifest names whose dependency declares a window at
    # all. None of them carries the ceiling directly — which is the finding,
    # not an empty result: in this package the cap always arrives one hop
    # down, through the table below.
    ("markdown", "3.5"): ">=3.8",
    ("Pillow", "10.0.0"): ">=3.8",
    ("requests", "2.31"): ">=3.7",
    ("mmdc", "0.3"): ">=3.4",
    ("langdetect", "1.0.9"): "",
    ("sprezzature-audio", "1.5.0"): ">=3.10",
}

#: The ceiling one hop further down, for a dependency whose *own* window is
#: open but whose base graph cannot avoid a capped library.
#:
#: Both of this package's capped extras are here rather than in the table
#: above, and that is the reason this second one exists instead of a fudged
#: entry in the first: the declared ``Requires-Python`` of
#: ``best-engine-ai-helper 1.4`` really is ``>=3.10``, and writing ``<3.14``
#: beside its name would be recording a reading nobody can take.
#:
#: * ``best-engine-ai-helper 1.4`` declares ``os-helper<3,>=2.3.0``, and the
#:   ceiling is unavoidable there — checked across the whole of
#:   ``os-helper``'s simple index on 2026-10-31, **not one of its releases
#:   ships without ``<3.14``**, so no resolution of that floor escapes it.
#: * ``sprezzature-audio 1.3.0`` is not a published version at all (the index
#:   has 1.1.0, 1.1.1, 1.4.0, 1.5.0), so ``>=1.3.0`` resolves to 1.4.0, whose
#:   own ``narrate`` extra names ``speaker-helper[detect,kokoro]>=0.8.0`` —
#:   and ``speaker-helper 0.8.0`` is ``>=3.10,<3.14`` on the index. Two hops,
#:   both read rather than assumed.
#:
#: Each value is ``(the dependency line that carries it, its window)``.
CAPPED_ONE_HOP_DOWN: dict[tuple[str, str], tuple[str, str]] = {
    ("best-engine-ai-helper", "1.4"): ("os-helper<3,>=2.3.0", "<3.14,>=3.10"),
    ("sprezzature-audio", "1.3.0"): (
        "speaker-helper[detect,kokoro]>=0.8.0, in 1.4.0's narrate extra",
        "<3.14,>=3.10",
    ),
}

#: The minor versions a capped dependency has to be checked against. 3.14 is
#: the one that exists and is excluded; 3.15 is here so a ceiling moving to
#: ``<3.15`` is noticed before the interpreter ships.
CANDIDATES: tuple[str, ...] = ("3.10", "3.11", "3.12", "3.13", "3.14", "3.15")


def _canonical(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _floor(spec: SpecifierSet) -> str:
    """The ``>=`` version a specifier names, or '' when it names none."""
    for clause in spec:
        if clause.operator in (">=", "==", "~="):
            return clause.version
    return ""


def _direct_requirements(extra: str, seen: set[str] | None = None) -> list[Requirement]:
    """The requirements ``pip install <this>[extra]`` reads off *this* manifest.

    Self-references are followed (``all`` is a pointer at three other lists in
    the same file) and nothing else is: the point of this guard is what the
    manifest says, and a transitive package's version is not something the
    manifest names.
    """
    seen = set() if seen is None else seen
    out: list[Requirement] = []
    for raw in EXTRAS.get(extra, []):
        req = Requirement(raw)
        if _canonical(req.name) != _canonical(DISTRIBUTION):
            out.append(req)
            continue
        for inner in sorted(req.extras):
            if inner not in seen:
                seen.add(inner)
                out.extend(_direct_requirements(inner, seen))
    return out


def excluded_versions(windows: list[str]) -> tuple[str, ...]:
    """Which of :data:`CANDIDATES` every one of ``windows`` does not admit.

    The arithmetic the assertions below rest on, kept separate so it can be
    shown literal input rather than a manifest. An empty window string means
    "declares nothing", which admits everything.
    """
    out: list[str] = []
    for version in CANDIDATES:
        for window in windows:
            if window and not SpecifierSet(window).contains(version):
                out.append(version)
                break
    return tuple(out)


def boundaries(lost: tuple[str, ...]) -> tuple[str, ...]:
    """The versions where a window closes, which is what prose names.

    ``("3.14", "3.15")`` is one edge, not two facts: a comment saying "capped
    below 3.14" has said everything, and demanding it also recite 3.15 would
    be asserting the horizon rather than the ceiling. A window closed at both
    ends — ``("3.10", "3.14", "3.15")`` — has two edges, and both have to be
    named, because a reader told only about the ceiling installs on 3.10 and
    fails anyway.
    """
    order = list(CANDIDATES)
    return tuple(
        version
        for version in lost
        if order.index(version) == 0 or order[order.index(version) - 1] not in lost
    )


def _comment_for(extra: str) -> str:
    """The contiguous block of ``#`` lines sitting directly above ``extra``.

    The artifact under test. Fragile on purpose: the thing being asserted *is*
    the prose a person reads when they open the manifest, and a comment that
    drifted away from its extra has stopped being that.
    """
    lines = PYPROJECT_TEXT.splitlines()
    pattern = re.compile(rf"^{re.escape(extra)}\s*=")
    for index, line in enumerate(lines):
        if not pattern.match(line):
            continue
        block: list[str] = []
        cursor = index - 1
        while cursor >= 0 and lines[cursor].lstrip().startswith("#"):
            block.append(lines[cursor].lstrip("# ").rstrip())
            cursor -= 1
        return "\n".join(reversed(block))
    return ""


def _capped_extras() -> dict[str, tuple[str, ...]]:
    """Every extra reaching a measured-capped floor, and the versions it loses."""
    out: dict[str, tuple[str, ...]] = {}
    for extra in EXTRAS:
        windows: list[str] = []
        for req in _direct_requirements(extra):
            key = (req.name, _floor(req.specifier))
            if key in MEASURED_AT_THEIR_FLOOR:
                windows.append(MEASURED_AT_THEIR_FLOOR[key])
            if key in CAPPED_ONE_HOP_DOWN:
                windows.append(CAPPED_ONE_HOP_DOWN[key][1])
        lost = excluded_versions(windows)
        if lost:
            out[extra] = lost
    return out


# ── The rules ──────────────────────────────────────────────────────────────


def test_the_arithmetic_on_literal_windows() -> None:
    """The comparison, shown its inputs rather than reading an environment.

    The assertion a thin environment cannot thin away, and the reason the rest
    of this file is not vacuous anywhere. Sabotage kept: drop the ``not`` from
    ``excluded_versions``' ``contains`` and this goes red first.
    """
    assert excluded_versions(["<3.14,>=3.10"]) == ("3.14", "3.15")
    assert excluded_versions([">=3.10"]) == ()
    # No declared window at all admits everything — ``nemo_toolkit 1.23.0``.
    assert excluded_versions([""]) == ()
    # A floor is an exclusion too, at the other end.
    assert excluded_versions([">=3.11"]) == ("3.10",)
    # One capped dependency in a list of clean ones is enough.
    assert excluded_versions([">=3.10", "<3.14,>=3.10", ""]) == ("3.14", "3.15")
    # The prose only has to name where a window closes, not every version
    # past it; a window closed at both ends has two edges and needs both.
    assert boundaries(("3.14", "3.15")) == ("3.14",)
    assert boundaries(("3.10", "3.14", "3.15")) == ("3.10", "3.14")
    assert boundaries(()) == ()


def test_the_measured_table_is_not_empty() -> None:
    """A table nobody filled would make every assertion below pass."""
    assert MEASURED_AT_THEIR_FLOOR, "nothing was measured, so nothing is checked"
    assert CAPPED_ONE_HOP_DOWN, "the one-hop table was emptied; re-read the index"
    # From either table: in this suite one brick carries the ceiling on its
    # declared floors and another only one hop down, and an assertion that
    # demanded the first would be false for the second rather than wrong
    # about it.
    windows = [*MEASURED_AT_THEIR_FLOOR.values(), *(w for _, w in CAPPED_ONE_HOP_DOWN.values())]
    assert any(excluded_versions([w]) for w in windows), (
        "not one measured floor carries a ceiling, by either reading, so no "
        "extra can be capped and this file has stopped testing anything. "
        "Re-read the index."
    )


@pytest.mark.parametrize(
    ("name", "version"),
    sorted(set(MEASURED_AT_THEIR_FLOOR) | set(CAPPED_ONE_HOP_DOWN), key=lambda k: k),
)
def test_a_measured_floor_is_still_the_floor_the_manifest_names(name: str, version: str) -> None:
    """The reading is of the version this manifest asks for, or it is of nothing.

    The floor moving is the way this table rots: raise ``audio-helper>=1.6.0``
    to ``>=2.0.0`` and the recorded ``<3.14`` is a reading of a version nobody
    installs any more. It may well still hold — but "probably" is what this
    whole file exists to refuse.
    """
    named = {
        (req.name, _floor(req.specifier)) for extra in EXTRAS for req in _direct_requirements(extra)
    }

    assert (name, version) in named, (
        f"MEASURED_AT_THEIR_FLOOR records {name} {version}, which no extra in "
        f"pyproject.toml names any more. Re-read "
        f"https://pypi.org/pypi/{name}/<the new floor>/json and update the "
        "table with what it says."
    )


def test_every_capped_extra_names_its_ceiling() -> None:
    """The narrowing is allowed. Shipping it unannounced is not."""
    capped = _capped_extras()
    assert capped, (
        "no extra reaches a capped floor, so this assertion checked nothing — "
        "which would be good news, and is worth confirming rather than "
        "assuming. Check MEASURED_AT_THEIR_FLOOR against the manifest."
    )

    silent: dict[str, tuple[str, ...]] = {}
    for extra, lost in sorted(capped.items()):
        comment = _comment_for(extra)
        if not all(version in comment for version in boundaries(lost)):
            silent[extra] = lost

    if silent:
        detail = "\n".join(
            f"    [{extra}] cannot be installed on "
            + ", ".join(lost)
            + " — its comment has to name "
            + ", ".join(boundaries(lost))
            for extra, lost in sorted(silent.items())
        )
        pytest.fail(
            f"{DISTRIBUTION} promises requires-python = "
            f"{PROJECT['requires-python']!r}, and these extras quietly do not "
            "keep it:\n" + detail + "\n  Say it in the comment directly above "
            "each one in pyproject.toml. The base install is unaffected, which "
            "is exactly why nothing else would ever catch this."
        )
