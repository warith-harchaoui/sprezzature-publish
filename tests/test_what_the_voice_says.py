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

import _readalong
import pytest
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
    return [
        (p["text"], speakable(_readalong.without_markers(s["text"]), "en"))
        for p, s in zip(page, said)
    ]


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
    # `spoken` keeps the marker wrapped so the splitter sees the page's
    # shape; what the voice gets is what survives `without_markers`.
    assert (inner in _readalong.without_markers(block.spoken)) is spoken


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
    assert _readalong.without_markers(block.spoken) == "Take x here."


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
    assert "the ratio of" in out


def test_a_narrator_that_fails_costs_nothing() -> None:
    """The deterministic reading is the baseline, not a degraded mode."""
    def broken(latex: str, lang: str) -> str:
        raise RuntimeError("no model here")

    out = speakable(r"Hard \(\frac{\sum_{i=1}^{n} x_i}{n}\).", "en", narrator=broken)
    assert "the ratio of" in out


# ── Telling a formula rather than spelling it ──────────────────────────────


def test_an_expectation_reads_as_a_phrase() -> None:
    """
    The shape every statistics paper writes, and the one that showed the
    difference between the two jobs. Spelled, it is "E, open bracket, theta,
    mid, m, close bracket"; told, it is a sentence.
    """
    assert speak_math(r"\mathbb{E}[\theta \mid m]", "en") == (
        "the expected value of theta given m"
    )
    assert speak_math(r"\mathbb{E}[\theta \mid m]", "fr") == (
        "l'espérance de theta sachant m"
    )


def test_a_compound_fraction_is_bound_by_its_phrasing() -> None:
    """
    "a over b" is how a simple fraction is said, and it stops working the
    moment either half is a sum: "tau squared over tau squared plus sigma
    squared" can be heard three ways and a listener has no parentheses to
    fall back on. "The ratio of A to B" binds, because "to" closes the
    first half.
    """
    assert speak_math(r"\frac{a}{b}", "en") == "a over b"
    assert speak_math(r"\frac{a+1}{b}", "en") == "the ratio of a plus 1 to b"


def test_an_implicit_product_gets_the_word_and_the_comma() -> None:
    """
    A page writes no sign between a fraction and the symbol it multiplies.
    Said aloud the symbol sounds like a stray letter, and the comma is what
    closes the ratio before the product opens.
    """
    said = speak_math(
        r"\frac{\tau^2}{\tau^2 + \sigma^2}\; m", "en"
    )
    assert said.endswith(", times m")
    assert " ," not in said


def test_grouping_brackets_are_not_read_out() -> None:
    """
    Brackets are punctuation for the eye. "Open bracket" is the spelling
    this module exists to remove; the phrasing carries the grouping.
    """
    said = speak_math(r"\mathbb{P}[X > t]", "en")
    assert "bracket" not in said
    assert said == "the probability of X is greater than t"


def test_the_whole_formula_from_the_page_reads_as_one_sentence() -> None:
    """The live case, end to end."""
    assert speak_math(
        r"\mathbb{E}[\theta \mid m] \;=\; \frac{\tau^2}{\tau^2 + \sigma^2}\; m",
        "en",
    ) == (
        "the expected value of theta given m equals the ratio of tau squared "
        "to tau squared plus sigma squared, times m"
    )


# ── A formula on its own line is a sentence too ────────────────────────────

MATH_PAGE = (
    "<article>"
    "<p>the more so as the measurement is noisy:</p>"
    r'<div class="drz-math">$$\mathbb{E}[\theta \mid m] = '
    r'\frac{\tau^2}{\tau^2 + \sigma^2} m$$</div>'
    "<p>This is the shrinkage formula.</p>"
    "</article>"
)


def test_a_display_formula_is_narrated_at_all() -> None:
    """
    The defect this is written for, and it was silent.

    Display maths lives in a block element — `<div>`, `<figure>`, whatever
    the renderer wanted — and a `<div>` is not a narrated block, so the
    formula was skipped entirely. The sentence introducing it ended on a
    colon and pointed at nothing, which is worse than spelling the formula
    out: a listener hears the setup and never the thing.
    """
    blocks = _readalong.page_blocks(MATH_PAGE, scope="article")
    assert len(blocks) == 3, [b.tag for b in blocks]
    assert blocks[1].tag == "div"
    assert "mathbb" in blocks[1].visible


def test_a_layout_div_is_still_not_narrated() -> None:
    """
    The cost of the fix, kept at zero. A `<div>` is layout almost always
    and content just often enough to matter; narrating all of them would
    change what is read on every page ever built with this, for the sake of
    the few that put a formula in one. So one is opened on approval and
    taken apart again unless it holds a formula and nothing else.
    """
    blocks = _readalong.page_blocks(
        "<article><div class='wrap'><p>Inside a layout div.</p></div>"
        "<div>Loose text that was never narrated before.</div></article>",
        scope="article",
    )
    assert [b.tag for b in blocks] == ["p"]


