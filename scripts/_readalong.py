"""
_readalong — wire a narrated page to its audio, sentence by sentence.

The audio and the page come from the same Markdown by two different routes:
``_narrate.extract_segments`` cleans the Markdown and hands sentences to a TTS
engine, while ``md_to_html`` renders the Markdown with the ``markdown``
library. Nothing makes those two agree about what sentence twelve is, and a
read-along that is wrong by one sentence is worse than none -- it tells a
reader with confidence to look at the wrong line.

So this module does not number sentences independently. It takes the cues the
narration actually produced, splits the rendered HTML with the *same*
splitter, and compares the two lists. They match, or it raises and names the
first divergence. There is no third outcome where it wraps something and
hopes.

Reading the page as a tree, not as a pattern
--------------------------------------------
The blocks are found by walking the HTML rather than matching it, because
three things a regex cannot see decide what a block's text is:

* A code fence inside a list item. The narration drops fenced code; a
  pattern matching ``<li>…</li>`` swallows the ``<pre>`` with it and reads
  out ``git clone … cd … python3 -m venv``.
* A nested list. ``<li>Parent<ul><li>Child</li></ul></li>`` is two narrated
  segments in the audio and one match to a pattern, which merges them.
* An image. ``![alt](src)`` is narrated -- the alt text is what a listener
  gets instead of the picture -- so the page has to count that text too,
  and the picture is what gets highlighted while it is read.

Cues with nothing of their own to highlight
-------------------------------------------
Not every cue has a sentence on the page. ``extract_segments`` wraps a
blockquote in :data:`_narrate.QUOTE_OPENING` and
:data:`_narrate.QUOTE_CLOSING` so a listener hears where the quotation
starts and stops, and "End quote." is a sentence the reader never sees.
Those cues are attached to the block they belong to instead of being matched
to text, and the player simply keeps the current highlight while they play.

What it emits
-------------
* ``<span class="ra-s" id="ra-12">`` around each sentence, which is what the
  highlight attaches to.
* A player: ``<audio controls>`` plus a ``<track kind="metadata">`` pointing
  at the narration's WebVTT, so the browser parses the cues and fires
  ``cuechange`` with no parsing code of ours.

Accessibility notes, since that is the point of the feature
-----------------------------------------------------------
Read-along audio is not for screen-reader users -- they already have speech,
and a second voice talking over theirs is an obstacle, not an aid. It serves
dyslexic readers, readers with low vision who use magnification, readers
tired or distracted, and people reading in a second language. That shapes
every decision below:

* The highlight is **visual only**. No ARIA live region, no ``aria-current``
  churn: announcing every sentence as it is spoken would make the page
  unusable for anyone who *is* on a screen reader, for the benefit of someone
  who is not.
* Auto-scroll becomes instant under ``prefers-reduced-motion`` rather than
  disappearing. Smooth scrolling is the vestibular trigger; a jump is not
  animation, and removing the scroll altogether would leave a reader hunting
  for the highlight they asked to follow.
* The highlight is a background tint **and** a left border, never colour
  alone -- WCAG 1.4.1.
* Every sentence is clickable to seek, and the player keeps native controls,
  so the feature is reachable by keyboard without a single custom key
  handler.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import html
import os
import re
import shutil
import unicodedata
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import TypeAlias

#: How a block of prose becomes sentences. Threaded through every
#: read-along entry point rather than imported, so the page and the
#: narration are split by the *same* function — two splitters that
#: disagree put the highlight on the wrong sentence, which is the one
#: bug this module exists to avoid.
SentenceSplitter: TypeAlias = Callable[[str], "list[str]"]

#: Block elements whose text is narrated. Code blocks are deliberately absent:
#: ``extract_segments`` strips them, so the narration has nothing to say about
#: them and wrapping them would push every later index out by one.
NARRATED_BLOCKS: frozenset[str] = frozenset(
    {"p", "li", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6"}
)

#: Subtrees whose text is not read. ``pre`` holds code and ``table`` is
#: skipped for the same reason; the rest is page furniture that exists on
#: every hand-written page and on no Markdown one -- a reader asking to hear
#: *this article* did not ask for the navigation, the cookie banner or the
#: contents of a ``<style>`` block.
SKIPPED_SUBTREES: frozenset[str] = frozenset(
    {
        "pre",
        "table",
        "script",
        "style",
        "template",
        "noscript",
        "svg",
        "head",
        "title",
        "nav",
        "footer",
        "aside",
        "form",
        "dialog",
        "select",
        "option",
    }
)


def _matches(selector: str, tag: str, attrs: list[tuple[str, str | None]]) -> bool:
    """Whether an element matches a one-step selector.

    Three forms, which is all a scope needs: ``article`` (tag name),
    ``#main`` (id) and ``.post-body`` (one class). Deliberately not a CSS
    engine -- descendant combinators and attribute predicates would invite
    the caller to express something this walker cannot honour, and the
    failure would be a page narrated from the wrong element.
    """
    if selector.startswith("#"):
        return any(name == "id" and value == selector[1:] for name, value in attrs)
    if selector.startswith("."):
        return any(
            name == "class" and selector[1:] in (value or "").split() for name, value in attrs
        )
    return tag == selector.lower()


#: Attributes that take an element out of the reading. ``aria-hidden`` is the
#: one that matters: it already hides the element from assistive technology,
#: and narrating what a screen reader is told to ignore would have this
#: feature contradict the page it is trying to help.
def _is_hidden(attrs: list[tuple[str, str | None]]) -> bool:
    """Whether an element is hidden from readers, by markup rather than CSS."""
    for name, value in attrs:
        if name == "hidden":
            return True
        if name == "aria-hidden" and (value or "").strip().lower() == "true":
            return True
    return False


#: Class on every wrapped sentence. Short because it appears once per
#: sentence and a long name is measurable page weight on a long post.
SENTENCE_CLASS = "ra-s"

#: Audio types this player will declare, by file extension. Public so the
#: converter can look for exactly the recordings this player can serve. A ``<source>``
#: with the wrong ``type`` is a file the browser declines to load, and one
#: with no ``type`` costs a round trip to find out -- so an unknown extension
#: raises here rather than being guessed at.
AUDIO_TYPES: dict[str, str] = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".opus": "audio/ogg",
    ".flac": "audio/flac",
}

#: Elements with no closing tag. They are tracked separately because inline
#: depth is counted by pairs: a ``<br>`` that increments and never decrements
#: pushes every later piece of the block one level deeper, and the crossing
#: check below then refuses a sentence that was never crossing anything. A
#: hard line break inside a paragraph is ordinary prose, so this was not a
#: rare case.
VOID_ELEMENTS: frozenset[str] = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

#: Strikethrough markers, which this project's renderer does not implement:
#: ``~~F5-TTS~~`` reaches the page as text. The narration drops them -- a
#: voice saying "tilde tilde" is not reading the sentence -- so the page side
#: has to agree they are markup and not words.
_TILDES = re.compile(r"~~")

_TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class VttCue:
    """One cue read back from a narration WebVTT file."""

    index: int
    text: str
    start_seconds: float
    end_seconds: float


class ReadAlongMismatch(RuntimeError):
    """The page and the narration disagree about the sentences.

    Raised rather than worked around. The two lists come from the same
    Markdown, so a divergence means one of the two routes changed -- a new
    Markdown construct that ``extract_segments`` strips and the renderer
    keeps, or the reverse -- and the fix is to make them agree again, not to
    wrap whatever happens to line up.
    """


def _timestamp_seconds(stamp: str) -> float:
    """Parse ``HH:MM:SS.mmm`` or ``MM:SS.mmm`` into seconds."""
    parts = stamp.strip().split(":")
    if len(parts) == 2:
        parts = ["0", *parts]
    hours, minutes, rest = parts
    return int(hours) * 3600 + int(minutes) * 60 + float(rest)


def parse_vtt(text: str) -> list[VttCue]:
    """Read the cues a narration run wrote.

    Only what this project emits is supported -- an identifier line, a timing
    line, one line of payload. Styling blocks, regions and positioning are
    not parsed, because nothing here writes them and silently ignoring a
    construct is how a parser starts lying about its input.
    """
    if not text.lstrip().startswith("WEBVTT"):
        raise ReadAlongMismatch("not a WebVTT file: it does not start with WEBVTT")

    cues: list[VttCue] = []
    blocks = re.split(r"\n\s*\n", text.strip())
    for block in blocks[1:]:  # blocks[0] is the WEBVTT header
        lines = [line for line in block.splitlines() if line.strip()]
        if len(lines) < 3:
            continue
        identifier, timing, *payload = lines
        if "-->" not in timing:
            continue
        start, end = (part.strip() for part in timing.split("-->", 1))
        cues.append(
            VttCue(
                index=int(identifier.strip()),
                text=" ".join(" ".join(payload).split()),
                start_seconds=_timestamp_seconds(start),
                end_seconds=_timestamp_seconds(end.split()[0]),
            )
        )
    return cues


def _visible_text(fragment: str) -> str:
    """The words a reader sees, with markup and entities resolved.

    Comparison has to happen on this rather than on raw HTML: the narration
    never saw ``<em>`` and the page never saw the Markdown asterisks, so the
    two agree on words and on nothing else.
    """
    return " ".join(html.unescape(_TAG.sub("", fragment)).split())


# ── Reading the page as a tree ──────────────────────────────────


@dataclass
class _Piece:
    """One atom of a block's content: its markup, and the words it shows.

    Three kinds, distinguished by what may be done to them:

    * **text** -- may be cut, because a sentence can end in the middle of it;
    * **atomic** -- may not. An ``<img>`` is the case that matters: its alt
      text is narrated, possibly as several sentences, but a picture is one
      object and a span boundary inside it has nowhere to go;
    * **a nested block** -- a list inside a list item, say. Its words belong
      to *it*, so it shows none of its own here, and it is rendered by
      recursion once its own sentences are wrapped.
    """

    raw: str
    visible: str = ""
    atomic: bool = False
    child: _Block | None = None
    #: Inline nesting depth on each side of this piece. A span must open and
    #: close at the same depth: one that opens outside an ``<em>`` and closes
    #: inside it crosses the element, which is not valid HTML -- so it is
    #: detected, not emitted. Both sides are recorded because a span grows by
    #: swallowing the tags that close inside it, and only ``after`` says when
    #: it has swallowed enough.
    depth: int = 0
    after: int = 0
    #: Part of a footnote reference marker -- a superscript whose whole
    #: content is a number. Shown on the page, not spoken: see
    #: :attr:`_Block.spoken`.
    reference: bool = False


@dataclass
class _Block:
    """One narrated block of the page, with the markup that opened it."""

    tag: str
    open_raw: str = ""
    close_raw: str = ""
    pieces: list[_Piece] = field(default_factory=list)
    #: Inside a ``<blockquote>``. Carried because the narration says where a
    #: quotation starts and stops, and on a hand-written page the quoted text
    #: lives in a ``<p>`` *inside* the ``<blockquote>`` rather than in the
    #: element itself -- so the quotation is not visible from the block's own
    #: tag.
    in_quote: bool = False
    #: Whether this block belongs in the narration. Notes do not: see
    #: :func:`_mark_notes`. The page still shows them -- only the reading
    #: skips them -- so this is carried on the block rather than removed
    #: from the tree.
    narrated: bool = True

    @property
    def visible(self) -> str:
        """The words this block shows itself, whitespace collapsed.

        A nested block's words are not among them: the narration gives a
        nested list item its own segment, so counting it twice -- once for
        the parent, once for itself -- would put every later cue out by one.
        """
        return " ".join("".join(piece.visible for piece in self.pieces).split())

    @property
    def spoken(self) -> str:
        """The same words, with the ones meant for the eye alone marked.

        Today that means footnote reference markers. A superscript "1" is a
        signpost to the bottom of the page; read aloud it lands glued to
        whatever word it follows, and "the Ralph technique one, after Ralph
        Wiggum" is a sentence about a version number. The reader loses
        nothing, because the thing it points at is read in its own place.

        The page keeps the marker. Only the narration drops it, which is
        why this is a second string rather than an edit to
        :attr:`visible` -- the read-along still has to highlight exactly
        what the page shows.

        The marker is *wrapped*, not removed, and that is the whole
        subtlety. Removing it here changes where sentences end: a page
        reading ``ranking the top N<sup>9</sup>.`` gives ``top N9.``, which
        every sentence splitter ends a sentence on, and ``top N.`` without
        the marker, which every sentence splitter reads as an initial and
        runs into the next sentence. One page in twelve hit exactly that,
        and the two texts came out a sentence apart.

        So the text handed to the splitter keeps the page's shape to the
        character, and the markers are taken out of each sentence
        afterwards -- see :func:`without_markers`. The wrapper is a word
        joiner: invisible, non-breaking, and not something prose contains.
        """
        out: list[str] = []
        inside = False
        for piece in self.pieces:
            # One wrapper per *run*, not per piece. A marker is usually
            # three pieces -- the <a>, its text, the </a> -- and wrapping
            # each would bracket the empty ones too.
            if piece.reference != inside:
                out.append(MARKER)
                inside = piece.reference
            out.append(piece.visible)
        if inside:
            out.append(MARKER)
        return " ".join("".join(out).split())


#: Wraps a footnote marker in :attr:`_Block.spoken`. U+2060 WORD JOINER:
#: invisible, non-breaking, and not a character prose contains -- so the
#: sentence splitter sees the page's own shape and the marker can still be
#: found and removed once the sentences are settled.
MARKER: str = "\u2060"

_MARKED = re.compile(f"{MARKER}[^{MARKER}]*{MARKER}")


#: The class on the element the player is injected as. Named here because
#: two operations need it and they must not drift: the one that writes the
#: player, and the one that takes it back out.
PLAYER_CLASS = "ra-player"


def _balanced_element(html_text: str, start: int, tag: str) -> int:
    """Where the element opening at ``start`` ends, nesting followed.

    A regular expression cannot do this. ``<div class="ra-player">`` holds
    seven nested ``<div>`` of its own, so a pattern that stops at the first
    ``</div>`` cuts the player in half and leaves its tail in the page.
    """
    depth = 0
    pattern = re.compile(rf"</?{tag}\b[^>]*>", re.I)
    for found in pattern.finditer(html_text, start):
        depth += -1 if found.group().startswith("</") else 1
        if depth == 0:
            return found.end()
    raise ReadAlongMismatch(f"<{tag}> opened at {start} is never closed")


def strip_player(html_text: str) -> tuple[str, int]:
    """A page with its read-along taken back out, and how many markers went.

    The inverse of :func:`inject_into_page`, and it exists because correcting
    a sentence in a narrated page is an ordinary thing to want. The timings
    live in the page, one ``data-start`` per sentence; edit the prose and
    every marker after the edit points at the wrong line. Re-recording is
    the only repair, and re-recording needs the page back the way it was
    before the player was written into it.

    Without this, every caller writes it again. It was written from scratch
    three times in three days on one site, and each rewrite walked into the
    same two traps: a pattern that stops at the first ``</div>`` cuts the
    player in half, and unwrapping a ``<span class="ra-s">`` by deleting the
    tag *and its content* silently deletes the sentence.

    Three things come out: the player element, the ``<span>`` around each
    sentence (its content kept), and the stylesheet and module links if they
    were written into the head. Nothing else is touched, which is what makes
    the result safe to hand to a text editor and then to narrate again.

    >>> page, markers = strip_player(
    ...     '<p><span class="ra-s" id="ra-0" data-start="0.000">Hi.</span></p>')
    >>> page
    '<p>Hi.</p>'
    >>> markers
    1
    """
    opening = re.search(rf"<div[^>]*\b{re.escape(PLAYER_CLASS)}\b[^>]*>", html_text)
    if opening is not None:
        end = _balanced_element(html_text, opening.start(), "div")
        # Swallow the blank line the injection left behind, never the
        # character before it: gluing two words together would be a silent
        # corruption of the prose.
        while end < len(html_text) and html_text[end] in " \t\r\n":
            end += 1
        html_text = html_text[: opening.start()] + html_text[end:]

    markers = 0
    while True:
        found = re.search(rf"<span\s[^>]*\b{re.escape(SENTENCE_CLASS)}\b[^>]*>", html_text)
        if found is None:
            break
        end = _balanced_element(html_text, found.start(), "span")
        closing = html_text.rindex("</span>", found.end(), end)
        html_text = html_text[: found.start()] + html_text[found.end() : closing] + html_text[end:]
        markers += 1

    for asset in ASSET_FILES:
        html_text = re.sub(
            rf"[ \t]*<(?:link|script)\b[^>]*{re.escape(asset)}[^>]*>"
            rf"(?:</script>)?[ \t]*\r?\n?",
            "",
            html_text,
        )

    return html_text, markers


def disagreements(
    html_text: str, cues: Sequence[VttCue], *, tolerate: Sequence[str] = ()
) -> list[str]:
    """What a *delivered* page and a *delivered* VTT disagree about.

    :func:`inject_into_page` already refuses to write markers onto prose that
    moved while the voice was being recorded, and that net is reliable. It
    cannot help with the other order of events: a page edited *after* the
    player was written into it. Nothing fires then. The page keeps its
    markers, each one still carries a time, and every time now points at the
    wrong sentence — which is worse than no highlight at all, because it is
    confidently wrong.

    So this reads only what was shipped, and compares it to what was shipped
    beside it. Same number of markers as cues, same text, and each
    ``data-start`` at the beginning of its own cue to the millisecond.

    ``tolerate`` holds cue texts that legitimately have no marker. A
    narration announces the end of a block quotation out loud, "End quote.",
    and those words are not on the page, so they cannot carry a marker. Pass
    them rather than loosening the comparison: an equality that holds
    everywhere is worth more than one that is approximately right.

    Returns one line per disagreement, empty when the two agree.
    """
    wanted = [
        c
        for c in cues
        if " ".join(c.text.split()).rstrip(".").lower()
        not in {t.rstrip(".").lower() for t in tolerate}
    ]

    # No scope argument, deliberately. The markers only exist where they
    # were injected, so they *are* the scope; asking the caller to name it
    # again would be one more thing to get wrong.
    #
    # Template tags go first. On a PHP page the `?>` of a `<?= ASSETS ?>`
    # closes a `[^>]*` early, so stripping HTML before the template language
    # cuts tags in half and loses attributes.
    body = re.sub(r"<\?.*?\?>", " ", html_text, flags=re.S)

    found: list[tuple[str, float | None, str]] = []
    for marker in re.finditer(rf"<span\s[^>]*\b{re.escape(SENTENCE_CLASS)}\b[^>]*>", body):
        attrs = marker.group()
        # Named apart from the loop variables below: reusing `name` and
        # `start` for both a Match and a str made the whole function
        # untypeable, and the reader has to hold two meanings for one word.
        has_id = re.search(r'id="([^"]*)"', attrs)
        has_start = re.search(r'data-start="([^"]*)"', attrs)
        end = _balanced_element(body, marker.start(), "span")
        closing = body.rindex("</span>", marker.end(), end)
        found.append(
            (
                has_id.group(1) if has_id else "?",
                float(has_start.group(1)) if has_start else None,
                _visible_text(body[marker.end() : closing]),
            )
        )

    out: list[str] = []
    if len(found) != len(wanted):
        out.append(f"{len(found)} markers against {len(wanted)} cues")
    for (name, start, said), cue in zip(found, wanted):
        if start is None:
            out.append(f"{name}: no data-start")
            continue
        if abs(start - cue.start_seconds) > 0.0005:
            out.append(f"{name}: data-start {start:.3f} against {cue.start_seconds:.3f}")
        spoken = " ".join(cue.text.split())
        if said != spoken:
            # Say *where* they part, not how each begins: two sentences that
            # differ at their thirtieth word look identical in a report that
            # prints the first sixty characters of each.
            at = next(
                (i for i in range(min(len(said), len(spoken))) if said[i] != spoken[i]),
                min(len(said), len(spoken)),
            )
            window = slice(max(0, at - 30), at + 30)
            out.append(f"{name} at {at}: {said[window]!r} against {spoken[window]!r}")
    return out


def without_markers(sentence: str) -> str:
    """One sentence, with its footnote markers taken out.

    Applied *after* splitting, never before: see :attr:`_Block.spoken`.
    """
    return " ".join(_MARKED.sub("", sentence).split())


#: What a footnote marker looks like once the markup is stripped: a number,
#: optionally in brackets or parentheses. Anything else in a ``<sup>`` is
#: content and gets read.
_REFERENCE_MARKER = re.compile(r"[\[(]?\s*\d{1,3}\s*[\])]?")


#: What a page calls the section where its sources live. Folded to
#: lowercase without accents before matching, so "Références" and
#: "References" are the same key.
#:
#: This is the *second* signal, and it only fires when the first one finds
#: nothing. The first is structural — the footnote markers in the prose say
#: what they point at — and it needs no vocabulary at all, which is why it
#: is tried first and why a page whose heading is in no language this table
#: knows still works. But plenty of pages list their sources without
#: linking a single marker to them, and for those the name is all there is.
NOTE_SECTION_HEADINGS: frozenset[str] = frozenset(
    {
        # English
        "references",
        "reference",
        "bibliography",
        "notes",
        "footnotes",
        "endnotes",
        "sources",
        "further reading",
        "works cited",
        "citations",
        "see also",
        # French
        "references",
        "bibliographie",
        "notes",
        "notes et references",
        "sources",
        "pour aller plus loin",
        "ouvrages cites",
        "a lire aussi",
        # A few more that cost nothing to know
        "bibliografia",
        "referencias",
        "literatur",
        "quellen",
        "fonti",
        "bibliografie",
        "referenties",
        "bibliografía",
    }
)

#: A block that reads like a source rather than like prose: a list item, or
#: anything carrying a citation element or a bare URL.
_LOOKS_CITED = re.compile(r"<cite\b|https?://|\bdoi\.org/|\barxiv\.org/", re.I)

#: How much of a section has to read like sources before its heading is
#: taken at its word. Two thirds, not all: a bibliography often opens with
#: a line of prose saying what the list is.
_CITED_SHARE: float = 0.66


def _fold(text: str) -> str:
    """Lowercase, unaccented, punctuation-free — a heading as a key."""
    stripped = unicodedata.normalize("NFKD", text)
    stripped = "".join(c for c in stripped if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", stripped.lower()).split())


def _mark_named_sections(blocks: list[_Block]) -> bool:
    """Silence a section that says what it is, when it also looks the part.

    The corroboration matters. A heading called "Notes" above three
    paragraphs of prose is a section of an essay, and silencing it because
    of its name would be the kind of guess that makes a tool untrustworthy.
    A heading called "Notes" above twenty list items carrying ``<cite>``
    elements and arXiv links is an apparatus. The name proposes; the shape
    decides.
    """
    found = False
    for index, block in enumerate(blocks):
        if block.tag not in HEADING_TAGS:
            continue
        if _fold(block.visible) not in NOTE_SECTION_HEADINGS:
            continue
        end = index + 1
        while end < len(blocks) and blocks[end].tag not in HEADING_TAGS:
            end += 1
        body = blocks[index + 1 : end]
        if not body:
            continue
        cited = sum(
            1
            for b in body
            if b.tag == "li"
            or _LOOKS_CITED.search(b.open_raw + "".join(piece.raw for piece in b.pieces))
        )
        if cited / len(body) < _CITED_SHARE:
            continue
        for b in blocks[index:end]:
            b.narrated = False
        found = True
    return found


#: How far back from the first note to look for the heading that opens the
#: section holding it. Short on purpose: a bibliography's heading is within
#: a block or two of its list -- a title, maybe a line saying what the list
#: is -- and a longer reach would start silencing prose that happens to sit
#: above a note.
_NOTE_SECTION_REACH: int = 4


def _element_id(raw: str) -> str:
    match = re.search(r'\bid="([^"]+)"', raw)
    return match.group(1) if match else ""


def _mark_notes(blocks: list[_Block], targets: set[str]) -> None:
    """Take the notes out of the narration, and the page keeps them.

    A bibliography is reference apparatus. Thirty-seven citations read
    aloud is ten minutes of author names and arXiv numbers, which is not
    something anybody listens to and not something the recording is for.

    Found structurally rather than by its name: the footnote markers in the
    prose say what they point at, and what they point at is the notes. No
    page says "Bibliography" in every language, and plenty say "References",
    "Notes", "Sources" or nothing at all — but every one of them links its
    markers to its notes, because that is what makes a footnote a footnote.

    The section runs from the heading above the first note to the last note.
    Taking only the list would leave its heading and its opening line read
    aloud, announcing a section that then never arrives.
    """
    if not targets:
        _mark_named_sections(blocks)
        return
    marked = [index for index, block in enumerate(blocks) if _element_id(block.open_raw) in targets]
    if not marked:
        _mark_named_sections(blocks)
        return
    first, last = min(marked), max(marked)

    start = first
    for index in range(first - 1, max(-1, first - 1 - _NOTE_SECTION_REACH), -1):
        start = index
        if blocks[index].tag in HEADING_TAGS:
            break
    else:
        # No heading within reach: silence the notes themselves and leave
        # whatever is above them alone.
        start = first

    for block in blocks[start : last + 1]:
        block.narrated = False

    # A page can have both: linked footnotes in one section and an unlinked
    # "Further reading" in another.
    _mark_named_sections(blocks)


#: Elements that wrap a display formula and nothing else. They are layout
#: everywhere else on a page, so they are opened as blocks on approval and
#: unwrapped again at their close unless what they hold turns out to be one
#: formula. A page that writes its mathematics this way is not unusual —
#: KaTeX, MathJax and every hand-rolled renderer want a block element to put
#: the formula in, and none of them agree on a class to look for.
MATH_WRAPPERS: frozenset[str] = frozenset({"div", "figure"})

#: Headings, which is where a section starts.
HEADING_TAGS: frozenset[str] = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

#: What such a wrapper has to contain to earn being narrated: a display
#: formula, and nothing else.
_DISPLAY_MATH_ONLY = re.compile(r"\s*(?:\$\$.+?\$\$|\\\[.+?\\\])\s*", re.S)


class _PageWalker(HTMLParser):
    """Split rendered HTML into narrated blocks, keeping the markup.

    Rebuilds the document rather than indexing into it: every event is
    re-emitted verbatim, so the output differs from the input only by the
    spans that get inserted. ``convert_charrefs`` is off so that entities
    stay entities -- resolving them would quietly rewrite ``&amp;`` as ``&``
    in the page's own source.
    """

    def __init__(self, scope: str | None = None) -> None:
        super().__init__(convert_charrefs=False)
        #: Only blocks inside this element are narrated. ``None`` narrates the
        #: whole document, which is right for a page this project rendered and
        #: wrong for one it did not: a hand-written page carries a header, a
        #: nav and a footer that a reader asking for *this article* did not
        #: ask to hear.
        self._scope = scope
        self._scope_at: int | None = None
        #: The pieces holding the start tags of the scope element and of
        #: ``<body>``. Kept so a player can be placed at the top of the
        #: article it belongs to: the pieces are mutable, so the injection
        #: appends to one of them rather than hunting for a tag in the
        #: rebuilt string.
        self.scope_piece: _Piece | None = None
        self.body_piece: _Piece | None = None
        #: The document itself, as pieces. Nested content hangs off
        #: ``_Piece.child`` rather than being flattened, so reading order
        #: survives into the rebuild.
        self.out: list[_Piece] = []
        #: Every narrated block, in reading order -- which is the order the
        #: cues are in, and the only order the alignment may use.
        self.blocks: list[_Block] = []
        self._open: list[_Block] = []
        self._skip = 0
        self._depth = 0
        #: ``<blockquote>`` nesting, so a paragraph knows it is quoted.
        self._quoted = 0
        #: Depth of the hidden subtree we are inside, if any. Tracked by the
        #: whole element stack rather than a flag: ``aria-hidden`` on a
        #: wrapper hides everything under it, not just its own text.
        self._hidden_at: int | None = None
        self._stack = 0
        #: Ids that a footnote marker points at. Collected while walking,
        #: which works because a marker always precedes the note it names.
        self.reference_targets: set[str] = set()
        #: Index of the first piece of the open ``<sup>``, if any. A
        #: superscript is only a footnote marker if its *whole* content is a
        #: number, and that is not known until it closes.
        self._sup_from: int | None = None

    def _emit(self, piece: _Piece) -> None:
        (self._open[-1].pieces if self._open else self.out).append(piece)

    def _raw(
        self, raw: str, visible: str = "", *, atomic: bool = False, after: int | None = None
    ) -> None:
        self._emit(
            _Piece(
                raw,
                visible,
                atomic=atomic,
                depth=self._depth,
                after=self._depth if after is None else after,
            )
        )

    # -- events ------------------------------------------------------------

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag}>"
        if tag not in VOID_ELEMENTS:
            self._stack += 1
            if self._hidden_at is None and _is_hidden(attrs):
                self._hidden_at = self._stack
        if tag == "blockquote":
            self._quoted += 1
        if (
            self._scope is not None
            and self._scope_at is None
            and tag not in VOID_ELEMENTS
            and _matches(self._scope, tag, attrs)
        ):
            self._scope_at = self._stack
            self._raw(raw, atomic=True)
            self.scope_piece = (self._open[-1].pieces if self._open else self.out)[-1]
            return
        if self._hidden_at is not None:
            self._raw(raw, atomic=True)
            return
        if tag in SKIPPED_SUBTREES:
            self._raw(raw, atomic=True)
            self._skip += 1
            return
        if self._skip:
            self._raw(raw, atomic=True)
            return
        if tag == "sup" and self._sup_from is None:
            target = self._open[-1].pieces if self._open else self.out
            self._raw(raw, atomic=True)
            self._sup_from = len(target) - 1
            return
        if tag == "img":
            alt = next((value or "" for name, value in attrs if name == "alt"), "")
            self._raw(raw, html.unescape(alt), atomic=True)
            return
        if tag in NARRATED_BLOCKS or tag in MATH_WRAPPERS:
            block = _Block(tag, open_raw=raw, in_quote=self._quoted > 0)
            self._emit(_Piece("", child=block, atomic=True, depth=self._depth))
            self._open.append(block)
            if self._scope is None or self._scope_at is not None:
                self.blocks.append(block)
            self._depth = 0
            return
        if tag in VOID_ELEMENTS:
            # A line break separates words. Without the space, "Line one.<br>
            # Line two." reads back as one run of characters and the
            # comparison fails on a page that is perfectly ordinary.
            self._raw(raw, " " if tag == "br" else "", atomic=True)
            return
        self._raw(raw, atomic=True, after=self._depth + 1)
        if tag == "body":
            self.body_piece = (self._open[-1].pieces if self._open else self.out)[-1]
        self._depth += 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        raw = self.get_starttag_text() or f"<{tag}/>"
        if tag == "img" and not self._skip:
            alt = next((value or "" for name, value in attrs if name == "alt"), "")
            self._raw(raw, html.unescape(alt), atomic=True)
            return
        self._raw(raw, atomic=True)

    def handle_endtag(self, tag: str) -> None:
        raw = f"</{tag}>"
        if tag == "blockquote":
            self._quoted = max(0, self._quoted - 1)
        if tag not in VOID_ELEMENTS:
            leaving_hidden = self._hidden_at == self._stack
            if self._scope_at == self._stack:
                self._scope_at = None
            self._stack = max(0, self._stack - 1)
            if leaving_hidden:
                self._hidden_at = None
                self._raw(raw, atomic=True)
                return
        if self._hidden_at is not None:
            self._raw(raw, atomic=True)
            return
        if tag in SKIPPED_SUBTREES:
            self._skip = max(0, self._skip - 1)
            self._raw(raw, atomic=True)
            return
        if self._skip:
            self._raw(raw, atomic=True)
            return
        if tag == "sup" and self._sup_from is not None:
            self._raw(raw, atomic=True)
            self._close_sup()
            return
        if (
            (tag in NARRATED_BLOCKS or tag in MATH_WRAPPERS)
            and self._open
            and self._open[-1].tag == tag
        ):
            block = self._open.pop()
            block.close_raw = raw
            self._depth = 0
            if tag in MATH_WRAPPERS and not _DISPLAY_MATH_ONLY.fullmatch(block.visible):
                self._unwrap(block)
                # Taken off the narration list as well as out of the tree:
                # it was added when it opened, before anyone could know what
                # it held.
                if self.blocks and self.blocks[-1] is block:
                    self.blocks.pop()
                else:
                    self.blocks = [b for b in self.blocks if b is not block]
            return
        if tag in VOID_ELEMENTS:
            self._raw(raw, atomic=True)
            return
        self._raw(raw, atomic=True, after=max(0, self._depth - 1))
        self._depth = max(0, self._depth - 1)

    def _unwrap(self, block: _Block) -> None:
        """Put a wrapper's contents back where they were.

        A ``<div>`` is layout almost always and content just often enough to
        matter, and which one it is cannot be known until it closes. So one
        is opened as a block on approval and, if it turns out to hold
        anything other than a single display formula, taken apart again —
        its pieces returned to its parent exactly as they arrived, with its
        own tags as ordinary markup around them.

        The alternative was to narrate every ``<div>``, which changes what
        is read on every page ever built with this, for the sake of the few
        that put a formula in one.
        """
        target = self._open[-1].pieces if self._open else self.out
        for index in range(len(target) - 1, -1, -1):
            if target[index].child is block:
                target[index : index + 1] = [
                    _Piece(block.open_raw, atomic=True, depth=target[index].depth),
                    *block.pieces,
                    _Piece(block.close_raw, atomic=True, depth=target[index].depth),
                ]
                return

    def _close_sup(self) -> None:
        """Decide whether the superscript that just closed was a reference.

        The test is what it contains, not what it is called. A ``<sup>``
        whose whole visible content is a number -- bare, bracketed, or
        parenthesised -- is a footnote marker in every convention that
        writes one: Markdown's ``<sup><a href="#fn1">1</a></sup>``,
        Wikipedia's ``[1]``, and a hand-written page's plain ``1``. A
        ``<sup>`` holding ``2`` as an exponent is the same shape, and that
        is a real limit of this test: ``x`` followed by a superscript 2 is
        indistinguishable from a reference without reading the href or the
        surrounding prose. Erring toward "reference" costs a spoken
        exponent; erring the other way puts a number in the middle of every
        citation. Pages with exponents in prose are rarer than pages with
        footnotes.
        """
        assert self._sup_from is not None
        target = self._open[-1].pieces if self._open else self.out
        inside = target[self._sup_from + 1 : -1]
        text = "".join(piece.visible for piece in inside).strip()
        if _REFERENCE_MARKER.fullmatch(text):
            for piece in inside:
                piece.reference = True
                for href in re.findall(r'href="#([^"]+)"', piece.raw):
                    self.reference_targets.add(href)
        self._sup_from = None

    def handle_data(self, data: str) -> None:
        if self._skip or self._hidden_at is not None:
            self._raw(data, atomic=True)
            return
        # Tildes are markup this renderer leaves behind; they are emitted as
        # they stand but must not count as words.
        self._raw(data, _TILDES.sub("", data))

    def handle_entityref(self, name: str) -> None:
        self._raw(f"&{name};", html.unescape(f"&{name};"), atomic=True)

    def handle_charref(self, name: str) -> None:
        self._raw(f"&#{name};", html.unescape(f"&#{name};"), atomic=True)

    def handle_comment(self, data: str) -> None:
        self._raw(f"<!--{data}-->", atomic=True)

    def handle_decl(self, decl: str) -> None:
        self._raw(f"<!{decl}>", atomic=True)

    def handle_pi(self, data: str) -> None:
        self._raw(f"<?{data}>", atomic=True)

    def unknown_decl(self, data: str) -> None:
        self._raw(f"<![{data}]>", atomic=True)


def _walk(body_html: str, scope: str | None = None) -> _PageWalker:
    """Parse a rendered page into blocks and pieces.

    The notes are marked here rather than by each caller, so the narration
    and the page that follows it cannot disagree about what is read. A
    block skipped by one and not the other puts every later cue out by one,
    and `align` would refuse the build — the safe failure, but still a
    build that does not happen.
    """
    walker = _PageWalker(scope)
    walker.feed(body_html)
    walker.close()
    _mark_notes(walker.blocks, walker.reference_targets)
    return walker


def page_blocks(body_html: str, *, scope: str | None = None) -> list[_Block]:
    """The narrated blocks of a rendered page that show words, in reading order."""
    return [block for block in _walk(body_html, scope).blocks if block.visible and block.narrated]


def page_sentences(
    body_html: str, *, split: SentenceSplitter, scope: str | None = None
) -> list[str]:
    """Every sentence the page shows, in reading order.

    Separate from :func:`wrap_sentences` so the agreement between a page and
    its narration can be checked -- in a test, or before a build commits to
    narrating a post -- without producing any markup.
    """
    return [
        sentence
        for block in page_blocks(body_html, scope=scope)
        for sentence in split(block.visible)
    ]


# ── Matching cues to sentences ─────────────────────────────────────────────


def _unframe(text: str, opening: str, closing: str) -> str | None:
    """A cue's text as the page shows it, or ``None`` if the page never shows it.

    The narration's quotation framing is the only thing standing between the
    two: ``Quote:`` is spoken before a quoted block and ``End quote.`` after
    it, and neither is on the page.
    """
    stripped = " ".join(text.split())
    if stripped == closing:
        return None
    if stripped.startswith(opening):
        return stripped[len(opening) :].strip()
    return stripped


def align(
    blocks: list[_Block], cues: list[VttCue], *, split: SentenceSplitter, opening: str, closing: str
) -> list[list[list[VttCue]]]:
    """Match each block's sentences to the cues that speak them.

    Returns
    -------
    list of list of list of VttCue
        Per block, per sentence, the cues that speak it -- normally exactly
        one, and more when the narration added framing words of its own.

    Raises
    ------
    ReadAlongMismatch
        If the page's sentences are not the narration's sentences. The
        message names the first one that differs, because "they diverged
        somewhere" is not actionable.
    """
    assignments: list[list[list[VttCue]]] = []
    position = 0
    numbered = 0
    reading: list[VttCue] | None = None

    def _absorb_framing() -> None:
        """Hand a framing cue to whatever sentence is being read."""
        nonlocal position
        while position < len(cues) and _unframe(cues[position].text, opening, closing) is None:
            if reading is not None:
                reading.append(cues[position])
            position += 1

    for block in blocks:
        per_sentence: list[list[VttCue]] = []
        for sentence in split(block.visible):
            _absorb_framing()
            spoken = (
                _unframe(cues[position].text, opening, closing) if position < len(cues) else None
            )
            if spoken != sentence:
                heard = (
                    repr(cues[position].text)
                    if position < len(cues)
                    else "(nothing left in the audio)"
                )
                raise ReadAlongMismatch(
                    f"the page and the narration disagree at sentence {numbered}: "
                    f"page says {sentence!r}, audio says {heard}. "
                    f"The narration has {len(cues)} cues."
                )
            reading = [cues[position]]
            per_sentence.append(reading)
            position += 1
            numbered += 1
        assignments.append(per_sentence)

    _absorb_framing()
    if position != len(cues):
        raise ReadAlongMismatch(
            f"the narration has {len(cues) - position} cue(s) the page shows no sentence "
            f"for, starting with {cues[position].text!r}. "
            f"The page has {numbered} sentences."
        )
    return assignments


# ── Wrapping ───────────────────────────────────────────────────────────────


def _render(pieces: list[_Piece], wrapped: dict[int, str]) -> str:
    """Serialise pieces, replacing each nested block with its wrapped form."""
    out: list[str] = []
    for piece in pieces:
        if piece.child is None:
            out.append(piece.raw)
            continue
        block = piece.child
        out.append(block.open_raw)
        out.append(wrapped.get(id(block), _render(block.pieces, wrapped)))
        out.append(block.close_raw)
    return "".join(out)


def _visible_count(text: str) -> int:
    """Characters a comparison can see: no whitespace, no leftover tildes."""
    return sum(1 for char in text if not char.isspace() and char != "~")


def _cut(piece: _Piece, needed: int) -> tuple[_Piece, _Piece | None, int]:
    """Cut a text piece after ``needed`` visible characters.

    Returns the part that closes the current sentence, the remainder (or
    ``None`` when the piece is used up), and how many visible characters were
    taken. Atomic pieces are never cut: they go whole or not at all.
    """
    counted = _visible_count(piece.visible)
    if piece.atomic or counted <= needed:
        return piece, None, counted

    taken = 0
    cut = len(piece.raw)
    for index, char in enumerate(piece.raw):
        if taken == needed:
            cut = index
            break
        if not char.isspace() and char != "~":
            taken += 1
    head, tail = piece.raw[:cut], piece.raw[cut:]
    return (
        _Piece(head, _TILDES.sub("", head), depth=piece.depth, after=piece.after),
        _Piece(tail, _TILDES.sub("", tail), depth=piece.depth, after=piece.after),
        taken,
    )


def _span_runs(taken: list[_Piece]) -> list[tuple[bool, list[_Piece]]] | None:
    """Split a sentence's pieces into the runs a span can legally wrap.

    Usually there is one run and it is the whole sentence, markup and all.
    The exception is a sentence that crosses a boundary between elements. A
    bibliography entry ends ``…</cite> <span class="note">Keeps a memory…``
    with no full stop in between, so what a reader hears as one sentence runs
    out of the citation and into the note; and ``A <em>sentence that. Ends</em>
    here.`` puts one ``<em>`` across two of them. No single element can hold
    either -- a span cannot close a tag it did not open -- so the sentence is
    wrapped in *several*, which carry the same cue and light up together.

    That is a capability, not a compromise: the spans still cover exactly the
    sentence's own words, which is the whole promise. What is refused is a
    split that would leave some of those words outside every span, because a
    highlight that quietly drops half a sentence is the wrongness this module
    exists to prevent.

    Returns
    -------
    list of (bool, list of _Piece), or None
        ``True`` for a run to wrap, ``False`` for pieces to emit untouched,
        in document order. ``None`` when no split covers every word.
    """
    base = taken[0].depth
    if taken[-1].after == base and all(
        piece.depth >= base and piece.after >= base for piece in taken
    ):
        # The ordinary case, and the one every Markdown page takes.
        return [(True, taken)]

    out: list[tuple[bool, list[_Piece]]] = []
    pending = list(taken)
    while pending:
        # A tag shows no words, so it cannot decide the depth a span lives
        # at: it is emitted exactly where the page already had it. Whitespace
        # between two elements is skipped for the same reason -- a span around
        # a space highlights nothing.
        if _visible_count(pending[0].visible) == 0:
            out.append((False, [pending.pop(0)]))
            continue
        current = pending[0].depth
        # The longest prefix that never leaves the element the run starts in,
        # trimmed back to where it closes everything it opened.
        end = 1
        while (
            end < len(pending) and pending[end].depth >= current and pending[end].after >= current
        ):
            end += 1
        run = pending[:end]
        while run and run[-1].after != current:
            run.pop()
        if not run:
            out.append((False, [pending.pop(0)]))
            continue
        out.append((True, run))
        # Whatever was trimmed stays in `pending` and is reconsidered: it is
        # the start of the next run, not something to drop.
        del pending[: len(run)]

    spilled = any(
        not is_span and any(_visible_count(piece.visible) for piece in pieces)
        for is_span, pieces in out
    )
    return None if spilled or not any(is_span for is_span, _ in out) else out


def _wrap_block(
    block: _Block,
    per_sentence: list[list[VttCue]],
    wrapped: dict[int, str],
    *,
    split: SentenceSplitter,
) -> str:
    """Wrap one block's sentences, keeping the inline markup it already has."""
    queue = list(block.pieces)
    out: list[str] = []

    for sentence, cues in zip(split(block.visible), per_sentence):
        needed = _visible_count(sentence)
        # A nested block before the sentence's first word stays outside the
        # span: one that opened on a nested list would highlight every item
        # of it for the sake of one. Inline markup is the opposite case --
        # ``<strong>`` opening the sentence belongs *inside*, or the span
        # would close the tag it never opened.
        while queue and queue[0].child is not None:
            out.append(_render([queue.pop(0)], wrapped))
        taken: list[_Piece] = []
        while needed > 0 and queue:
            head, tail, got = _cut(queue[0], needed)
            taken.append(head)
            if tail is None:
                queue.pop(0)
            else:
                queue[0] = tail
            needed -= got
        if not taken:
            continue
        # Swallow the tags that close what the sentence opened: a heading
        # that is entirely a link stops on the link text, one piece short of
        # its own ``</a>``. Kept only if it balances the run, because the next
        # tag along may be an *opening* one, which would leave the span worse
        # off than it started.
        opened_at = taken[0].depth
        if taken[-1].after != opened_at:
            held = len(taken)
            while (
                taken[-1].after != opened_at
                and queue
                and queue[0].child is None
                and _visible_count(queue[0].visible) == 0
            ):
                taken.append(queue.pop(0))
            if taken[-1].after != opened_at:
                queue[:0] = taken[held:]
                del taken[held:]
        runs = _span_runs(taken)
        if runs is None:
            raise ReadAlongMismatch(
                f"the sentence {sentence!r} opens and closes at different inline-markup "
                "depths, so a span around it would cross an element. Emphasis that "
                "straddles a sentence boundary cannot be highlighted sentence by "
                "sentence; rephrase the source, or narrow --scope to leave it out."
            )
        cue = cues[0]
        # ``data-ra-cue`` is written only when the sentence needed more than
        # one span, because it costs bytes on every sentence of every page and
        # earns them on very few. The id stays on the first run: it is where
        # the sentence starts, and what the player scrolls to.
        spans = sum(1 for is_span, _ in runs if is_span)
        marker = f' data-ra-cue="{cue.index}"' if spans > 1 else ""
        first = True
        for is_span, pieces in runs:
            if not is_span:
                out.append(_render(pieces, wrapped))
                continue
            identity = f' id="ra-{cue.index}"' if first else ""
            out.append(
                f'<span class="{SENTENCE_CLASS}"{identity}{marker} '
                f'data-start="{cue.start_seconds:.3f}">' + _render(pieces, wrapped) + "</span>"
            )
            first = False
    out.append(_render(queue, wrapped))
    return "".join(out)


