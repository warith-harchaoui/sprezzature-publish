#!/usr/bin/env python3
"""
sprezzature-publish-narrate
============

Generate an audio narration of a Markdown post (blog article, doc page,
essay) using a local OSS text-to-speech engine. Output is **optional
editorial enhancement** — pre-recorded audio of long-form text is
*not* a WCAG 2.x requirement (screen readers already cover that case).
The use cases are: multitasking audience, podcast positioning, and
cognitive-accessibility "alternative format" (WAI-COGA direction).

Pipeline
--------
1. ``_narrate.extract_segments`` parses the Markdown into a list of
   structured segments (heading, paragraph, list item, blockquote).
   Each segment carries baseline narration hints derived from the
   Markdown structure (pause lengths, emotion from leading emoji,
   pace from frontmatter ``narration.tone``).
2. ``_narrate.load_pronunciation`` / ``apply_pronunciation_text``
   adjust what is *spoken* so brand names / acronyms are pronounced
   correctly; the cue text keeps the page's words.
3. **Optional** ``--ai-hints`` calls a local Ollama vision-or-text
   model per segment and enriches the hints with semantic context
   the structure alone cannot see (sarcasm, build-up before a
   punchline, pacing). Defaults to off — the deterministic
   structural path stays the baseline.
4. The chosen engine wrapper (``narrate_kokoro.py`` by default, or
   ``narrate_kyutai.py`` / ``narrate_openvoice.py`` /
   ``narrate_chatterbox.py``) runs as a
   subprocess and synthesises one WAV per segment, then concatenates
   with the requested pauses.
5. A manifest entry is written to ``out/audio/manifest.json``
   recording source path, audio path, engine, voice, language, the
   voice that actually spoke, sha256, and measured duration, so
   subsequent runs short-circuit on unchanged posts. The language is
   in the key as well as in the row: it picks the voice, so the same
   text under a different language is a different recording.

Usage
-----
::

    # Default engine (kokoro): the language of the whole text, detected
    # once, picks the voice that reads all of it
    python3 sprezzature-publish/scripts/sprezzature-publish-narrate.py posts/hello.md

    # A page that quotes another language at length, where detection would
    # answer with the quotes rather than with the page
    python3 sprezzature-publish/scripts/sprezzature-publish-narrate.py \
        --lang fr posts/lettre.md

    # ChatterboxTTS with a custom voice sample (designer's own voice)
    python3 sprezzature-publish/scripts/sprezzature-publish-narrate.py \\
        --engine chatterbox \\
        --voice-sample voices/me.wav \\
        posts/hello.md

    # Enrich segment hints via local Ollama (qwen3-vl:8b, the one model)
    python3 sprezzature-publish/scripts/sprezzature-publish-narrate.py \\
        --engine openvoice --voice base-en-default \\
        --ai-hints \\
        posts/hello.md

    # Debug: just print the (enriched) hints, do not call the engine
    python3 sprezzature-publish/scripts/sprezzature-publish-narrate.py \\
        --ai-hints --ai-hints-only posts/hello.md

Requirements
------------
* Python 3.10+; PyYAML is optional (pronunciation override + frontmatter
  parsing degrade silently when missing).
* One of the engine wrappers installed. They live in sprezzature-audio,
  which owns the sound modality in both directions:
  - ``pip install 'sprezzature-audio[narrate-kokoro]'``
  - ``pip install 'sprezzature-audio[narrate-kyutai]'``
  - ``pip install 'sprezzature-audio[narrate-openvoice]'``
  - ``pip install 'sprezzature-audio[narrate-chatterbox]'``
* A running Ollama daemon if ``--ai-hints`` is passed (the same
  daemon ``alt_from_ollama.py`` and ``meta_from_ollama.py`` use).

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def _llm_chat(*args: Any, **kwargs: Any) -> Any:
    """The one LLM call this tool makes, imported at the moment it is made.

    Every LLM/VLM call across sprezzature-* routes through this one function
    — no script imports an Ollama/OpenAI/LangChain client directly. It
    resolves the backend and model tag from the SPREZZATURE_LLM_*
    environment variables (SPREZZATURE_LLM_BACKEND defaults to "ollama");
    the `model` argument at the call site is a per-call override on top.

    Deferred rather than imported at module level, which is how it was
    written and which made the whole command depend on an extra it uses only
    when asked to. `--ai-hints` is off by default: the structural path is the
    baseline and the model only ever enriches it. But the import ran
    regardless, so `pip install 'sprezzature-publish[narrate]'` — the extra
    whose entire purpose is this command — produced a command that exited on
    `--help` with a message about a *different* extra. The one shape of
    install the feature is named after was the one that could not run it.
    """
    try:
        from best_engine_ai_helper.llm import chat
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise SystemExit(
            "--ai-hints asks a local model, which is the [prose] extra: "
            "pip install 'sprezzature-publish[prose]'. Without it the "
            "narration still works — the structural hints are the baseline."
        ) from exc
    return chat(*args, **kwargs)


# Local helpers — pure-Python, no heavy ML deps.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _readalong  # noqa: E402
from _lang import detect_text_language  # noqa: E402
from _narrate import (  # noqa: E402
    LLM_SYSTEM_PROMPT,
    NarrationManifestEntry,
    Segment,
    apply_pronunciation_text,
    explode_to_sentences,
    extract_segments,
    load_pronunciation,
    merge_llm_hint,
    read_manifest,
    segments_from_blocks,
    segments_to_text,
    source_sha256,
    write_manifest,
)
from _prompts import render as render_prompt  # noqa: E402
from _speech_text import MathNarrator, speakable  # noqa: E402

# ── Module-level configuration ──────────────────────────────────────────────

#: Suffixes read as HTML rather than Markdown. A page already rendered has
#: its structure in its elements, so it needs no Markdown twin to be narrated.
HTML_SUFFIXES: frozenset[str] = frozenset({".html", ".htm", ".xhtml", ".php"})

#: Engines we know how to dispatch to, best first. The wrappers ship in
#: sprezzature-audio and are invoked as subprocesses so their heavy ML
#: imports never leak into the orchestrator's import graph.
#:
#: `kokoro` leads because it is the one that answers the question this tool
#: asks — "this article should have a voice". It is 82 M parameters,
#: Apache-2.0 in code *and* weights, runs on ONNX Runtime with no torch at
#: all, carries 54 voices across nine languages, and needs nothing recorded.
#:
#: `kyutai` arrived with speaker-helper 0.11 (2026-10-26) and is the French
#: answer: a Paris lab's `tts-1.6b-en_fr`, which renders French natively where
#: all three others reach it through an English-first pipeline. It is not the
#: default, and the reason is the line above — its code is MIT and its weights
#: are CC-BY-4.0, which is permissive but is not "Apache-2.0 in code *and*
#: weights". Ask for it by name on a French page and it is the better voice;
#: nobody gets a different licence by surprise.
#:
#: `openvoice` and `chatterbox` are voice-*cloning* engines: they want a
#: reference clip and a multi-gigabyte ML stack, which is the right trade only
#: when the point is to sound like a particular person.
#:
#: Note what this list is NOT. speaker-helper 0.11 ships a router that ranks
#: engines per language and condition, and for offline narration it would pick
#: kyutai for French and chatterbox for English. That is its decision to make
#: about *speech*; this is a decision about *what this package is willing to
#: install by default*, and the licence bar is the difference. The router's
#: answer is a recommendation a caller can follow with `--engine`.
ENGINES: tuple[str, ...] = ("kokoro", "kyutai", "openvoice", "chatterbox")

#: The default voice, per engine. Kokoro's is empty on purpose: the language
#: picks the voice, and a hard-coded default would be a hard-coded language.
#: On a bilingual site that is not a small mistake: the language is what the
#: phonemiser uses, so French read as English is not an accent, it is an
#: American spelling the words out.
#:
#: What makes the empty string safe is ``--lang``, which this module always
#: sends. Without it the wrapper detects the language of *each block* and
#: picks a voice per block, which is not the same promise at all. Measured
#: on one site's fourteen narrations: 89 blocks read by a voice foreign to
#: their page, Italian and Spanish among them, because "Stanislas, 2021" and
#: a three-word heading carry no signal. A page has one language; it is
#: decided once, below, from the whole text.
DEFAULT_VOICE: dict[str, str] = {
    "kokoro": "",
    # Empty for the same reason as kokoro's: kyutai carries a female default
    # per language (CML-TTS 10087 enhanced for French, VCTK p329 for English)
    # and naming one here would name a language with it.
    "kyutai": "",
    "openvoice": "base-en-default",
    "chatterbox": "default",
}

#: The one authorized LLM for ``--ai-hints`` — ``qwen3-vl:8b`` (via Ollama), the
#: same model :mod:`alt_from_ollama` uses, so the user only ever pulls one. Not
#: user-selectable; ``OLLAMA_MODEL`` is honoured only as a test seam.
DEFAULT_LLM_MODEL: str = os.environ.get("OLLAMA_MODEL", "qwen3-vl:8b")

#: Ollama daemon URL (shared default with alt_from_ollama / meta_from_ollama).
OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")


# ── LLM enrichment (optional, opt-in via --ai-hints) ──────────────────────


def _llm_classify_segment(
    seg: Segment,
    *,
    prev_text: str,
    next_text: str,
    model: str,
    timeout_s: float,
) -> dict[str, Any]:
    """
    Ask the local Ollama model to annotate one segment.

    Returns an empty dict on any error (network, timeout, JSON parse
    failure) so the caller falls back to structural defaults — fail
    soft everywhere.

    Parameters
    ----------
    seg : Segment
        Segment with structural defaults already filled in.
    prev_text, next_text : str
        Adjacent segment text, used as context.
    model : str
        Ollama model tag (e.g. ``qwen3-vl:8b``).
    timeout_s : float
        Per-call wall-clock budget.

    Returns
    -------
    dict
        Parsed JSON object on success, ``{}`` on any failure.
    """
    # Concise prompt — engine wrappers consume the structured JSON.
    user_prompt: str = (
        f"Previous segment: {prev_text!r}\n"
        f"Segment to annotate: {seg['text']!r}\n"
        f"Next segment: {next_text!r}\n"
        f"Segment kind: {seg['kind']}\n"
        f"Baseline emotion: {seg['emotion']}; baseline pace: {seg['pace']}.\n"
        "Reply with the JSON object only."
    )
    try:
        text: str = str(_llm_chat(user_prompt, system=LLM_SYSTEM_PROMPT, model=model)).strip()
        return json.loads(text) if text else {}
    except Exception:
        # ConnectionError, Timeout, JSONDecodeError — fail soft.
        return {}


def enrich_with_llm(
    segments: list[Segment],
    *,
    model: str = DEFAULT_LLM_MODEL,
    timeout_s: float = 30.0,
) -> list[Segment]:
    """
    Walk every segment, ask the LLM for hints, merge with structural baseline.

    A failed LLM call leaves the structural defaults untouched. The
    caller never crashes because the daemon is missing.

    Parameters
    ----------
    segments : list of Segment
    model : str
        Ollama model tag.
    timeout_s : float
        Per-segment wall-clock budget.

    Returns
    -------
    list of Segment
        Same length as the input; one merged segment per input.
    """
    out: list[Segment] = []
    for i, seg in enumerate(segments):
        prev_text: str = segments[i - 1]["text"] if i > 0 else ""
        next_text: str = segments[i + 1]["text"] if i < len(segments) - 1 else ""
        hint = _llm_classify_segment(
            seg,
            prev_text=prev_text,
            next_text=next_text,
            model=model,
            timeout_s=timeout_s,
        )
        out.append(merge_llm_hint(seg, hint) if hint else seg)
    return out


# ── Engine dispatch ────────────────────────────────────────────────────────


def _math_narrator(model: str) -> MathNarrator:
    """A reader for formulas too tangled to spell out, or ``None``.

    Reuses the ``latex_caption`` prompt this package already ships for the
    lint's screen-reader captions, because it asks for exactly the thing a
    narration needs: one plain-language sentence, in the document's
    language, that does not read the formula symbol by symbol. Two callers,
    one prompt — a second one would drift from it.

    Returned as a closure rather than wired in directly so
    :func:`_speech_text.speakable` stays free of the model, the network and
    the optional extra: the deterministic reading is the baseline, and this
    is the enrichment on top.
    """
    prompts = Path(__file__).resolve().parent / "prompts"

    def narrate(latex: str, lang: str) -> str | None:
        prompt = render_prompt("latex_caption", prompts_dir=prompts, latex_src=latex, lang=lang)
        answer = str(_llm_chat(prompt, model=model)).strip().strip('"').strip()
        return answer or None

    return narrate


def _engine_command(engine: str, python: str = sys.executable) -> list[str] | None:
    """Resolve how to invoke the chosen engine, or ``None`` if it is absent.

    The voices live in ``sprezzature-audio`` now, and they belong there:
    captions turn sound into timed text, narration turns text into timed
    sound, and one package owns that modality in both directions. This one
    owns the document and the page. A reader who wants Markdown rendered
    should not install a speech stack to get it.

    Resolution order, and both halves matter. ``python -m`` against the
    installed package is the normal path. The sibling checkout is the
    fallback, because this repository is developed next to that one and a
    contributor who has not pip-installed it should still be able to narrate
    a post.
    """
    module = f"sprezzature_audio_scripts.narrate_{engine}"
    try:
        found = importlib.util.find_spec(module) is not None
    except ModuleNotFoundError:
        # `find_spec` imports the *parent* package to ask it, so a missing
        # sprezzature-audio raises here rather than answering None. Without
        # this, the one case this function exists to handle — the voices are
        # not installed — crashed instead of returning the sentence that
        # names the install command. Invisible on a machine that has the
        # package; the only place it showed was CI.
        found = False
    if found:
        return [python, "-m", module]
    # Walked rather than indexed. This was `parents[3]`, which was right
    # while these scripts lived at sprezzature/sprezzature-publish/scripts/
    # and wrong the moment the package was extracted into its own repository
    # — one level shallower, so the path resolved to /Users/sprezzature-audio
    # and the fallback silently never fired again. A fallback that cannot
    # fire looks exactly like a fallback that was never needed.
    here = Path(__file__).resolve().parent
    for ancestor in here.parents:
        sibling = ancestor / "sprezzature-audio" / "scripts" / f"narrate_{engine}.py"
        if sibling.is_file():
            return [python, str(sibling)]
    return None


def _engine_is_available(engine: str, python: str = sys.executable) -> bool:
    """
    Probe whether the engine's Python dependencies are importable.

    Each wrapper exposes a ``--check`` flag that imports the heavy
    module and exits 0 / 1 accordingly. We invoke it as a subprocess
    so the import never enters the orchestrator's address space.
    """
    command = _engine_command(engine, python)
    if command is None:
        return False
    try:
        proc = subprocess.run(
            command + ["--check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def _language_fell_back(requested: str, report: dict[str, Any]) -> bool:
    """Whether the reading happened in a language other than the one asked for.

    Kokoro carries 54 voices across nine languages, which leaves most of the
    world out: ask for Welsh and an English voice answers. That is a sane
    fallback and a terrible silence, because the audio sounds perfectly fine
    and is simply in the wrong tongue.

    Worked out by comparing tags rather than read off the report. The wrapper
    does return a ``language_fallback`` field, but nothing in the chain below
    ever sets it -- the backend computes the flag when it picks the voice and
    drops it on the floor -- so trusting it would be recording a constant
    ``False`` and calling it a measurement. What the report does say
    truthfully is which language it ended up in: ask for ``de`` and it comes
    back ``en-us``, ask for ``fr`` and it comes back ``fr-fr``. Comparing the
    base tags is therefore the question actually being answered.

    Parameters
    ----------
    requested : str
        The language asked for, as a two-letter tag.
    report : dict
        The wrapper's JSON report, whose ``language`` is the tag it used.

    Returns
    -------
    bool
        True when the two name different languages. False when they agree,
        and when either side is missing -- an unanswerable question is not
        evidence of a fallback.
    """
    used: str = str(report.get("language", ""))
    if not requested or not used:
        return False
    # Base tags only: "fr" against "fr-fr" is the same language, and the
    # region is the engine's business rather than a disagreement.
    return used.split("-", 1)[0].lower() != requested.split("-", 1)[0].lower()


def run_engine(
    engine: str,
    *,
    segments: list[Segment],
    voice: str,
    voice_sample: Path | None,
    out_dir: Path,
    lang: str = "",
    lexicon: Path | None = None,
    python: str = sys.executable,
) -> dict[str, Any]:
    """
    Hand off to the engine wrapper.

    Communication is by JSON: orchestrator writes
    ``segments.json`` + invocation flags; wrapper writes
    ``out_dir/<slug>.wav`` (or .mp3) and prints a JSON summary on
    stdout (``{"audio": "...", "duration_seconds": ...}``).

    Parameters
    ----------
    engine : str
        One of :data:`ENGINES`.
    segments : list of Segment
        Output of :func:`extract_segments` (optionally LLM-enriched).
    voice : str
        Engine-specific built-in voice name. Ignored when
        ``voice_sample`` is set.
    voice_sample : Path or None
        Path to a reference WAV for voice cloning. None → use the
        engine's built-in voice ``voice``.
    out_dir : Path
        Directory to write the audio into.
    lang : str
        Two-letter language tag for the whole reading. Empty leaves the
        choice to the wrapper, which then makes it *per block* and mixes
        voices inside one page; every caller here passes it.
    lexicon : Path or None
        A pronunciation lexicon (YAML), forwarded untouched. Technical
        prose is full of words no engine can guess — WebVTT, RTTM, OKLCH,
        GMTED2010 — and each engine guesses differently, so the same page
        read twice does not sound the same. Stating a word once fixes it
        everywhere. Needs speaker-helper 0.11 or later.

    Returns
    -------
    dict
        ``{"audio": str, "duration_seconds": float}`` — caller writes
        this into the manifest.

    Raises
    ------
    RuntimeError
        When the engine wrapper exits non-zero. The wrapper's stderr
        is included in the message for debuggability.
    """
    command = _engine_command(engine)
    if command is None:
        raise RuntimeError(
            f"engine {engine!r} is not reachable. The voices ship with "
            f"sprezzature-audio: pip install 'sprezzature-audio[narrate]', "
            f"then sprezzature-audio-install-voice --engine {engine}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    segments_file: Path = out_dir / ".segments.json"
    segments_file.write_text(
        json.dumps(segments, ensure_ascii=False),
        encoding="utf-8",
    )

    cmd: list[str] = [
        *command,
        "--segments",
        str(segments_file),
        "--out-dir",
        str(out_dir),
    ]
    if voice_sample:
        cmd += ["--voice-sample", str(voice_sample)]
    else:
        cmd += ["--voice", voice]
    # Sent whenever we know it, which is always in practice. The wrapper
    # treats an empty --lang as "work it out yourself", and it works it out
    # one block at a time, so leaving this off is how a bilingual page ends
    # up with two accents. Harmless to the cloning engines: they take the
    # same flag and use it for their own language setting, which otherwise
    # defaults to French for everybody.
    if lang:
        cmd += ["--lang", lang]
    # Only when there is one. The flag landed in sprezzature-audio with
    # speaker-helper 0.11, and sending it to an older wrapper would fail the
    # whole narration over a file nobody asked for.
    if lexicon:
        cmd += ["--lexicon", str(lexicon)]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    # Clean the segments scratch file regardless of outcome.
    try:
        segments_file.unlink()
    except OSError:
        pass
    if proc.returncode != 0:
        raise RuntimeError(
            f"{engine} wrapper exited {proc.returncode}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    # The wrapper prints one JSON object on the last non-empty line.
    last_line: str = next(
        (line for line in reversed(proc.stdout.splitlines()) if line.strip()),
        "",
    )
    try:
        return json.loads(last_line)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"{engine} wrapper returned non-JSON output:\n{proc.stdout}") from e


# ── CLI ────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """Parse the command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="sprezzature-publish-narrate",
        description="Narrate a Markdown post via a local OSS TTS engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "post",
        type=Path,
        help="Path to the post to narrate: Markdown, or an HTML page.",
    )
    parser.add_argument(
        "--scope",
        default=None,
        help="HTML input only: the element to read, as 'article', '#id' or "
        "'.class'. Without it the whole document is read — header, nav "
        "and footer included, which is rarely what a reader asked for.",
    )
    parser.add_argument(
        "--engine",
        choices=ENGINES,
        default="kokoro",
        help="TTS engine wrapper (default: kokoro).",
    )
    parser.add_argument(
        "--voice",
        default="",
        help="Engine built-in voice name. Left empty, each engine uses its "
        "own default — for kokoro that means detecting the language of "
        "the text and picking the voice that speaks it. Ignored if "
        "--voice-sample is set.",
    )
    parser.add_argument(
        "--voice-sample",
        type=Path,
        default=None,
        help="Path to a reference WAV for voice cloning. Overrides --voice.",
    )
    parser.add_argument(
        "--lang",
        default="",
        help="Two-letter language tag for the whole reading, e.g. 'fr'. "
        "Left empty it is detected once from the full text, which is "
        "right for almost every page; set it where a page quotes "
        "another language at length and detection reads the quotes "
        "instead of the page.",
    )
    parser.add_argument(
        "--lexicon",
        type=Path,
        default=None,
        help="A pronunciation lexicon (YAML) for the words no engine can "
        "guess — acronyms, product names, surnames. State a word once and "
        "every narration says it the same way. Needs speaker-helper 0.11.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("out/audio"),
        help="Where to write the audio file + manifest (default: out/audio/).",
    )
    parser.add_argument(
        "--ai-hints",
        action="store_true",
        help="Enrich segment hints via local Ollama (off by default).",
    )
    parser.add_argument(
        "--ai-hints-only",
        action="store_true",
        help="Print the enriched segment hints as JSON and exit. "
        "Useful for review before invoking the TTS engine.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-narrate even when the manifest sha256 matches the source.",
    )
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint. Returns ``0`` on success."""
    args = parse_args()
    if not args.post.is_file():
        print(f"FAIL post not found: {args.post}", file=sys.stderr)
        return 1

    source: str = args.post.read_text(encoding="utf-8")
    if args.post.suffix.lower() in HTML_SUFFIXES:
        # A page that was never Markdown is a page nobody can regenerate,
        # which is precisely the page that most needs an accessibility pass
        # it can receive without being rewritten. The structural hints come
        # from the page's own elements — an <h2> earns the same pause as a
        # '##' because it is the same thing.
        page = _readalong.page_blocks(source, scope=args.scope)
        blocks = [(block.tag, block.visible, block.in_quote) for block in page]
        segments: list[Segment] = segments_from_blocks(blocks)
        # The same blocks, minus what is written for the eye alone. Built as
        # a parallel list rather than threaded through `Segment`, because
        # the two differ only in their text and every other decision — the
        # pauses, the emotion, the kind — is identical by construction.
        spoken_blocks = [(block.tag, block.spoken, block.in_quote) for block in page]
        spoken_segments: list[Segment] | None = segments_from_blocks(spoken_blocks)
    else:
        # The same silencing the HTML route gets for free from
        # `page_blocks`. Without it the two halves of this package disagree
        # about what belongs to the reading: the voice says the
        # bibliography and the read-along binder, which does apply the
        # rule, then refuses the page it was handed.
        segments = _readalong.drop_note_sections(extract_segments(source))
        spoken_segments = None
    if not segments:
        print(f"FAIL post is empty (no narrate-able segments): {args.post}", file=sys.stderr)
        return 1

    # Pronunciation overrides are loaded here but applied to the SPOKEN
    # string only, further down. Applying them to the segments rewrote the
    # cue text ("Stanislasse" showed up in the read-along), and on the page
    # route the spoken side was then rebuilt from the page's own words, so
    # the engine never heard the override at all: the fix was read, not said.
    pronunciation = load_pronunciation(args.post)

    if args.ai_hints:
        # The model is fixed at qwen3-vl:8b (the one authorized LLM); not a CLI
        # knob. ``enrich_with_llm`` defaults to ``DEFAULT_LLM_MODEL``.
        segments = enrich_with_llm(segments)

    if args.ai_hints_only:
        print(json.dumps(segments, indent=2, ensure_ascii=False))
        return 0

    # Split into sentences only now, and the order is deliberate. The model
    # judges emotion and pace from a whole block, where the context lives; a
    # sentence shown alone loses the thread and gets flatter hints. And
    # `--ai-hints-only` stays readable as blocks, which is what a human
    # inspecting the hints wants to see.
    #
    # From here on, a "segment" is a sentence: it is the unit that gets its
    # own slice of audio, and therefore the unit the page can follow. The
    # HTML must be built from this same call, or cue 12 and span 12 stop
    # being the same words.
    segments = explode_to_sentences(segments)

    # What the voice says, where it differs from what the page shows.
    #
    # Two things make it differ, and both would otherwise be read aloud as
    # the typography they are: a footnote marker ("the Ralph technique one,
    # after Ralph Wiggum") and a formula ("backslash, open parenthesis, R
    # equals T underscore..."). The cue keeps the page's words, so the
    # read-along still highlights what a reader sees; only the string handed
    # to the engine changes.
    # One language for the page, and it serves two purposes from here: it
    # decides what `speakable` spells out, and it decides which voice reads.
    # Detection runs on the joined text of every block rather than block by
    # block, because that is where the signal is -- a heading or a dateline
    # on its own is a coin toss.
    lang = args.lang or detect_text_language(" ".join(seg["text"] for seg in segments))
    # A formula above a handful of operators is not helped by being spelled
    # out: "the sum over i of x i, all over n" is a transliteration, and
    # only a sentence survives being heard once with no page in front of
    # you. Behind --ai-hints, like every other thing here that asks a model.
    narrator = _math_narrator(DEFAULT_LLM_MODEL) if args.ai_hints else None
    spoken = explode_to_sentences(spoken_segments) if spoken_segments else None
    if spoken is not None and len(spoken) != len(segments):
        # Should not happen any more: the spoken text keeps the page's shape
        # to the character while it is split, markers and all, and they are
        # taken out per sentence afterwards. Kept as a guard rather than an
        # assertion because a narration is not worth losing over a sentence
        # count -- the fallback reads the maths and leaves the markers,
        # which is the lesser of the two wrongs.
        print(
            f"note: {len(spoken)} spoken sentences against {len(segments)} on "
            f"the page; keeping the page's wording and reading the maths only",
            file=sys.stderr,
        )
        spoken = None
    for index, segment in enumerate(segments):
        source_text = (
            _readalong.without_markers(spoken[index]["text"]) if spoken else segment["text"]
        )
        say = speakable(source_text, lang, narrator=narrator)
        # The override takes the spoken string as it leaves `speakable`, so
        # it also covers a token that a formula or a footnote spelled out.
        say = apply_pronunciation_text(say, pronunciation)
        if say != segment["text"]:
            segment["say"] = say

    # Cache check — skip when nothing changed.
    manifest_path: Path = args.out_dir / "manifest.json"
    manifest: dict[str, NarrationManifestEntry] = read_manifest(manifest_path)
    source_key: str = args.post.as_posix()
    # The overrides belong in the digest: they no longer touch the segment
    # text, so without this a new pronunciation.yaml would hit the cache and
    # the voice would never say it.
    digest: str = source_sha256(
        segments_to_text(segments)
        + (json.dumps(pronunciation, sort_keys=True, ensure_ascii=False) if pronunciation else "")
    )
    if not args.force:
        existing = manifest.get(source_key)
        if (
            existing is not None
            and existing.source_sha256 == digest
            and existing.engine == args.engine
            and existing.voice
            == (args.voice_sample.as_posix() if args.voice_sample else args.voice)
            # The language belongs in the key for the same reason it belongs
            # in the call: it chooses the voice, so the same text under a
            # different language is different audio. Rows written before it
            # was recorded carry "" and therefore miss, which is the right
            # outcome rather than a nuisance -- those were read with a voice
            # per block, and reusing them would carry the mixture forward
            # through the very change that fixes it.
            and existing.language == lang
            # Resolved against the base it was *written* against. The row
            # stores the path relative to out_dir.parent (see the write
            # below), while this test used to read it relative to the
            # process's working directory -- so the file was found only when
            # the two happened to coincide, and the cache that this whole
            # block exists for never hit on a normal run. Absolute rows,
            # which is what the tests build, hit either way and hid it.
            and (args.out_dir.parent / existing.audio).is_file()
        ):
            print(f"OK cache hit: {existing.audio}")
            return 0

    # An empty --voice means "whatever this engine calls default", and the
    # engines disagree about what that is: openvoice wants a base speaker
    # name, chatterbox the literal string "default", kokoro nothing at all
    # because for kokoro the language names the voice and the language is
    # sent separately. Resolving it here keeps that difference out of every
    # call site below.
    if not args.voice:
        args.voice = DEFAULT_VOICE.get(args.engine, "")

    if not _engine_is_available(args.engine):
        # The paths this used to print pointed into this repository, where
        # the voices lived before they moved to sprezzature-audio. They
        # resolved to nothing, which is the worst shape for an install hint:
        # the reader follows it, gets "no such file", and cannot tell whether
        # they are in the wrong directory or reading a stale message.
        print(
            f"FAIL engine '{args.engine}' is not installed.\n"
            f"  Install: pip install 'sprezzature-audio[narrate-{args.engine}]'\n"
            f"  Then run: sprezzature-audio-install-voice --engine {args.engine}",
            file=sys.stderr,
        )
        return 2

    started: float = time.monotonic()
    result: dict[str, Any] = run_engine(
        args.engine,
        segments=segments,
        voice=args.voice,
        voice_sample=args.voice_sample,
        out_dir=args.out_dir,
        lang=lang,
        lexicon=args.lexicon,
    )
    elapsed: float = time.monotonic() - started

    manifest[source_key] = NarrationManifestEntry(
        source=source_key,
        audio=str(Path(result["audio"]).relative_to(args.out_dir.parent))
        if str(result["audio"]).startswith(str(args.out_dir.parent))
        else str(result["audio"]),
        engine=args.engine,
        voice=args.voice_sample.as_posix() if args.voice_sample else args.voice,
        source_sha256=digest,
        duration_seconds=float(result.get("duration_seconds", -1)),
        language=lang,
        # What the engine reports it did, not what we asked: the two differ
        # whenever the ask was empty, which is the normal case here. A WAV
        # carries no record of the voice that produced it, so if this row
        # does not say, nothing does.
        resolved_voice=str(result.get("voice", "")),
        language_fallback=_language_fell_back(lang, result),
    )
    write_manifest(manifest_path, manifest)
    print(
        f"OK narrated {source_key} in {elapsed:.1f}s → {result['audio']} "
        f"({result.get('duration_seconds', 0):.1f}s audio, "
        f"{lang} / {result.get('voice', '?')})"
    )
    # A page whose language has no voice is read in another one, and that is
    # the kind of thing a log line should not bury: the audio sounds fine,
    # it is simply the wrong tongue.
    if _language_fell_back(lang, result):
        print(
            f"note: no voice for '{lang}'; read with '{result.get('voice', '?')}' instead",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
