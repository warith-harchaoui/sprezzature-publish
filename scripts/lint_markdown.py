#!/usr/bin/env python3
"""
lint_markdown
=============

Static + AI-assisted linter for Markdown files emitted or shipped by the
sprezzature skill. Three jobs:

1. **Static rules.** Deterministic checks over the Markdown source —
   heading-level skips, trailing whitespace, code blocks without a
   language hint, image without alt text, link to a missing local path.
2. **Mermaid blocks.** Nothing here draws them. Each one is reported as
   ``MMD001``, which says to draw the diagram with
   ``sprezzature-figures render flowchart`` and embed the SVG.
3. **LaTeX blocks.** Validate ``$$ … $$`` display blocks and
   ``\\begin{align} … \\end{align}`` environments — delimiter balance,
   multi-line alignment with ``&`` separators, and the common pitfall of
   leaving a single backslash where ``\\\\`` is required for a line break.

AI-assisted suggestions (optional). When ``--ai`` is set and a local
Ollama daemon is reachable, the script asks the default model for
captions for LaTeX blocks (a sentence-long description for screen-reader
users).

The AI step **never** mutates the source. It prints suggestions; you
apply them by hand. The deterministic rules can rewrite (``--fix``)
trailing whitespace; nothing else.

Usage
-----
::

    sprezzature-publish-lint docs/intro.md
    sprezzature-publish-lint docs/                   # walks the dir
    sprezzature-publish-lint --fix docs/             # apply safe rewrites
    sprezzature-publish-lint --ai docs/intro.md      # add Ollama suggestions

Exit code
---------
* 0 — no errors.
* 1 — one or more errors. Warnings do not affect the exit code.

Notes
-----
* Python 3.10+, click and the standard library only for the static rules.
* Cross-platform. On Windows the LaTeX delimiter parser is the same.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _click import run_command, sprezzature_command  # noqa: E402

# ── Severity levels ────────────────────────────────────────────────────────

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass
class Finding:
    """One lint finding: file path, 1-indexed line, rule id, severity, and message."""

    path: Path
    line: int  # 1-indexed
    rule: str  # short id e.g. "MD001"
    severity: str  # ERROR / WARNING / INFO
    message: str


# ── Block extractors (stdlib regex) ────────────────────────────────────────

FENCE_RE = re.compile(r"^(```+|~~~+)([^\n]*)\n(.*?)\n\1\s*$", re.DOTALL | re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
IMG_RE = re.compile(r"!\[(.*?)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
LINK_RE = re.compile(r"(?<!!)\[(.*?)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
DISPLAY_MATH_RE = re.compile(r"^\$\$\n(.*?)\n\$\$\s*$", re.DOTALL | re.MULTILINE)
ALIGN_ENV_RE = re.compile(r"\\begin\{(align\*?|aligned|gather\*?)\}(.*?)\\end\{\1\}", re.DOTALL)


def fenced_blocks(text: str) -> list[tuple[int, str, str]]:
    """Yield (start_line_1_indexed, language, body) for every fenced block."""
    out: list[tuple[int, str, str]] = []
    for m in FENCE_RE.finditer(text):
        lang = m.group(2).strip()
        body = m.group(3)
        start_line = text[: m.start()].count("\n") + 1
        out.append((start_line, lang, body))
    return out


# ── Static rules ──────────────────────────────────────────────────────────


def lint_heading_order(path: Path, text: str) -> list[Finding]:
    """MD001 — heading levels must not skip (h1 → h3 is wrong)."""
    findings: list[Finding] = []
    last_level: int = 0
    prose = _strip_code(text)
    for m in HEADING_RE.finditer(prose):
        level = len(m.group(1))
        if last_level and level > last_level + 1:
            line = text[: m.start()].count("\n") + 1
            findings.append(
                Finding(
                    path,
                    line,
                    "MD001",
                    ERROR,
                    f"Heading level jumps from h{last_level} to h{level}.",
                )
            )
        last_level = level
    return findings


def lint_trailing_whitespace(path: Path, text: str) -> list[Finding]:
    """MD009 — no trailing spaces (except the intentional two-space line break)."""
    findings: list[Finding] = []
    for i, line in enumerate(text.splitlines(), 1):
        rstripped = line.rstrip(" \t")
        if rstripped != line and not line.endswith("  "):  # `  ` = MD line break
            findings.append(
                Finding(
                    path,
                    i,
                    "MD009",
                    WARNING,
                    "Trailing whitespace (use two spaces only for an intentional line break).",
                )
            )
    return findings


def lint_fenced_code_language(path: Path, text: str) -> list[Finding]:
    """MD040 — every fenced code block declares a language."""
    findings: list[Finding] = []
    for start_line, lang, _body in fenced_blocks(text):
        if not lang:
            findings.append(
                Finding(
                    path,
                    start_line,
                    "MD040",
                    WARNING,
                    "Fenced code block missing language hint (use ```bash, ```python, ```text, …).",
                )
            )
    return findings


#: What to do about a Mermaid block. One sentence in one place, because the
#: lint reports it and the converter repeats it.
MERMAID_ADVICE = "draw the diagram with `sprezzature-figures render flowchart` and embed the SVG"


def is_mermaid_fence(lang: str) -> bool:
    """Whether a fence's info string names Mermaid, in any case, with or without attributes."""
    return re.match(r"\{?\s*\.?mermaid(?![\w-])", lang, re.IGNORECASE) is not None