def wrap_sentences(
    body_html: str,
    cues: list[VttCue],
    *,
    split: SentenceSplitter,
    opening: str,
    closing: str,
    scope: str | None = None,
) -> str:
    """Wrap each narrated sentence in a span the highlight can find.

    Parameters
    ----------
    body_html : str
        Rendered page body.
    cues : list of VttCue
        What the narration actually said, in order.
    split : callable
        ``_narrate.split_sentences``. Passed in rather than imported so this
        module stays testable on its own and so there is visibly *one*
        splitter rather than two that happen to agree today.
    opening, closing : str
        ``_narrate.QUOTE_OPENING`` and ``_narrate.QUOTE_CLOSING`` -- the words
        the narration says around a quotation and the page does not show.
        Passed in for the same reason as the splitter.

    Returns
    -------
    str
        The body with every narrated sentence wrapped.

    Raises
    ------
    ReadAlongMismatch
        If the page's sentences are not the narration's sentences.
    """
    walker = _walk(body_html, scope)
    blocks = [block for block in walker.blocks if block.visible and block.narrated]
    assignments = align(blocks, cues, split=split, opening=opening, closing=closing)

    # Innermost first, so a parent's render finds its children already
    # wrapped rather than re-wrapping them.
    wrapped: dict[int, str] = {}
    for block, per_sentence in reversed(list(zip(blocks, assignments))):
        wrapped[id(block)] = _wrap_block(block, per_sentence, wrapped, split=split)
    return _render(walker.out, wrapped)


