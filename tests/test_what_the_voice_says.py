"""
Where the page and the narration stop being the same text.

A page is read with the eyes and a narration with the ears, and three things
on a page are written for the eye alone: a footnote marker, a formula, and
the typography around them. Reading them out literally is not fidelity — it
is a machine reading markup aloud. "The Ralph technique one, after Ralph
Wiggum" is a sentence about a version number; "backslash, open parenthesis,
R equals T underscore" is not a sentence at all.

The rule the whole thing rests on: **the cue keeps the page's words.** Only
the string handed to the speech engine changes. That is what lets a
read-along highlight exactly what a reader sees while the voice says
something a person would say — and it is the invariant most at risk from a
well-meaning edit, so it is checked first.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import pytest

import _readalong
from _narrate import explode_to_sentences, segments_from_blocks
from _speech_text import NARRATE_ABOVE, SpeechMismatch, complexity, speak_math, speakable

PAGE = (
    "<article>"
    '<p>He calls it the Ralph technique<sup><a href="#ref-1">1</a></sup>, '
    "after Ralph Wiggum.</p>"
    r"<p>Write \(T_{AB}\) for the translation and \(R = T_{BA} \circ T_{AB}\) "
    "for the round trip.</p>"
    "</article>"
)


def _both(html: str) -> list[tuple[str, str]]:
    """Every sentence as the page shows it, beside what the voice says."""
    blocks = _readalong.page_blocks(html, scope="article")
    page = explode_to_sentences(
        segments_from_blocks([(b.tag, b.visible, b.in_quote) for b in blocks])
    )
    said = explode_to_sentences(
        segments_from_blocks([(b.tag, b.spoken, b.in_quote) for b in blocks])
    )
    assert len(page) == len(said)
    return [(p["text"], speakable(s["text"], "en")) for p, s in zip(page, said)]


# ── The invariant ──────────────────────────────────────────────────────────


def test_the_page_keeps_every_word_it_shows() -> None:
    """
    The cue text is the page text, always. Change this and the read-along
    stops highlighting what the reader is looking at — and it fails
    silently, because `align` compares strings and would simply refuse to
    build rather than build something wrong. That is the better failure,
    but it is still a build that does not happen.
    """
    shown = [page for page, _ in _both(PAGE)]
    assert "technique1" in shown[0]
    assert r"\(T_{AB}\)" in shown[1]


# ── Footnote markers ───────────────────────────────────────────────────────


def test_a_footnote_marker_is_not_spoken() -> None:
    """
    It is a signpost to the bottom of the page. Read aloud it lands glued to
    the word before it, and the listener hears a number with no idea what it
    refers to. Nothing is lost: the note it points at is read in its place.
    """
    page, said = _both(PAGE)[0]
    assert "technique1" in page
    assert "technique," in said
    assert "1" not in said


@pytest.mark.parametrize(
    ("inner", "spoken"),
    [
        ("1", False),          # a plain marker
        ("[12]", False),       # the bracketed convention
        ("(3)", False),        # and the parenthesised one
        ("n", True),           # an exponent, which is content
        ("th", True),          # an ordinal
        ("note", True),        # a word is a word
    ],
)
def test_a_superscript_is_judged_by_what_it_holds(inner: str, spoken: bool) -> None:
    """
    By content, not by class name. Markdown writes
    `<sup><a href="#fn1">1</a></sup>`, Wikipedia writes `[1]`, a hand-made
    page writes `1` — and none of them agree on a class to look for. A
    superscript whose whole content is a number is a reference in every one
    of those conventions.
    """
    html = f"<article><p>Before<sup>{inner}</sup> after.</p></article>"
    block = _readalong.page_blocks(html, scope="article")[0]
    assert (inner in block.spoken) is spoken


def test_an_exponent_in_prose_is_the_known_limit() -> None:
    """
    States the cost rather than hiding it: `x<sup>2</sup>` has the same
    shape as a reference and is treated as one. Erring this way costs a
    spoken exponent; erring the other way puts a stray number in the middle
    of every citation on the page, and footnotes are far more common in
    prose than exponents.
    """
    block = _readalong.page_blocks(
        "<article><p>Take x<sup>2</sup> here.</p></article>", scope="article"
    )[0]
    assert block.visible == "Take x2 here."
    assert block.spoken == "Take x here."


# ── Mathematics ────────────────────────────────────────────────────────────


def test_a_formula_becomes_a_sentence() -> None:
    page, said = _both(PAGE)[1]
    assert "\\" in page
    assert "\\" not in said
    assert "T A B" in said
    assert "composed with" in said


@pytest.mark.parametrize(
    ("latex", "expected"),
    [
        ("R", "R"),
        ("T_{AB}", "T A B"),
        (r"x^2", "x squared"),
        (r"x^3", "x cubed"),
        (r"x^{n+1}", "x to the power of n plus 1"),
        (r"\frac{a}{b}", "a over b"),
        (r"\sqrt{2\ln K}", "the square root of 2 log K"),
        (r"\sigma \neq \tau", "sigma is not equal to tau"),
    ],
)
def test_the_common_notation_reads_as_a_person_would_say_it(
    latex: str, expected: str
) -> None:
    assert speak_math(latex, "en") == expected


def test_subscript_letters_are_spelled_out() -> None:
    """
    `T_{AB}` read as "T ab" turns an index into a syllable. Digits are left
    alone: "x 12" is a number, not one and two.
    """
    assert speak_math("T_{AB}", "en") == "T A B"
    assert speak_math("x_{12}", "en") == "x 12"


def test_an_unknown_command_loses_its_backslash_rather_than_its_meaning() -> None:
    """
    Spelling `\\foo` out is the failure this module exists to remove, so the
    fallback is to say the word — wrong far less often than wrong in every
    case.
    """
    assert "backslash" not in speak_math(r"\foo", "en")
    assert speak_math(r"\foo", "en") == "foo"


def test_display_maths_is_read_like_inline_maths() -> None:
    """
    A formula on its own line is still a sentence, and a listener cannot see
    the line break that made it display maths.
    """
    assert speakable(r"Then \[R = 1\] holds.", "en") == "Then R equals 1 holds."
    assert speakable("Then $$R = 1$$ holds.", "en") == "Then R equals 1 holds."


# ── In the language the page is written in ─────────────────────────────────


def test_a_french_page_hears_french_operators() -> None:
    """
    The language comes from `langdetect` via the shared `_lang` helper, the
    same way an alt text or a caption gets one. A French page read with
    English operator names is worse than silence: the listener hears fluent
    words in the wrong language and assumes they misheard.
    """
    assert speakable(r"La borne vaut \(\sqrt{2\ln K}\).", "fr") == (
        "La borne vaut la racine carrée de 2 log K."
    )
    assert speak_math(r"R = T_{BA} \circ T_{AB}", "fr") == (
        "R égale T B A composé avec T A B"
    )


def test_a_language_with_no_vocabulary_is_refused() -> None:
    with pytest.raises(SpeechMismatch, match="no spoken maths vocabulary"):
        speakable(r"\(R\)", "de")


def test_a_page_without_maths_never_asks_about_the_language() -> None:
    """
    The refusal must not fire on every page in a language the maths table
    has never heard of. Most pages have no formula at all.
    """
    assert speakable("Plain prose, nothing to read.", "de") == (
        "Plain prose, nothing to read."
    )


# ── When spelling is not reading ───────────────────────────────────────────


def test_complexity_separates_the_two_kinds_of_formula() -> None:
    """
    `R` and `R = T_{BA} \\circ T_{AB}` are both fine spelled out. A nested
    fraction of sums is not: the transliteration is sound with no meaning in
    it, and that is where a narrator earns its cost.
    """
    assert complexity("R") == 0
    assert complexity(r"R = T_{BA} \circ T_{AB}") <= NARRATE_ABOVE
    assert complexity(r"\frac{\sum_{i=1}^{n} x_i}{n}") > NARRATE_ABOVE


def test_a_narrator_is_asked_only_about_the_hard_ones() -> None:
    asked: list[str] = []

    def narrator(latex: str, lang: str) -> str:
        asked.append(latex)
        return "the average of the x values"

    out = speakable(r"Simple \(R\) and hard \(\frac{\sum_{i=1}^{n} x_i}{n}\).",
                    "en", narrator=narrator)
    assert asked == [r"\frac{\sum_{i=1}^{n} x_i}{n}"]
    assert "the average of the x values" in out
    assert "R" in out


def test_a_narrator_that_answers_with_latex_is_ignored() -> None:
    """
    A model handed a formula sometimes hands it back. Accepting that would
    put the markup straight into the voice — the thing this module exists
    to prevent — so the deterministic reading wins.
    """
    out = speakable(r"Hard \(\frac{\sum_{i=1}^{n} x_i}{n}\).", "en",
                    narrator=lambda latex, lang: r"\frac{a}{b}")
    assert "\\" not in out
    assert "over" in out


def test_a_narrator_that_fails_costs_nothing() -> None:
    """The deterministic reading is the baseline, not a degraded mode."""
    def broken(latex: str, lang: str) -> str:
        raise RuntimeError("no model here")

    out = speakable(r"Hard \(\frac{\sum_{i=1}^{n} x_i}{n}\).", "en", narrator=broken)
    assert "over" in out