def lint_mermaid_blocks(path: Path, text: str) -> list[Finding]:
    """MMD001 — a Mermaid block is neither drawn here nor passed over in silence."""
    return [
        Finding(path, start_line, "MMD001", WARNING, f"Mermaid block: {MERMAID_ADVICE}.")
        for start_line, lang, _body in fenced_blocks(text)
        if is_mermaid_fence(lang)
    ]


def lint_image_alt(path: Path, text: str) -> list[Finding]:
    """MD045 — images need alt text (or explicit empty `![]()` for decorative)."""
    findings: list[Finding] = []
    for m in IMG_RE.finditer(text):
        alt = m.group(1).strip()
        if alt == "":
            # Empty alt is *valid* for decorative images, but tag it as INFO so the
            # author confirms it intentionally. See alt-text-ai.md in sprezzature-accessibility.
            line = text[: m.start()].count("\n") + 1
            findings.append(
                Finding(
                    path,
                    line,
                    "MD045",
                    INFO,
                    "Empty alt text — confirm this image is decorative (otherwise add an alt).",
                )
            )
    return findings


# ── Auto-fix helpers ─────────────────────────────────────────────────────


def fix_trailing_whitespace(text: str) -> str:
    """
    Strip trailing spaces / tabs on every line, preserving the
    intentional two-space line-break suffix (MD009).

    Idempotent. The Markdown spec treats a line ending in ``"  "``
    (two spaces) as an explicit ``<br>``; we keep that. Any other
    trailing whitespace — single spaces, three-or-more spaces, tab
    characters — is collapsed.

    Parameters
    ----------
    text : str
        Source Markdown.

    Returns
    -------
    str
        New Markdown with offending trailing whitespace removed. The
        document's line count is preserved (a fully-blank line of
        spaces becomes an empty line, not a removed line).
    """
    out_lines: list[str] = []
    for line in text.splitlines():
        if line.endswith("  ") and not line.endswith("   "):
            # Exactly two trailing spaces — Markdown's intentional
            # line break. Preserve.
            out_lines.append(line)
            continue
        out_lines.append(line.rstrip(" \t"))
    new: str = "\n".join(out_lines)
    # ``splitlines`` drops the trailing newline; restore it if the
    # original had one so the file does not gain / lose a final EOL.
    if text.endswith("\n"):
        new += "\n"
    return new


def lint_local_links(path: Path, text: str) -> list[Finding]:
    """MD050 — local link targets exist on disk.

    Scans a code-stripped view of the document so link *syntax examples* inside
    fenced blocks or inline-code spans (e.g. documenting ``[text](url)`` in a
    table cell) are not mistaken for real links. ``_strip_code`` preserves line
    breaks, so reported line numbers stay accurate.
    """
    findings: list[Finding] = []
    parent = path.parent
    prose = _strip_code(text)
    for m in LINK_RE.finditer(prose):
        href = m.group(2)
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        # Strip anchor and query.
        rel = href.split("#", 1)[0].split("?", 1)[0]
        if not rel:
            continue
        target = (parent / rel).resolve()
        if not target.exists():
            line = text[: m.start()].count("\n") + 1
            findings.append(
                Finding(
                    path,
                    line,
                    "MD050",
                    ERROR,
                    f"Local link target does not exist: {href}",
                )
            )
    return findings


# ── LaTeX checks ──────────────────────────────────────────────────────────


def _strip_code(text: str) -> str:
    """
    Remove fenced blocks and inline-code spans before scanning for prose-level
    markers like `$$` or backtick math. Preserves line breaks so reported line
    numbers stay accurate.
    """

    # Blank out fenced blocks but keep their newlines.
    def blank_fence(m: re.Match[str]) -> str:
        """Replace a fenced block with equal-count newlines to preserve line numbers."""
        return "\n" * m.group(0).count("\n")

    no_fence = FENCE_RE.sub(blank_fence, text)
    # Blank out inline-code spans.
    return re.sub(r"`+[^`\n]*`+", lambda m: " " * len(m.group(0)), no_fence)