_HEAD_CLOSE = re.compile(r"</head\s*>", re.I)


def inject_player_only(
    html_text: str,
    *,
    scope: str | None,
    head: str,
    player: str,
) -> str:
    """The page with the player added and nothing else touched.

    What ``--no-follow`` builds. Not a degraded mode: the article keeps its
    own markup exactly, so nothing in it can go stale when the prose is
    edited later — which is the honest half of the objection to a highlight
    that follows the voice. The player still works; what it does not do is
    light the page up.
    """
    walker = _walk(html_text, scope)
    anchor = walker.scope_piece or walker.body_piece
    if anchor is None:
        raise ReadAlongMismatch(
            "nowhere to put the player: the page has no <body> and no element "
            f"matching {scope!r}. Pass a scope that the page actually contains."
        )
    anchor.raw += "\n" + player
    out = _render(walker.out, {})
    if head:
        if _HEAD_CLOSE.search(out):
            out = _HEAD_CLOSE.sub(lambda m: head + "\n" + m.group(0), out, count=1)
        else:
            out = head + "\n" + out
    return out


def inject_into_page(
    html: str,
    cues: list[VttCue],
    *,
    split: SentenceSplitter,
    opening: str,
    closing: str,
    scope: str | None = None,
    head: str = "",
    player: str = "",
) -> str:
    """Add a read-along to a page that already exists.

    The counterpart to building a page from Markdown: here the document is
    the input, and it comes back with its sentences wrapped, the stylesheet
    and module in its ``<head>``, and the player at the top of the article.
    Everything else is returned byte for byte -- the page is rebuilt from a
    parse of itself, so a hand-written document keeps its own markup,
    attribute order and entities.

    This is the case the feature is for. A page that was never Markdown is a
    page nobody can regenerate, which is exactly the page that most needs an
    accessibility pass it can receive without being rewritten.

    Parameters
    ----------
    html : str
        The whole document.
    cues : list of VttCue
        What the narration said, in order.
    split : callable
        ``_narrate.split_sentences``.
    opening, closing : str
        ``_narrate.QUOTE_OPENING`` / ``QUOTE_CLOSING``.
    scope : str, optional
        ``article``, ``#id`` or ``.class`` -- the element to read. Without
        it the whole document is read, header and footer included, which is
        rarely what a reader asked for.
    head : str
        Markup for the document head, usually the stylesheet and module
        links. Placed before ``</head>``, or at the very top when the input
        is a fragment with no head at all.
    player : str
        The player markup, placed immediately after the scope element's
        opening tag -- top of the article, which is this skill's placement
        rule -- or after ``<body>`` when there is no scope.

    Returns
    -------
    str
        The page, with the read-along in it.
    """
    walker = _walk(html, scope)
    blocks = [block for block in walker.blocks if block.visible and block.narrated]
    assignments = align(blocks, cues, split=split, opening=opening, closing=closing)

    wrapped: dict[int, str] = {}
    for block, per_sentence in reversed(list(zip(blocks, assignments))):
        wrapped[id(block)] = _wrap_block(block, per_sentence, wrapped, split=split)

    if player:
        anchor = walker.scope_piece or walker.body_piece
        if anchor is None:
            raise ReadAlongMismatch(
                "nowhere to put the player: the page has no <body> and no element "
                f"matching {scope!r}. Pass a scope that the page actually contains."
            )
        # Mutating the piece rather than the rebuilt string: the piece is the
        # one place that is certainly this element's start tag, where a
        # pattern over the output would have to guess among several.
        anchor.raw += "\n" + player
    out = _render(walker.out, wrapped)

    if head:
        if _HEAD_CLOSE.search(out):
            out = _HEAD_CLOSE.sub(lambda m: head + "\n" + m.group(0), out, count=1)
        else:
            out = head + "\n" + out
    return out


