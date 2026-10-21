#!/usr/bin/env python3
"""
readalong — add a sentence-by-sentence read-along to a page that already exists.

The companion to ``md_to_html.py --readalong``, for the case that matters
more: a page nobody can regenerate. A hand-written HTML file, a template
exported from a design tool, a page that has been live for three years — none
of them has a Markdown source, and none of them should have to be rewritten
to gain an accessibility feature.

What it does
------------
Given a page and the output of a narration run, it returns the same page with

* ``<span class="ra-s" id="ra-12">`` around every narrated sentence;
* the player — ``<audio controls>`` plus ``<track kind="metadata">`` — at the
  top of the article;
* a reading time beside the measured listening time;
* ``readalong.css`` / ``readalong.js`` linked from the document head and
  copied next to the page.

Everything else comes back byte for byte. The page is rebuilt from a parse of
itself, so its own markup, attribute order and entities survive untouched.

Narrate first
-------------
::

    narrate_post.py page.html --scope article --out-dir audio/
    readalong.py page.html --narration audio/ --scope article --out built/

``narrate_post.py`` reads HTML directly: the structural hints come from the
page's own elements, so an ``<h2>`` earns the same pause a ``##`` would.

Why ``--scope``
---------------
A page written by hand carries a header, a navigation bar and a footer. A
reader who asked to hear *this article* did not ask for the navigation. Pass
``article``, ``#post`` or ``.entry-content`` and only that element is read.
Without it the whole document is, which is right for a page this project
rendered and wrong for almost any page it did not.

Why it can refuse
-----------------
The cues the narration wrote are compared, one by one, against the sentences
the page shows. They match, or this exits non-zero and names the first one
that differs. A highlight that is off by one tells a reader with confidence
to look at the wrong line, which is worse than no highlight at all.

On a page narrated through ``narrate_post.py``, the two come from a *single*
parse of that page, so they agree by construction. The comparison still runs,
because the page may have been edited since the recording — and then the
honest answer is that the recording is stale, not that the reader should be
pointed at the wrong sentence.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _narrate  # noqa: E402
import _readalong  # noqa: E402
from _argparse import make_parser  # noqa: E402
from _lang import detect_text_language  # noqa: E402


def build(page: Path, narration_dir: Path, out_dir: Path, *,
          scope: str | None, lang: str, follow: bool = True,
          stylesheets: tuple[Path, ...] = (), head: bool = True,
          href_base: str = "") -> Path:
    """Write `page` with its read-along into `out_dir`; return the new path.

    Parameters
    ----------
    page : Path
        The HTML document to wire up.
    narration_dir : Path
        A narration run: ``narration.vtt`` plus the audio named for the page.
    out_dir : Path
        Where the finished page and the two asset files go. The input is never
        modified in place -- a page that is live somewhere is not a draft.
    scope : str or None
        ``article``, ``#id`` or ``.class``: the element to read.
    lang : str
        BCP-47 language tag, for the player's accessible name and the wording
        of the duration.
    stylesheets : tuple of Path
        Extra stylesheets to read the page's colours from. A page built
        from a fragment and a site-wide stylesheet carries none of its own
        colours, so there is nothing to find in it; this is how the site
        hands them over.
    head : bool
        Whether to write the stylesheet and module links into the page. A
        templated site puts them in its layout once instead of in every
        page, and a fragment has no ``<head>`` for them to go in.
    href_base : str
        A URL prefix for the audio and the cues, instead of a path relative
        to the output file. A fragment is not served from where it is
        stored, so a relative path computed from disk points nowhere.
    follow : bool
        Whether the page follows the reading, sentence by sentence. On by
        default, and off is a supported shape rather than a degraded one.

        The objection to a following highlight is worth recording, because
        it is a real one: it needs a timestamp per sentence, so it is only
        as sound as the alignment behind it, and some readers who listen
        *and* read want to read ahead of the voice rather than be led by it.

        The first half is answered here — ``align`` compares every cue to
        its sentence and refuses to build a page rather than ship one whose
        highlight lands on the wrong words. The second half is a preference,
        and this is the switch for it. With ``follow=False`` the page gets
        the player and nothing else: no spans, no module work beyond the
        controls, and nothing to go stale if the prose is edited later.

    Raises
    ------
    FileNotFoundError
        If the narration directory holds no recording for this page.
    _readalong.ReadAlongMismatch
        If the page and the recording disagree about the sentences.
    """
    source = page.read_text(encoding="utf-8")
    found = _readalong.narration_sources(narration_dir, page.stem)
    if found is None:
        raise FileNotFoundError(
            f"no narration for {page.name} in {narration_dir}: expected "
            f"narration.vtt and {page.stem}<audio suffix>. "
            f"Run narrate_post.py on the page first."
        )
    audio, cues = found
    out_dir.mkdir(parents=True, exist_ok=True)

    vtt_text = cues.read_text(encoding="utf-8")
    # Read once and handed to both: the player shows it as a clock before any
    # audio is fetched, the caption as whole minutes. Two presentations of
    # one measurement.
    spoken = _readalong.spoken_seconds(vtt_text)
    meta = _readalong.listening_meta_html(spoken_seconds=spoken, lang=lang)
    # The meta line goes *inside* the player. Emitted beside it, the host
    # page's own spacing between blocks left it floating halfway to the
    # headline, attached to neither.
    # The player borrows the page's colours when the page says what they
    # are. Read from the markup and from whatever stylesheets resolve to
    # files beside it; a page that says nothing keeps the component's own
    # default rather than being dressed in a guess.
    palette = _readalong.page_palette(
        source,
        stylesheets=[
            *_readalong.local_stylesheets(source, page),
            *(sheet.read_text(encoding="utf-8", errors="replace")
              for sheet in stylesheets if sheet.is_file()),
        ],
    )
    player = _readalong.player_html(
        audio_src=(f"{href_base.rstrip('/')}/{audio.name}" if href_base
                   else _readalong.href_from(audio, out_dir)),
        vtt_src=(f"{href_base.rstrip('/')}/{cues.name}" if href_base
                 else _readalong.href_from(cues, out_dir)),
        label=_readalong.player_label(lang),
        lang=lang,
        duration_seconds=spoken,
        meta_html=meta,
        colours=_readalong.player_colours(palette),
    )
    if not follow:
        built = _readalong.inject_player_only(
            source, scope=scope,
            head=_readalong.head_markup() if head else "", player=player,
        )
    else:
        built = _readalong.inject_into_page(
            source,
            _readalong.parse_vtt(vtt_text),
            split=_narrate.split_sentences,
            opening=_narrate.QUOTE_OPENING,
            closing=_narrate.QUOTE_CLOSING,
            scope=scope,
            head=_readalong.head_markup() if head else "",
            player=player,
        )

    _readalong.copy_assets(out_dir)
    destination = out_dir / f"{page.stem}.html"
    destination.write_text(built, encoding="utf-8")
    return destination


def strip(page: Path, out_dir: Path) -> Path:
    """Write `page` without its read-along into `out_dir`; return the new path.

    The inverse of :func:`build`, and the first half of correcting a sentence
    in a page that already has a voice. The timings live in the page, one per
    sentence, so editing the prose moves every sentence after the edit out
    from under its timestamp. The repair is to take the player out, edit the
    prose, and record again -- in that order, because :func:`build` refuses
    to write markers over markers.

    The input is never modified in place, for the same reason as
    :func:`build`: a page that is live somewhere is not a draft.

    Returns the path written, and prints nothing: the caller decides what to
    say.
    """
    source = page.read_text(encoding="utf-8")
    stripped, markers = _readalong.strip_player(source)
    out_dir.mkdir(parents=True, exist_ok=True)
    destination = out_dir / page.name
    destination.write_text(stripped, encoding="utf-8")
    return destination


def check(page: Path, narration_dir: Path, *,
          tolerate: tuple[str, ...] = ()) -> list[str]:
    """What a shipped `page` and a shipped narration disagree about.

    :func:`build` already refuses to write markers onto prose that moved
    while the voice was recording. This is the other order of events, which
    nothing else catches: a page edited *after* its player was written in.
    The markers stay, their times stay, and every time now points at the
    wrong sentence. That is worse than no highlight, because it is
    confidently wrong, and no exception is raised anywhere to say so.

    So this reads only what was shipped and compares it to what was shipped
    beside it. Run it after every deploy that touched a narrated page; file
    sizes say nothing about alignment.

    Parameters
    ----------
    page : Path
        The page as served, markers and all.
    narration_dir : Path
        The narration run as served, holding ``narration.vtt``.
    tolerate : tuple of str
        Cue texts that legitimately carry no marker. A narration says "End
        quote." out loud after a block quotation, and those words are not on
        the page. Naming them is better than loosening the comparison.

    Returns one line per disagreement, and an empty list when the two agree.
    """
    cues = _readalong.parse_vtt(
        (narration_dir / "narration.vtt").read_text(encoding="utf-8"))
    return _readalong.disagreements(
        page.read_text(encoding="utf-8"), cues, tolerate=tolerate)


def main() -> int:
    """CLI entry point; returns a process exit code."""
    parser = make_parser(
        prog="sprezzature-publish-readalong",
        description="Add a sentence-by-sentence read-along to an existing HTML page.",
        epilog="Examples:\n"
               "  narrate_post.py page.html --scope article --out-dir audio/\n"
               "  readalong.py page.html --narration audio/ --scope article --out built/\n",
    )
    parser.add_argument("page", type=Path, help="HTML page to wire up.")
    parser.add_argument(
        "--narration", type=Path, default=None, dest="narration_dir",
        help="Directory holding the narration run (narration.vtt + the audio). "
             "Required except with --strip, which reads nothing but the page.",
    )
    parser.add_argument(
        "--out", type=Path, default=None, dest="out_dir",
        help="Output directory. The input page is never modified in place. "
             "Required except with --check, which writes nothing.",
    )
    parser.add_argument(
        "--strip", action="store_true",
        help="Take the read-along back out instead of putting it in. The "
             "first half of correcting a sentence in a page that already "
             "has a voice: strip, edit the prose, then record again. Needs "
             "--out and ignores --narration.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Compare a shipped page to its shipped cues and say nothing if "
             "they agree. Catches the one failure nothing else does: a page "
             "edited after its player was written in, whose every timestamp "
             "now points at the wrong sentence. Needs --narration and "
             "writes nothing.",
    )
    parser.add_argument(
        "--tolerate", action="append", default=[], metavar="TEXT",
        help="With --check: a cue text that legitimately carries no marker. "
             "A narration says 'End quote.' after a block quotation, and "
             "those words are not on the page. Repeatable.",
    )
    parser.add_argument(
        "--scope", default=None,
        help="Element to read: 'article', '#id' or '.class'. Without it the "
             "whole document is read, navigation and footer included.",
    )
    parser.add_argument(
        "--css", type=Path, action="append", default=[], dest="stylesheets",
        metavar="PATH",
        help="A stylesheet to read the page's colours from. Repeatable. For "
             "a page built from a fragment, which carries none of its own.",
    )
    parser.add_argument(
        "--no-head", action="store_true",
        help="Do not write the stylesheet and module links into the page. "
             "For a templated site that carries them in its layout.",
    )
    parser.add_argument(
        "--href-base", default="", metavar="URL",
        help="URL prefix for the audio and the cues, instead of a path "
             "relative to the output. For a page not served from where it "
             "is stored.",
    )
    parser.add_argument(
        "--no-follow",
        action="store_true",
        help="Add the player without the sentence-by-sentence highlight. A "
             "supported shape, not a degraded one: some readers want to read "
             "ahead of the voice rather than be led by it.",
    )
    parser.add_argument(
        "--lang", default="auto",
        help="BCP-47 language tag. Default: auto = detect from the page's text.",
    )
    args = parser.parse_args()

    if not args.page.is_file():
        print(f"readalong: no such page: {args.page}", file=sys.stderr)
        return 2

    if args.strip and args.check:
        print("readalong: --strip and --check do opposite things; pick one",
              file=sys.stderr)
        return 2

    if args.strip:
        if args.out_dir is None:
            print("readalong: --strip needs --out", file=sys.stderr)
            return 2
        before = args.page.read_text(encoding="utf-8")
        destination = strip(args.page, args.out_dir)
        _, markers = _readalong.strip_player(before)
        print(f"{args.page} \u2192 {destination}: "
              f"player out, {markers} markers unwrapped")
        return 0

    if args.check:
        if args.narration_dir is None:
            print("readalong: --check needs --narration", file=sys.stderr)
            return 2
        try:
            found = check(args.page, args.narration_dir,
                          tolerate=tuple(args.tolerate))
        except FileNotFoundError as missing:
            print(f"readalong: {missing}", file=sys.stderr)
            return 1
        if not found:
            print(f"{args.page}: page and cues agree")
            return 0
        print(f"{args.page}: {len(found)} disagreement(s)", file=sys.stderr)
        for line in found:
            print(f"  {line}", file=sys.stderr)
        return 1

    for name, value in (("--narration", args.narration_dir),
                        ("--out", args.out_dir)):
        if value is None:
            print(f"readalong: {name} is required", file=sys.stderr)
            return 2

    lang = args.lang
    if lang in ("", "auto"):
        # Detected from what the page *says*, not from a `lang` attribute: a
        # template exported from a design tool often carries the wrong one,
        # and the wording of "3 min listen" is the reader's, not the tool's.
        words = _readalong.page_words(
            args.page.read_text(encoding="utf-8"), scope=args.scope
        )
        lang = detect_text_language(" ".join(words))

    try:
        destination = build(
            args.page, args.narration_dir, args.out_dir,
            scope=args.scope, lang=lang, follow=not args.no_follow,
            stylesheets=tuple(args.stylesheets), head=not args.no_head,
            href_base=args.href_base,
        )
    except (FileNotFoundError, _readalong.ReadAlongMismatch) as failure:
        print(f"readalong: {failure}", file=sys.stderr)
        return 1

    if args.no_follow:
        print(f"{args.page} → {destination}: player only, lang={lang}")
        return 0
    sentences = len(_readalong.page_sentences(
        args.page.read_text(encoding="utf-8"),
        split=_narrate.split_sentences, scope=args.scope,
    ))
    print(f"{args.page} → {destination}: {sentences} sentences wrapped, lang={lang}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