def lint_latex_blocks(path: Path, text: str) -> list[Finding]:
    """MDX001 — LaTeX display blocks: balanced delimiters and multi-line hygiene."""
    findings: list[Finding] = []
    prose = _strip_code(text)

    # 1) Stray $$ not paired (count must be even).
    dollar_dollar = re.findall(r"(?<!\\)\$\$", prose)
    if len(dollar_dollar) % 2 != 0:
        findings.append(
            Finding(
                path,
                1,
                "MDX001",
                ERROR,
                f"Odd number of `$$` delimiters ({len(dollar_dollar)}); display math is unbalanced.",
            )
        )

    # 2) Within each $$…$$ block, multi-line formulas should be inside
    #    an alignment env (align, aligned, gather) and use `\\` for line breaks.
    for m in DISPLAY_MATH_RE.finditer(prose):
        body = m.group(1)
        start_line = text[: m.start()].count("\n") + 1
        body_lines = [ln for ln in body.splitlines() if ln.strip()]
        if len(body_lines) > 1:
            uses_env = any(
                env in body for env in ("\\begin{align", "\\begin{aligned", "\\begin{gather")
            )
            uses_double_backslash = re.search(r"(?<!\\)\\\\(?!\\)", body) is not None
            if not uses_env and not uses_double_backslash:
                findings.append(
                    Finding(
                        path,
                        start_line,
                        "MDX002",
                        WARNING,
                        "Multi-line display math without `\\\\` line breaks or an `align`/`gather` "
                        "environment. Most renderers will collapse the lines.",
                    )
                )

    # 3) Inside align/aligned/gather, each non-trailing line should end with `\\`.
    for m in ALIGN_ENV_RE.finditer(prose):
        env = m.group(1)
        body = m.group(2)
        start_line = text[: m.start()].count("\n") + 1
        lines = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
        # Drop the last line (no `\\` expected) and check the rest.
        for idx, ln in enumerate(lines[:-1]):
            if not ln.endswith("\\\\"):
                findings.append(
                    Finding(
                        path,
                        start_line + idx + 1,
                        "MDX003",
                        ERROR,
                        f"`\\begin{{{env}}}` block: line {idx + 1} missing `\\\\` line break.",
                    )
                )

    return findings


# ── Optional Ollama-assisted suggestions ──────────────────────────────────

# These imports are deferred — the script must run without the prompt
# templates or `_ollama.py` available (those are needed only with --ai).
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _ollama import ollama_engine, pick_default_model  # type: ignore
    from _prompts import render as render_prompt  # type: ignore

    HAVE_AI = True
except ImportError:
    HAVE_AI = False


# Prompts live in scripts/prompts/*.yaml — see _prompts.py for loader.
# Each prompt is zero-shot with a strict output contract; the parser
# returns an empty result when the model drifts off-contract.


def _ask(prompt: str, model: str) -> str:
    """One call to the local model, through best-engine-ai-helper like every other.

    This was the one tool in the package that posted to Ollama's HTTP API
    itself: the same server, but outside the routing every other call takes.
    """
    from best_engine_ai_helper.llm import chat

    return str(chat(prompt, model=model, engine=ollama_engine(model))).strip()


def ai_caption_latex(latex_src: str, lang: str, model: str) -> str | None:
    """Ask the local LLM for a plain-language caption of a LaTeX block; ``None`` if unavailable."""
    if not HAVE_AI:
        return None
    prompt = render_prompt(
        "latex_caption",
        prompts_dir=Path(__file__).resolve().parent / "prompts",
        latex_src=latex_src,
        lang=lang,
    )
    try:
        return _ask(prompt, model).strip('"').strip()
    except Exception:  # pylint: disable=broad-except
        return None


# ── Driver ────────────────────────────────────────────────────────────────

STATIC_RULES = (
    lint_heading_order,
    lint_trailing_whitespace,
    lint_fenced_code_language,
    lint_image_alt,
    lint_local_links,
    lint_latex_blocks,
    lint_mermaid_blocks,
)