# ── Wiring a page to a narration run ───────────────────────────────────────

#: Wording for the player's label, which is the accessible name of the audio
#: element. No default: a language this project has not been taught is worth
#: seeing, not worth serving in English.
# ── The page's own colours ─────────────────────────────────────────────────
#
# The player used to pick its accent from a constant. That is the safe
# choice and the wrong one: a control dropped into somebody's article should
# look like it belongs to that article, and the article has already decided
# what its colours are.
#
# What can be read, and what cannot. A build tool has the page's markup and
# whatever stylesheets resolve to files beside it; it does not have a
# browser, so it cannot ask for a computed style. Everything here works from
# declarations as written.

#: Colour literals, in the three spellings a stylesheet uses.
_COLOUR = re.compile(
    r"#(?P<hex>[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b"
    r"|rgba?\((?P<rgb>[^)]*)\)"
)

#: One `property: value` pair, from an inline style or a rule body.
_DECLARATION = re.compile(r"(?P<prop>[-a-zA-Z]+)\s*:\s*(?P<value>[^;}]*)")

#: Below this chroma a colour is a grey, a near-white or a near-black, and
#: taking it as "the page's accent" would reproduce exactly the problem this
#: is here to solve.
_MIN_CHROMA: int = 24

#: Contrast a fill must reach against the page behind it. 3:1 is the WCAG
#: threshold for a non-text interface element — a play button is not text,
#: but it is the thing a reader has to find.
_MIN_FILL_CONTRAST: float = 3.0


