#!/usr/bin/env python3
"""
plain_language
==============

Rewrite UI copy at a target reading level using the local Ollama model
already used by :mod:`alt_from_ollama`. Meaning is preserved; jargon and
marketing voice are removed.

Cognitive accessibility (WCAG 2.4.5, Understanding 3.1.5, Reading Level)
is the criterion almost everyone skips because the rewrite is tedious.
The model is good at this and runs locally; the rewrite is free past the
fixed cost of a model pull.

Behavior
--------
* Reads input from stdin OR a file (``--input``); writes the rewrite to stdout.
* Honors ``--lang`` (default: detected from the text), so French
  in goes French out.
* Honors ``--target-grade`` (default ``8``) — a hint to the prompt, not a
  hard contract. Output is checked for length; the model is asked again
  in shorter form if it overshoots.
* ``--preserve "Brand,Product"`` lists tokens the rewriter must keep
  verbatim (proper nouns, code identifiers, API names).
* Output is cached on disk so the same input never hits the model twice;
  cache key includes target grade, language, preserve list, and model.
  "Never twice" now also covers *at the same time*: the cache is a
  `wallet-helper`_ ledger (see :mod:`_wallet`), so two runs that ask for the
  same sentence at the same moment make one model call and the second waits
  on the first. Before that, three concurrent runs asking for one sentence
  came back with three different rewrites of it — 126, 100 and 96 characters
  — and the one kept was whichever process wrote last.

Usage
-----
::

    # Pipe in a single string
    echo "Boost your productivity with our state-of-the-art platform" \\
        | python plain_language.py --target-grade 8 --lang en

    # Read from a file, write to another
    python plain_language.py --input src/copy.md > dist/copy.simple.md

    # Keep brand names intact
    python plain_language.py --preserve "Sprezzature,Tailwind,Montserrat" --input copy.md

    # Bypass the cache for this run
    python plain_language.py --no-cache --input copy.md

Notes
-----
* Python 3.10+, ``requests`` (shared with :mod:`alt_from_ollama`).
* Cache: ``~/.cache/sprezzature-skill/plain/`` — override with ``SPREZZATURE_CACHE_DIR``;
  disable with ``SPREZZATURE_NO_CACHE=1`` or ``--no-cache``.
* The rewriter refuses to invent facts. If the input is already plain
  language, the model returns it unchanged.

.. _wallet-helper: https://github.com/warith-harchaoui/wallet-helper

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import click
from _click import run_command, sprezzature_command  # noqa: E402

# Every LLM/VLM call across sprezzature-* routes through this one function —
# no script imports an Ollama/OpenAI/LangChain client directly. It resolves
# the backend and model tag from the SPREZZATURE_LLM_* environment variables
# (SPREZZATURE_LLM_BACKEND defaults to "ollama"); the `model` argument passed
# at each call site below is a per-call override on top of that.
try:
    from best_engine_ai_helper.llm import chat as _llm_chat
except ImportError as _exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "this tool asks a local model through best-engine-ai-helper, a base dependency, so this install is broken: "
        "pip install 'sprezzature-publish'"
    ) from _exc

# Shared Ollama helpers live in _ollama.py inside this skill folder so
# the script does not need a cross-skill import after the 0.2.0 split.
sys.path.insert(0, str(Path(__file__).parent))
from _lang import detect_text_language  # noqa: E402
from _ollama import (  # noqa: E402
    LANG_INSTRUCTIONS,
    OLLAMA_URL,
    detect_lang,
    ollama_engine,
    pick_default_model,
)
from _wallet import memoized  # noqa: E402

# ── Module-level configuration ────────────────────────────────────────────────

#: Maximum factor by which the rewrite may grow compared to the source.
#: 1.1 keeps the output approximately the same length; longer rewrites are
#: re-asked with a tighter constraint.
MAX_LENGTH_FACTOR: float = 1.1

#: Cache directory for the rewriter. Override with ``SPREZZATURE_CACHE_DIR``.
CACHE_DIR: Path = (
    Path(
        os.environ.get("SPREZZATURE_CACHE_DIR")
        or os.environ.get("FRONT_CACHE_DIR")
        or Path.home() / ".cache" / "sprezzature-skill"
    )
    / "plain"
)

#: Cache toggle, mirroring the other Ollama helpers.
NO_CACHE: bool = bool(os.environ.get("SPREZZATURE_NO_CACHE") or os.environ.get("FRONT_NO_CACHE"))


# ── Cache helpers ────────────────────────────────────────────────────────────


def _cache_key(text: str, grade: int, lang: str, preserve: list[str], model: str) -> str:
    """
    Compute a 32-character cache key from the inputs that affect the output.

    Parameters
    ----------
    text : str
        Source text to rewrite.
    grade : int
        Target reading grade level.
    lang : str
        Two-letter language code.
    preserve : list of str
        Tokens the rewriter must keep verbatim. Sorted for stability.
    model : str
        Ollama model tag.

    Returns
    -------
    str
        32 hex characters suitable as a filename stem.
    """
    h = hashlib.sha256()
    # ``\x00`` separators avoid ambiguity when an input contains a delimiter.
    h.update(f"{text}\x00{grade}\x00{lang}\x00".encode())
    h.update("\x01".join(sorted(preserve)).encode("utf-8"))
    h.update(f"\x00{model}".encode())
    return h.hexdigest()[:32]


# The read/write pair is gone; :func:`_cache_key` above is what remains of it,
# unchanged, because the key was never the part that was wrong. What the pair
# could not do is stop two processes from both deciding the entry was missing:
# three of them, started together, made three model calls 0.2 ms apart and got
# three different rewrites of one sentence. :mod:`_wallet` puts the model call
# inside a claim so the second and third wait for the first instead.


# ── Prompt construction ─────────────────────────────────────────────────────
#
# The prompt body lives in scripts/prompts/plain_language_rewrite.yaml.
# This function only assembles the dynamic prefix (language line) and
# the optional `preserve_line` clause before delegating to the loader.

# Deferred import — keep the prompt loader optional so that this script
# can still load without PyYAML when callers only need the non-prompt
# helpers (e.g. `LANG_INSTRUCTIONS`, `detect_text_language`).
try:
    from _prompts import render as render_prompt  # type: ignore

    HAVE_PROMPTS = True
except ImportError:
    HAVE_PROMPTS = False


def build_prompt(text: str, grade: int, lang: str, preserve: list[str]) -> str:
    """
    Build the prompt sent to the model.

    Parameters
    ----------
    text : str
        Source text.
    grade : int
        Target reading grade level (typically 6–10).
    lang : str
        Target language code (must match the source's language).
    preserve : list of str
        Tokens to keep verbatim.

    Returns
    -------
    str
        The full prompt, ready to send to Ollama.
    """
    # The language line commits the model to a single language early.
    lang_line: str = LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS["en"])

    preserve_line: str = ""
    if preserve:
        preserve_line = (
            f"Keep these tokens verbatim (do not translate, do not paraphrase): "
            f"{', '.join(preserve)}.\n"
        )

    if not HAVE_PROMPTS:
        # Fallback when _prompts is not importable. Should be unreachable
        # in practice since this script and _prompts.py ship together.
        return (
            f"{lang_line} Rewrite at grade {grade}. Preserve meaning. "
            f"{preserve_line}--- TEXT ---\n{text}\n--- END ---"
        )

    return render_prompt(
        "plain_language_rewrite",
        prompts_dir=Path(__file__).resolve().parent / "prompts",
        lang_line=lang_line,
        grade=grade,
        preserve_line=preserve_line,
        text=text,
    )


# ── Public API ──────────────────────────────────────────────────────────────


def rewrite(
    text: str,
    *,
    target_grade: int = 8,
    lang: str | None = None,
    preserve: list[str] | None = None,
    model: str | None = None,
) -> str:
    """
    Rewrite ``text`` at the requested reading grade level.

    Parameters
    ----------
    text : str
        Source text. Empty / whitespace-only inputs round-trip unchanged.
    target_grade : int, optional
        Target reading-level hint, default ``8``.
    lang : str or None, optional
        BCP-47 base tag. When ``None`` (default), detected from the
        environment via :func:`detect_lang`.
    preserve : list of str or None, optional
        Tokens the model must keep verbatim (brand names, identifiers).
    model : str or None, optional
        Ollama model tag to use. ``None`` takes the one model,
        ``qwen3-vl:8b``, from :func:`pick_default_model`.

    Returns
    -------
    str
        The rewritten text, with surrounding whitespace stripped.

    Raises
    ------
    SystemExit
        With code ``2`` when Ollama is unreachable.

    Examples
    --------
    >>> rewrite("Boost your productivity")              # doctest: +SKIP
    'Get more done.'
    """
    if not text.strip():
        # Trivial round-trip — no need to spin up the model.
        return text

    # Language: explicit ``lang`` wins. Otherwise ALWAYS detect from the
    # input text itself (the rewrite must stay in the source language) via
    # langdetect — no configured default; env/locale is only the floor.
    if lang is None:
        lang = detect_text_language(text, fallback=detect_lang())
    lang = lang.lower()[:2]
    preserve = preserve or []
    model = model or pick_default_model()

    key = _cache_key(text, target_grade, lang, preserve, model)

    # Both model calls — the rewrite and the one retry — live inside the
    # closure, because that is the whole point: a single-flight that the heavy
    # work sits *outside* of has nothing for the second caller to wait on, and
    # the length retry is a second trip to the model, not an afterthought.
    def ask_the_model() -> str:
        """Rewrite ``text`` through the model, retrying once if it overshoots."""
        prompt = build_prompt(text, target_grade, lang, preserve)
        try:
            out: str = str(_llm_chat(prompt, model=model, engine=ollama_engine(model))).strip()
        except RuntimeError as e:
            # best_engine_ai_helper.llm.chat wraps both connection failures and
            # HTTP error responses into RuntimeError (not requests.exceptions.*)
            # regardless of backend, so both cases are one except clause now.
            sys.stderr.write(
                f"Cannot reach Ollama at {OLLAMA_URL}, or it returned an error: {e}\n"
                f"Start it with `ollama serve`, then `ollama pull {model}`.\n"
            )
            sys.exit(2)

        # Length sanity check — if the model overshot, re-ask once with a tighter
        # instruction. We do not loop; one retry is the right balance between
        # correctness and predictable latency.
        if len(out) > len(text) * MAX_LENGTH_FACTOR:
            tighter: str = prompt + (
                f"\nThe previous rewrite was too long. "
                f"Keep it to AT MOST {int(len(text) * MAX_LENGTH_FACTOR)} characters.\n"
            )
            try:
                out = str(_llm_chat(tighter, model=model, engine=ollama_engine(model))).strip()
            except RuntimeError:
                # If the retry fails, keep the over-long rewrite — it is still
                # better than the original marketing copy in most cases.
                pass
        return out

    result: str = memoized(
        "plain",
        key,
        ask_the_model,
        cache_dir=CACHE_DIR,
        enabled=not NO_CACHE,
    )
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────


@sprezzature_command(
    "sprezzature-publish-plain",
    help=(
        "Rewrite UI copy at a target reading level via a local Ollama "
        "model. Preserves meaning, strips marketing voice; output length "
        "≤ 1.1× original."
    ),
    epilog=(
        "Examples:\n"
        "  cat draft.md | sprezzature-publish-plain --target-grade 8 --lang en\n"
        "  sprezzature-publish-plain --input copy.md --preserve 'Sprezzature,Tailwind' > out.md\n"
    ),
)
@click.option(
    "--input",
    "-i",
    "input_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Read from this file instead of stdin.",
)
@click.option(
    "--target-grade",
    "-g",
    "target_grade",
    type=int,
    default=8,
    show_default=True,
    help="Reading grade level.",
)
@click.option(
    "--lang",
    "-l",
    default=None,
    help="BCP-47 base tag (en, fr, es, …). Default: detected from the text, the locale as fallback.",
)
@click.option(
    "--preserve",
    default="",
    help="Comma-separated tokens to keep verbatim (brand names, identifiers).",
)
@click.option(
    "--no-cache",
    "no_cache",
    is_flag=True,
    default=False,
    help="Bypass the on-disk cache for this run.",
)
def _cli(
    input_path: Path | None,
    target_grade: int,
    lang: str | None,
    preserve: str,
    no_cache: bool,
) -> int:
    """Click command body for ``plain_language``; returns an int exit code.

    Behaviour is identical to the prior argparse-driven ``main``: reads
    from ``--input`` or stdin, writes the rewrite to stdout, and exits ``1``
    when invoked with neither a file nor a pipe.
    """
    global NO_CACHE
    if no_cache:
        NO_CACHE = True

    # Read the source either from a file or from stdin so the tool slots
    # cleanly into pipelines (`cat copy.md | plain_language.py`).
    if input_path:
        text: str = input_path.read_text(encoding="utf-8")
    else:
        if sys.stdin.isatty():
            click.echo(
                "No input. Pass --input <file> or pipe text to stdin.",
                err=True,
            )
            return 1
        text = sys.stdin.read()

    preserve_list: list[str] = [t.strip() for t in preserve.split(",") if t.strip()]

    # The model is fixed (qwen3-vl:8b); ``rewrite`` resolves it via
    # ``pick_default_model`` — not user-selectable.
    out = rewrite(
        text,
        target_grade=target_grade,
        lang=lang,
        preserve=preserve_list,
    )

    sys.stdout.write(out)
    if not out.endswith("\n"):
        sys.stdout.write("\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    """
    CLI entry point.

    Returns
    -------
    int
        Process exit code. ``0`` on success; the script delegates other
        codes to the underlying helpers (``2`` for connectivity issues).
    """
    return run_command(_cli, argv)


if __name__ == "__main__":
    sys.exit(main())