def lint_file(
    path: Path,
    *,
    fix: bool = False,
    ai: bool = False,
    ai_lang: str = "en",
    ai_model: str = "",
) -> tuple[list[Finding], list[str]]:
    """Lint one Markdown file. Returns (findings, ai_notes)."""
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return (
            [Finding(path, 1, "MD000", WARNING, f"Skipped — not valid UTF-8: {exc}")],
            [],
        )
    findings: list[Finding] = []
    for rule in STATIC_RULES:
        findings.extend(rule(path, text))

    # MD009 trailing-whitespace strip — only when ``--fix`` is set.
    # Idempotent; preserves the intentional two-space line break.
    if fix:
        new_text = fix_trailing_whitespace(text)
        if new_text != text:
            path.write_text(new_text, encoding="utf-8")
            text = new_text

    ai_notes: list[str] = []
    if ai:
        if not HAVE_AI:
            ai_notes.append(
                "(--ai requested but `_ollama.py` or the prompts are not importable; skipped)"
            )
        else:
            model = ai_model or pick_default_model()
            # LaTeX captions.
            for m in DISPLAY_MATH_RE.finditer(text):
                latex = m.group(1).strip()
                cap = ai_caption_latex(latex, ai_lang, model)
                if cap:
                    ai_notes.append(f"[latex] caption ({ai_lang}): {cap}")

    return findings, ai_notes


DEFAULT_EXCLUDE_DIRS = frozenset(
    {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "dist",
        "build",
        ".deepeval",
        ".private",
        "4ml",
    }
)


def gather_targets(target: Path) -> list[Path]:
    """Walk target. Skip vendor dirs (node_modules, .git, …) by default."""
    if target.is_file():
        return [target]
    out: list[Path] = []
    suffixes = {".md", ".markdown"}
    for p in target.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in suffixes:
            continue
        if any(part in DEFAULT_EXCLUDE_DIRS for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


@sprezzature_command(
    "sprezzature-publish-lint",
    help="Lint Markdown — heading order, code-fence languages, image alt, "
    "local links and LaTeX delimiter balance. Reports each Mermaid block "
    "(MMD001). Optionally asks Ollama for LaTeX caption suggestions.",
    epilog=(
        "\b\n"
        "Examples:\n"
        "  sprezzature-publish-lint docs/intro.md\n"
        "  sprezzature-publish-lint --fix docs/\n"
        "  sprezzature-publish-lint --fix --ai --ai-lang en docs/\n"
    ),
)
@click.argument("target", type=click.Path(path_type=Path))
@click.option(
    "--format",
    "format",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format. Default: text.",
)
@click.option(
    "--fix",
    is_flag=True,
    help="Apply safe mechanical fixes in place: MD009 strip trailing "
    "whitespace (preserves the intentional two-space line break). "
    "Idempotent. Never invents content.",
)
@click.option(
    "--ai",
    is_flag=True,
    help="Ask the local Ollama daemon for LaTeX captions. Read-only — never mutates the source.",
)
@click.option(
    "--ai-lang",
    "ai_lang",
    default="en",
    help="Language of the document, used for LaTeX captions. Default: en.",
)
@click.option(
    "--ai-model",
    "ai_model",
    default="",
    help="Override the Ollama model tag. Default: qwen3-vl:8b.",
)
def _cli(**options: Any) -> int:
    """Click command body: the flags arrive as keywords, the work is :func:`_run`."""
    return _run(SimpleNamespace(**options))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the Markdown linter; returns a process exit code."""
    return run_command(_cli, argv)


def _run(args: SimpleNamespace) -> int:
    """Lint every target the parsed flags name; return the process exit code."""

    targets = gather_targets(args.target)
    if not targets:
        print(f"sprezzature-lint-md: no Markdown files under {args.target}", file=sys.stderr)
        return 2

    all_findings: list[Finding] = []
    all_ai_notes: list[tuple[Path, list[str]]] = []
    for path in targets:
        findings, notes = lint_file(
            path,
            fix=args.fix,
            ai=args.ai,
            ai_lang=args.ai_lang,
            ai_model=args.ai_model,
        )
        all_findings.extend(findings)
        if notes:
            all_ai_notes.append((path, notes))

    if args.format == "json":
        print(
            json.dumps(
                [
                    {
                        "path": str(f.path),
                        "line": f.line,
                        "rule": f.rule,
                        "severity": f.severity,
                        "message": f.message,
                    }
                    for f in all_findings
                ],
                indent=2,
            )
        )
    else:
        for f in all_findings:
            print(f"{f.path}:{f.line}: {f.severity}: {f.rule}: {f.message}")
        if all_ai_notes:
            print("\n— AI suggestions (informational, never auto-applied) —")
            for path, notes in all_ai_notes:
                print(f"# {path}")
                for n in notes:
                    print(f"  {n}")

    errors = [f for f in all_findings if f.severity == ERROR]
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