def _parse_colour(text: str) -> tuple[int, int, int] | None:
    """One CSS colour to RGB, or ``None`` if it is not one we read."""
    match = _COLOUR.match(text.strip())
    if match is None:
        return None
    if match.group("hex"):
        digits = match.group("hex")
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return tuple(int(digits[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    parts = [p.strip() for p in re.split(r"[,/\s]+", match.group("rgb")) if p.strip()]
    if len(parts) < 3:
        return None
    try:
        channels = [int(round(float(p.rstrip("%")) * (2.55 if "%" in p else 1))) for p in parts[:3]]
    except ValueError:
        return None
    # A fully transparent colour is not a colour anybody sees.
    if len(parts) > 3:
        try:
            if float(parts[3].rstrip("%")) <= (5 if "%" in parts[3] else 0.05):
                return None
        except ValueError:
            pass
    return tuple(max(0, min(255, c)) for c in channels)  # type: ignore[return-value]


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _chroma(rgb: tuple[int, int, int]) -> int:
    """How far from grey. Max channel minus min, which is enough here."""
    return max(rgb) - min(rgb)


def _relative_luminance(rgb: tuple[int, int, int]) -> float:
    def channel(value: int) -> float:
        v = value / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    red, green, blue = rgb
    return 0.2126 * channel(red) + 0.7152 * channel(green) + 0.0722 * channel(blue)


def contrast(one: tuple[int, int, int], other: tuple[int, int, int]) -> float:
    """WCAG contrast ratio between two colours."""
    first, second = _relative_luminance(one), _relative_luminance(other)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def _declared_colours(css: str) -> list[tuple[str, tuple[int, int, int]]]:
    """Every colour a stylesheet actually paints with.

    The distinction that makes this work: a colour on the right of a
    **custom property definition** is skipped, a colour inside a real
    declaration is kept. `--framer-link-text-color: rgb(0, 153, 255)` is a
    framework default sitting on every rich-text block of the page, and the
    site overrides it — the rendered links are near-black. Counting
    occurrences without that rule picks the blue thirty-one times over and
    dresses the player in a colour that appears nowhere on the page.

    A `var(--token, #F7FABE)` fallback *inside* a real property is kept, and
    deliberately: that is how a design tool writes a token, and a named
    token is about as close to "the author chose this" as a stylesheet gets.
    """
    found: list[tuple[str, tuple[int, int, int]]] = []
    for declaration in _DECLARATION.finditer(css):
        prop = declaration.group("prop").lower()
        value = declaration.group("value")
        for piece in _COLOUR.finditer(value):
            colour = _parse_colour(piece.group(0))
            if colour is not None:
                found.append((prop, colour))
    return found


def local_stylesheets(html_text: str, page: Path, root: Path | None = None) -> list[str]:
    """The text of every stylesheet the page links that is a file on disk.

    A page's colours mostly live in its stylesheet, not in its markup, so
    reading only the HTML sees a fraction of the palette — on a page built
    by a design tool, often just the inline tokens. This reads the rest
    where it can.

    Where it can is the limit worth stating. A build tool has files, not a
    browser: a stylesheet on a CDN, or one served from a host that is not
    this build, is simply not available, and nothing here goes to the
    network to get it. Root-relative hrefs are resolved against ``root``
    when given — that is the site directory in a normal build — and against
    the page's own directory otherwise.
    """
    found: list[str] = []
    for href in re.findall(r'<link[^>]+rel="stylesheet"[^>]*>', html_text, re.I):
        match = re.search(r'href="([^"]+)"', href)
        if match is None:
            continue
        target = match.group(1).split("?")[0].split("#")[0]
        if "//" in target or target.startswith("data:"):
            continue
        bases = [page.parent] if not target.startswith("/") else []
        if root is not None:
            bases.append(root)
        for base in bases:
            candidate = (base / target.lstrip("/")).resolve()
            if candidate.is_file():
                try:
                    found.append(candidate.read_text(encoding="utf-8", errors="replace"))
                except OSError:  # pragma: no cover - unreadable file
                    pass
                break
    return found


def page_palette(html_text: str, *, stylesheets: Sequence[str] = ()) -> dict[str, str]:
    """The page's accent, ink and paper, as far as its own source tells.

    Returns a dict with whichever of ``accent``, ``ink`` and ``paper`` could
    be read, as ``#RRGGBB``. A page that says nothing useful returns an
    empty dict and the player keeps its own default rather than guessing.
    """
    sources = [
        *re.findall(r"<style[^>]*>(.*?)</style>", html_text, re.S),
        *(f"x{{{attr}}}" for attr in re.findall(r'style="([^"]*)"', html_text)),
        *stylesheets,
    ]
    counted: Counter[tuple[int, int, int]] = Counter()
    # Kept apart by the property that declared them, because luminance alone
    # gets a dark page exactly backwards: there the background is the dark
    # colour and the text the light one, so "dark means ink" would hand the
    # player the page's own background to paint a button with.
    grounds: Counter[tuple[int, int, int]] = Counter()
    inks: Counter[tuple[int, int, int]] = Counter()
    # Second-choice neutrals, read from custom property *definitions*.
    # Those are skipped for the accent, and for a good reason: a framework
    # default like `--framer-link-text-color` sits on every block of a page
    # and is then overridden, so counting it picks a colour painted
    # nowhere. The same caution would be too strict for ink and paper: a
    # design tool names its text colour in a token and consumes it through
    # `var()`, so refusing definitions outright leaves a page with obvious
    # black text looking like it never said so. Kept apart and used only
    # when the real declarations say nothing — and only for near-neutrals,
    # where being slightly wrong costs a shade of grey rather than a hue.
    named_grounds: Counter[tuple[int, int, int]] = Counter()
    named_inks: Counter[tuple[int, int, int]] = Counter()

    for source in sources:
        for prop, colour in _declared_colours(source):
            custom = prop.startswith("--")
            if not custom:
                counted[colour] += 1
            if _chroma(colour) >= _MIN_CHROMA:
                continue
            if "background" in prop:
                (named_grounds if custom else grounds)[colour] += 1
            elif "color" in prop:
                (named_inks if custom else inks)[colour] += 1

    grounds = grounds or named_grounds
    inks = inks or named_inks

    palette: dict[str, str] = {}
    coloured = [(n, c) for c, n in counted.items() if _chroma(c) >= _MIN_CHROMA]
    if coloured:
        # Frequency first, chroma to break ties: a page usually paints its
        # accent more than once, and when two are equally common the more
        # saturated one is the one being used *as* an accent.
        palette["accent"] = _hex(max(coloured, key=lambda pair: (pair[0], _chroma(pair[1])))[1])
    # Paper by frequency: a page paints its own background more often than
    # anything else paints a neutral one.
    if grounds:
        paper = grounds.most_common(1)[0][0]
        palette["paper"] = _hex(paper)
    else:
        paper = (255, 255, 255)

    # Ink by contrast against that paper, not by frequency and not by
    # darkness. Frequency picks the muted grey a page uses for captions —
    # sixteen occurrences against one for the body colour — and a grey
    # play button is the thing this whole pass exists to stop. Darkness
    # gets a dark page backwards. "The colour this page sets type in" is
    # "the one furthest from its background", and that holds either way up.
    if inks:
        palette["ink"] = _hex(max(inks, key=lambda c: contrast(c, paper)))
    return palette


def player_colours(palette: dict[str, str]) -> dict[str, str]:
    """Turn a page's palette into the two custom properties the player reads.

    Two, because an accent has two jobs and a page's accent is usually only
    good at one of them. ``--ra-accent`` fills the play button and the
    progress bar, so it has to carry contrast against the page. ``--ra-tint``
    washes the card and the read-along highlight, where a pale colour is
    exactly right.

    The live case: this site's accent is a pale chartreuse used as a chip
    background. As a wash it is the page's own voice; as a filled button it
    is 1.09:1 against white — invisible. So when the accent cannot carry a
    fill, the fill falls back to the page's ink and the accent stays where
    it works. That is not a compromise but the page's own arrangement: a
    pale chip with dark type on it.
    """
    accent = _parse_colour(palette.get("accent", ""))
    paper = _parse_colour(palette.get("paper", "")) or (255, 255, 255)
    ink = _parse_colour(palette.get("ink", ""))

    colours: dict[str, str] = {}
    # The page's own paper, whatever else is known. The bar sits over
    # scrolling text so it has to be opaque, and `Canvas` -- the browser's
    # idea of a page background -- is white on a page that is dark through
    # its own stylesheet without declaring `color-scheme`. That is not a
    # rare page; it is every hand-built dark theme.
    if palette.get("paper"):
        colours["--ra-paper"] = palette["paper"]
    if accent is None:
        return colours
    colours["--ra-tint"] = _hex(accent)
    if contrast(accent, paper) >= _MIN_FILL_CONTRAST:
        colours["--ra-accent"] = _hex(accent)
    elif ink is not None:
        colours["--ra-accent"] = _hex(ink)
    return colours


PLAYER_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "title": "Listen to this page",
        "play": "Play",
        "pause": "Pause",
        "back": "Back 15 seconds",
        "forward": "Forward 15 seconds",
        "speed": "Playback speed",
        "seek": "Seek",
    },
    "fr": {
        "title": "Écouter cette page",
        "play": "Lecture",
        "pause": "Pause",
        "back": "Reculer de 15 secondes",
        "forward": "Avancer de 15 secondes",
        "speed": "Vitesse de lecture",
        "seek": "Se déplacer dans la narration",
    },
}

#: Every control a language must name before a page in it can be narrated.
#: Checked rather than assumed: a missing key would reach the page as the
#: string "None" inside an `aria-label`, which is worse than English —
#: English at least tells a screen-reader user something.
PLAYER_STRING_KEYS: frozenset[str] = frozenset(
    {"title", "play", "pause", "back", "forward", "speed", "seek"}
)

#: The skip buttons' icon: an open ring with a gap at the top, an arrowhead
#: at one end of it, and nothing in the middle — because the middle is where
#: the number goes.
#:
#: Two versions of this were wrong before this one, and both only at real
#: size. The first was a filled disc with "15" laid over it: the number and
#: the glyph collided into a smudge. The second opened the ring but drew it
#: at radius 7 in a 24-unit box, which leaves about a pixel and a half of
#: clear space either side of the digits at the size these buttons are
#: actually drawn — the ring touched the number, and the arrowhead sat on
#: the ring's own end and made a blob of the join.
#:
#: So: radius 9.5, a seventy-degree gap at the top, a thin stroke, and the
#: arrowhead set at the end of the arc rather than on top of it. The
#: forward button is this same glyph mirrored in CSS, which is why the
#: number is an HTML element beside the SVG rather than a `<text>` inside
#: it: mirroring the ring is right, mirroring "15" is not.
_SKIP_GLYPH: str = (
    '        <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" '
    'fill="none" stroke="currentColor" stroke-width="1.5" '
    'stroke-linecap="round">'
    '<path d="M6.55 4.22A9.5 9.5 0 1 0 17.45 4.22"/>'
    '<path d="M7.4 0.9 2.3 4.3 7.4 7.7Z" fill="currentColor" stroke="none"/>'
    "</svg>"
)

#: How far the skip buttons jump. Fifteen seconds is what the podcast players
#: settled on, and the reason is worth keeping: it is long enough to undo a
#: lapse in attention and short enough that two taps are still a thought
#: rather than a navigation.
SKIP_SECONDS: int = 15

#: The speeds the rate button cycles through, starting at 1. No 2.5 or 3:
#: past about double, synthesised speech stops being faster reading and
#: becomes a different task.
PLAYBACK_RATES: tuple[float, ...] = (1.0, 1.25, 1.5, 1.75, 2.0, 0.75)

#: Files that drive the highlight, copied next to the page. Linked rather
#: than inlined so a reader's browser caches them once for a whole site.
ASSET_FILES: tuple[str, ...] = ("readalong.css", "readalong.js")


def assets_dir() -> Path:
    """Where the stylesheet and module that drive the highlight live."""
    return Path(__file__).resolve().parent.parent / "assets" / "readalong"


def player_strings(lang: str) -> dict[str, str]:
    """Every word the player shows or announces, in `lang`.

    Refuses rather than falling back. A player whose buttons are labelled in
    a language the page is not written in is worse than an unlabelled one:
    the screen-reader user hears confident, wrong words.
    """
    strings = PLAYER_LABELS.get(lang)
    if strings is None:
        raise ReadAlongMismatch(
            f"no read-along player wording for language {lang!r}; add it to "
            "PLAYER_LABELS rather than labelling a French page in English"
        )
    missing = PLAYER_STRING_KEYS - set(strings)
    if missing:
        raise ReadAlongMismatch(
            f"the {lang!r} player wording is missing {sorted(missing)}; a "
            f'missing key reaches the page as the string "None" inside an '
            f"aria-label, which tells a screen-reader user less than English "
            f"would"
        )
    return strings


def player_label(lang: str) -> str:
    """The player's accessible name in `lang`, or a refusal naming the gap."""
    return player_strings(lang)["title"]


def narration_sources(narration_dir: Path, stem: str) -> tuple[Path, Path] | None:
    """The audio file and cue file for one page, if a narration ran.

    Returns ``None`` when there is nothing to attach, which is the ordinary
    case: most pages of a site are not narrated, and a missing recording is
    not an error.

    Two filenames are accepted for the audio, and the second one is the
    repair. This looked only for ``<stem>.<ext>``, while ``narrate_post``
    writes ``narration.wav`` — so the two commands this module's own epilog
    documents back to back did not connect for any page not called
    "narration". And they failed in the shape that hides best: a missing
    recording is *not an error* here, by design, so the read-along was
    simply never attached and both commands reported success.

    ``<stem>.<ext>`` stays first so a site that already renamed its files
    keeps working. The cue file has always been fixed-name, which is the
    tell: a directory holding one ``narration.vtt`` holds one page's
    narration, so the audio beside it needs no key either.
    """
    cues = narration_dir / "narration.vtt"
    if not cues.is_file():
        return None
    audio = next(
        (
            candidate
            for name in (stem, "narration")
            for suffix in AUDIO_TYPES
            for candidate in [narration_dir / f"{name}{suffix}"]
            if candidate.is_file()
        ),
        None,
    )
    return None if audio is None else (audio, cues)


def copy_assets(out_dir: Path) -> None:
    """Put the stylesheet and module next to the page that links them."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in ASSET_FILES:
        shutil.copyfile(assets_dir() / name, out_dir / name)


def head_markup() -> str:
    """The two links a read-along page needs in its document head."""
    return (
        '  <link rel="stylesheet" href="readalong.css">\n'
        '  <script type="module" src="readalong.js"></script>'
    )


def href_from(path: Path, page_dir: Path) -> str:
    """`path` as the page's own HTML would reference it.

    Relative, so the output can be moved or served from a sub-path without a
    single link being rewritten.
    """
    return os.path.relpath(path.resolve(), page_dir.resolve()).replace(os.sep, "/")


def page_words(body_html: str, *, scope: str | None = None) -> list[str]:
    """The words the page shows, for a reading-time estimate.

    Counted from the same blocks the narration was built from, so the two
    figures on the page describe the same text: anything skipped by one --
    code, tables -- is skipped by both.
    """
    return [word for block in page_blocks(body_html, scope=scope) for word in block.visible.split()]


def spoken_seconds(vtt_text: str) -> float:
    """How long the narration runs, read off its last cue.

    Measured rather than estimated: the timeline counted samples as it laid
    the audio out, so the end of the final cue *is* the end of the recording.
    """
    cues = parse_vtt(vtt_text)
    return cues[-1].end_seconds if cues else 0.0


def _clock(seconds: float) -> str:
    """``64:03``, or ``1:04:03`` once there is an hour to show.

    No leading zero on the first field, which is what every player does and
    what makes ``0:09`` read as nine seconds rather than as a timestamp.
    """
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def player_html(
    *,
    audio_src: str,
    vtt_src: str,
    label: str,
    lang: str,
    duration_seconds: float = 0.0,
    meta_html: str = "",
    colours: dict[str, str] | None = None,
) -> str:
    """The audio player, with its cue track.

        ``kind="metadata"`` rather than ``"captions"``: these cues drive a
        highlight, they are not a caption overlay, and a browser showing them as
        subtitles over an audio element would be noise. The same file *is* served
        as captions elsewhere; what changes is the role it is given here.

        Shape
        -----
        Two players in one element, and only ever one of them visible.

        The ``<audio controls>`` is the page as delivered: it works with no
        JavaScript, no stylesheet, and no assumptions, and it is what a reader
        gets if either file fails to load. The ``ra-ui`` block beside it is the
        designed bar — a round play button, a scrubber, the clock, and the
        controls a long narration actually needs — and it ships ``hidden``. The
        module unhides it and hides the native controls in the same breath, so
        there is no moment where a reader sees two players, and no moment where
        they see none.

        Everything the bar says is rendered here rather than in the module. A
        string built in JavaScript is a string outside the language table, and
        this component already refuses to label a French page in English; it
        would be a strange thing to then do from a script.

    ``meta_html`` — the reading-and-listening line from
        :func:`listening_meta_html` — belongs *inside* the card. Emitted as a
        sibling it became an orphan: the host page puts its own spacing between
        flex children, so the line ended up floating halfway between the player
        and the headline, attached to neither. A child cannot shrink its
        parent's gap, and it should not try; the fix is to stop being a second
        child.

        The total duration is written in as well, from the narration's own
        measured length. ``preload="none"`` means the browser knows nothing about
        the file until the reader presses play, so a player that waited for
        metadata would show ``0:00`` next to a sixty-four-minute recording —
        exactly when a reader is deciding whether to commit to it.

        Raises
        ------
        ReadAlongMismatch
            If the audio file's extension is not one of :data:`AUDIO_TYPES`.
            Declaring the wrong type is a file the browser declines to play, and
            guessing is how that happens quietly.
            If `lang` has no wording — see :func:`player_strings`.
    """
    # The query and the fragment come off before the extension is read.
    # These two parameters are URLs rather than paths, and the recording now
    # travels under a content version, so `Path("...mp3?v=abc").suffix` is
    # ".mp3?v=abc" and the type lookup fails on a file whose type is in the
    # table. A src is allowed to carry a query; the type is decided by the
    # name under it.
    suffix = Path(audio_src.split("?", 1)[0].split("#", 1)[0]).suffix.lower()
    audio_type = AUDIO_TYPES.get(suffix)
    if audio_type is None:
        raise ReadAlongMismatch(
            f"no audio type known for {suffix or audio_src!r}; add it to AUDIO_TYPES "
            f"rather than letting the page declare the wrong one. "
            f"Known: {', '.join(sorted(AUDIO_TYPES))}."
        )
    words = player_strings(lang)
    total = _clock(duration_seconds)
    skip = SKIP_SECONDS
    # The page's own colours, when they could be read, as an inline
    # declaration on the player. Inline because this is a fact about *this*
    # page and belongs with it, not in a stylesheet shared by every page a
    # site has.
    style = "".join(f"{name}:{value};" for name, value in sorted((colours or {}).items()))
    style_attr = f' style="{html.escape(style, quote=True)}"' if style else ""

    def tag(text: str) -> str:
        return html.escape(text, quote=True)

    return (
        f'<div class="ra-player"{style_attr} data-readalong data-ra-skip="{skip}" '
        f'data-ra-rates="{",".join(str(r) for r in PLAYBACK_RATES)}" '
        f'data-ra-duration="{duration_seconds:.3f}">\n'
        f'  <p class="ra-title" id="ra-label">{html.escape(label)}</p>\n'
        '  <audio controls preload="none" aria-labelledby="ra-label" '
        "data-ra-audio>\n"
        f'    <source src="{html.escape(audio_src)}" type="{audio_type}">\n'
        f'    <track kind="metadata" src="{html.escape(vtt_src)}" '
        f'srclang="{html.escape(lang)}" label="Sentences" default>\n'
        "  </audio>\n"
        # `hidden` until the module is running. A designed bar with nothing
        # behind it is a worse failure than plain controls: it looks
        # operable and is not.
        '  <div class="ra-ui" data-ra-ui hidden>\n'
        # The scrubber rides the bar's top edge, which is what makes the bar
        # thin: a progress line is a line, and giving it a row of its own
        # costs twenty pixels of a page for nothing.
        f'    <input class="ra-scrub" type="range" min="0" max="1000" '
        f'value="0" step="1" data-ra-scrub aria-label="{tag(words["seek"])}" '
        f'aria-valuetext="0:00">\n'
        '    <div class="ra-row">\n'
        '      <button class="ra-play" type="button" data-ra-play '
        f'aria-label="{tag(words["play"])}" '
        f'data-ra-label-play="{tag(words["play"])}" '
        f'data-ra-label-pause="{tag(words["pause"])}"></button>\n'
        # No glyph element inside. The disc is drawn by CSS as a mask, so the
        # triangle is a *hole* in it rather than a shape painted on top —
        # which is the only version that survives being dropped into a page
        # whose background this component has never seen. See readalong.css.
        '      <span class="ra-said">\n'
        f'        <span class="ra-said-title">{html.escape(label)}</span>\n'
        '        <span class="ra-time" data-ra-elapsed>0:00</span>\n'
        f'        <span class="ra-time ra-time-total">{html.escape(total)}</span>\n'
        "      </span>\n"
        '      <span class="ra-tools">\n'
        '      <button class="ra-skip" type="button" data-ra-back '
        f'aria-label="{tag(words["back"])}">\n'
        f"{_SKIP_GLYPH}\n"
        # The sign is spelled out (U+2212, not a hyphen) and the unit too:
        # "15" alone made the reader guess the direction from the arrow,
        # and the arrow is the dimmest thing on the button by design.
        f'        <span class="ra-skip-n">\u2212{skip}s</span>\n'
        "      </button>\n"
        '      <button class="ra-skip ra-skip-fwd" type="button" '
        f'data-ra-forward aria-label="{tag(words["forward"])}">\n'
        f"{_SKIP_GLYPH}\n"
        f'        <span class="ra-skip-n">+{skip}s</span>\n'
        "      </button>\n"
        '      <button class="ra-rate" type="button" data-ra-rate '
        f'aria-label="{tag(words["speed"])}">1&#215;</button>\n'
        "      </span>\n"
        "    </div>\n"
        "  </div>\n"
        f"{meta_html}"
        "</div>"
    )


def _minutes(seconds: float) -> int:
    """Whole minutes, never zero -- "0 min read" tells a reader nothing."""
    return max(1, round(seconds / 60.0))


#: Whole minutes, per language. One number, not two: this line read
#: "45 min read · 64 min listen" and put an estimate beside a measurement,
#: inviting a comparison that can only come out one way.
_DURATION_PHRASES: dict[str, str] = {
    "en": "{minutes} min",
    "fr": "{minutes} min",
}


def listening_meta_html(*, spoken_seconds: float, lang: str) -> str:
    """How long the narration runs, as the one number worth showing.

    Measured, not estimated: the timeline counted samples as it laid the
    audio out, so the end of the final cue *is* the end of the recording.
    That is what makes it worth printing at all — it is the figure a reader
    uses to decide whether to commit to an hour.

    Marked up with ``<time datetime="PT…M">`` so the duration is machine
    readable. No role and no landmark: it is not a control, and announcing
    it as one would add noise for the screen-reader user this feature is
    careful not to disturb.
    """
    phrase = _DURATION_PHRASES.get(lang)
    if phrase is None:
        raise ReadAlongMismatch(
            f"no listening-time wording for language {lang!r}; add it to "
            "_DURATION_PHRASES rather than falling back to English"
        )
    minutes = _minutes(spoken_seconds)
    return (
        f'<p class="ra-meta"><time datetime="PT{minutes}M">'
        f"{html.escape(phrase.format(minutes=minutes))}</time></p>"
    )