def test_a_display_formula_is_told_not_spelled() -> None:
    """End to end: the page's own formula, as the voice says it."""
    blocks = _readalong.page_blocks(MATH_PAGE, scope="article")
    said = speakable(_readalong.without_markers(blocks[1].spoken), "en")
    assert "$" not in said and "\\" not in said
    assert said.startswith("the expected value of theta given m equals")
    assert said.endswith(", times m")


# ── Where the sentences end is the page's decision ─────────────────────────


def test_dropping_a_marker_does_not_move_a_sentence_boundary() -> None:
    """
    The subtlest defect of the lot, and it took twelve pages to surface.

    One page ends a sentence on ``ranking the top N<sup>9</sup>.`` The
    visible text is ``top N9.``, which every sentence splitter ends a
    sentence on. Take the marker out *before* splitting and it becomes
    ``top N.`` — which every sentence splitter reads as an initial, the way
    it reads the N in a name, and runs straight into the next sentence. The
    page and the narration then disagree by one sentence, from there to the
    end of the article.

    So the spoken text keeps the page's shape to the character while it is
    split — markers and all, wrapped in a word joiner — and the markers come
    out per sentence afterwards.
    """
    html = (
        "<article><p>Ranking the top N<sup>9</sup>. That order of magnitude "
        "holds for a schema of this size.</p></article>"
    )
    block = _readalong.page_blocks(html, scope="article")[0]

    page = explode_to_sentences(
        segments_from_blocks([(block.tag, block.visible, block.in_quote)])
    )
    said = explode_to_sentences(
        segments_from_blocks([(block.tag, block.spoken, block.in_quote)])
    )
    assert len(page) == 2, "the page itself does not have two sentences here"
    assert len(said) == len(page), (
        "the marker moved a sentence boundary: page "
        f"{[s['text'] for s in page]} against {[s['text'] for s in said]}"
    )
    assert _readalong.without_markers(said[0]["text"]) == "Ranking the top N."


def test_the_marker_is_invisible_but_findable() -> None:
    """
    It has to survive the splitter untouched and then be removable without
    guessing which digits were a marker and which were prose.
    """
    html = "<article><p>Top N<sup>9</sup>. In 2025 there were 9 of them.</p></article>"
    block = _readalong.page_blocks(html, scope="article")[0]
    assert _readalong.MARKER in block.spoken
    cleaned = _readalong.without_markers(block.spoken)
    assert cleaned == "Top N. In 2025 there were 9 of them.", cleaned


# ── A section that says what it is ─────────────────────────────────────────


def _sources_section(heading: str, items: int = 6) -> str:
    entries = "".join(
        f'<li><cite>Author {i} (2024). A paper.</cite> arxiv.org/abs/{i}</li>'
        for i in range(items)
    )
    return f"<article><p>Body text here.</p><h2>{heading}</h2><ol>{entries}</ol></article>"


@pytest.mark.parametrize(
    "heading",
    ["References", "Bibliography", "Références", "Further reading",
     "Sources", "Works cited", "NOTES"],
)
def test_a_sources_section_is_silenced_whatever_it_is_called(heading: str) -> None:
    """
    The structural rule — the markers say what they point at — needs no
    vocabulary and is tried first. But plenty of pages list their sources
    without linking a single marker to them, and for those the name is all
    there is. Folded to lowercase without accents, so "Références" and
    "References" are one key.
    """
    blocks = _readalong.page_blocks(_sources_section(heading), scope="article")
    assert [b.visible for b in blocks] == ["Body text here."], heading


def test_a_prose_section_called_notes_is_still_read() -> None:
    """
    The corroboration, and the reason the name alone is not enough.

    A heading called "Notes" above three paragraphs of prose is a section
    of an essay; silencing it because of its name is the kind of guess that
    makes a tool untrustworthy. The same heading above twenty list items
    carrying citations is an apparatus. The name proposes, the shape
    decides.
    """
    html = (
        "<article><p>Body.</p><h2>Notes</h2>"
        "<p>A real aside, in prose.</p><p>And a second paragraph of it.</p>"
        "<p>And a third, still prose.</p></article>"
    )
    blocks = _readalong.page_blocks(html, scope="article")
    assert len(blocks) == 5, [b.visible[:20] for b in blocks]


def test_a_page_can_have_both_kinds_of_section() -> None:
    """Linked footnotes in one place, an unlinked reading list in another."""
    html = (
        "<article><p>Prose with a marker"
        '<sup><a href="#ref-1">1</a></sup>.</p>'
        "<h2>Bibliography</h2><ol>"
        '<li id="ref-1"><cite>Linked source.</cite></li>'
        '<li id="ref-2"><cite>Another.</cite></li></ol>'
        "<h2>Further reading</h2><ol>"
        "<li><cite>Unlinked book, 2024.</cite></li>"
        "<li><cite>And another, 2025.</cite></li></ol></article>"
    )
    blocks = _readalong.page_blocks(html, scope="article")
    assert len(blocks) == 1 and blocks[0].tag == "p"
