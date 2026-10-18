"""
The designed player, checked without a browser.

The bar is progressive enhancement over a native ``<audio controls>``, and
that arrangement has exactly two ways to fail: a reader sees two players, or
a reader sees none. Both are invisible to the test suite that only checks
the markup is present, so what is checked here is the *pairing* — the
designed block ships hidden, the native one ships visible, and the module
swaps them together.

The rest is the things a control cannot be wrong about. A button that is a
``<div>`` has no keyboard. A scrubber that is not an ``<input type=range>``
has no arrow keys. A label built in JavaScript is a label outside the
language table, which this component refuses to do from Python and would be
a strange thing to then do from a script.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re
from pathlib import Path

import _readalong
import pytest

ROOT = Path(__file__).resolve().parent.parent

#: The player's default accent. One literal, and the stylesheet says why.
ACCENT = "#0D9488"
CSS = (ROOT / "assets" / "readalong" / "readalong.css").read_text(encoding="utf-8")
JS = (ROOT / "assets" / "readalong" / "readalong.js").read_text(encoding="utf-8")

#: The module with its comments removed. The comments explain *why* a label
#: is not built here, so they necessarily contain the words a search for
#: hard-coded labels is looking for.
JS_CODE = re.sub(r"/\*.*?\*/|//[^\n]*", "", JS, flags=re.S)

#: Every string literal in the module, which is the only place a label a
#: reader hears could actually be. Two earlier versions of this check
#: searched the file as text and both were wrong in the same way: "Play" is
#: a substring of the comment that explains the rule, and again of
#: `dataset.raLabelPlay`, which is the mechanism the rule asks for. A test
#: that fires on the thing it is protecting is worse than no test.
JS_LITERALS = {
    m.group(1) or m.group(2) or m.group(3)
    for m in re.finditer(r"'([^'\\]*)'|\"([^\"\\]*)\"|`([^`\\$]*)`", JS_CODE)
}


def player(lang: str = "en", seconds: float = 3817.361) -> str:
    return _readalong.player_html(
        audio_src="../audio/narration.mp3",
        vtt_src="../audio/narration.vtt",
        label=_readalong.player_label(lang),
        lang=lang,
        duration_seconds=seconds,
    )


# ── One player at a time, always exactly one ───────────────────────────────


def test_the_designed_bar_ships_hidden_and_the_native_one_visible() -> None:
    """
    Without the module, a reader must get the native controls — a designed
    bar with nothing behind it looks operable and is not.
    """
    html = player()
    assert re.search(r'<div class="ra-ui" data-ra-ui hidden>', html)
    assert "<audio controls" in html
    assert "<audio hidden" not in html


def test_the_swap_is_one_decision_in_each_direction() -> None:
    """
    The module unhides the bar and sets ``data-ra-enhanced``; the stylesheet
    hides the native controls off that same attribute. One signal, so there
    is no ordering in which both are visible or neither is.
    """
    assert "ui.hidden = false" in JS
    assert "setAttribute('data-ra-enhanced'" in JS
    # The rule is written as a group -- the title, the native controls and
    # the caption all go together -- so the check is "the native element is
    # among the things that disappear", not a rule of its own.
    hidden = re.search(
        r"((?:\.ra-player\[data-ra-enhanced\][^{,]*,?\s*)+)\{[^}]*display:\s*none", CSS
    )
    assert hidden and "audio" in hidden.group(1)


# ── Controls that keep their keyboard ──────────────────────────────────────


def test_every_control_is_a_real_button() -> None:
    """
    A ``<div>`` with a click handler has no keyboard, no focus, and no role.
    Every one of these is a ``<button type="button">`` so none of that has to
    be reimplemented — or remembered.
    """
    html = player()
    for control in ("data-ra-play", "data-ra-back", "data-ra-forward", "data-ra-rate"):
        match = re.search(rf"<(\w+)[^>]*\b{control}\b", html)
        assert match, f"{control} is not in the markup"
        assert match.group(1) == "button", f"{control} is a <{match.group(1)}>"
    assert html.count('type="button"') == 4


def test_the_scrubber_is_a_range_input() -> None:
    """
    Arrow keys, Home/End, touch, and a screen reader's own slider gestures
    all arrive correct because the browser implements them. A hand-rolled
    scrubber gets to reimplement every one, and gets one of them wrong.
    """
    html = player()
    assert re.search(r'<input class="ra-scrub" type="range"[^>]*data-ra-scrub', html)


@pytest.mark.parametrize(
    "control", ["data-ra-play", "data-ra-back", "data-ra-forward", "data-ra-rate"]
)
def test_every_control_has_a_non_empty_accessible_name(control: str) -> None:
    """An icon button with no label is an unlabelled button."""
    html = player()
    match = re.search(rf'<button[^>]*\b{control}\b[^>]*>', html)
    assert match
    label = re.search(r'aria-label="([^"]*)"', match.group(0))
    assert label and label.group(1).strip(), f"{control} has no aria-label"


# ── The words come from the language table ─────────────────────────────────


def test_a_french_page_gets_a_french_player() -> None:
    """
    The whole point of refusing an unknown language: a screen-reader user on
    a French page should not hear confident English.
    """
    html = player("fr")
    assert 'aria-label="Lecture"' in html
    assert 'data-ra-label-pause="Pause"' in html
    assert "Reculer de 15 secondes" in html
    assert "Play" not in html


def test_every_language_names_every_control() -> None:
    """
    A missing key would reach the page as the string "None" inside an
    aria-label — which tells a screen-reader user less than English would.
    """
    for lang, words in _readalong.PLAYER_LABELS.items():
        missing = _readalong.PLAYER_STRING_KEYS - set(words)
        assert not missing, f"{lang} is missing {sorted(missing)}"
        assert all(value.strip() for value in words.values()), lang


def test_a_language_missing_a_key_is_refused(monkeypatch) -> None:
    """
    Guards the check itself. Without this, dropping a key from the table
    would take its own assertion with it and the suite would stay green.
    """
    monkeypatch.setitem(
        _readalong.PLAYER_LABELS, "xx", {"title": "T", "play": "P"}
    )
    with pytest.raises(_readalong.ReadAlongMismatch, match="missing"):
        _readalong.player_strings("xx")


def test_the_module_builds_no_string_a_reader_hears() -> None:
    """
    Both labels are written into the markup by the generator, which has the
    language table; the module only swaps between them.
    """
    # `dataset.raLabelPause` is how the DOM spells the `data-ra-label-pause`
    # attribute the generator writes; the point is that the module *reads*
    # both labels rather than containing either.
    assert "dataset.raLabelPlay" in JS and "dataset.raLabelPause" in JS
    spoken = {
        words[key]
        for words in _readalong.PLAYER_LABELS.values()
        for key in ("play", "pause", "back", "forward", "speed", "seek")
    }
    leaked = spoken & JS_LITERALS
    assert not leaked, (
        f"{sorted(leaked)} are string literals in the module; a label a "
        f"reader hears belongs in PLAYER_LABELS, which is what gets "
        f"translated"
    )


# ── The clock ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("seconds", "shown"),
    [(0, "0:00"), (9, "0:09"), (65, "1:05"), (600, "10:00"), (3817.361, "1:03:37")],
)
def test_the_clock_reads_like_a_clock(seconds: float, shown: str) -> None:
    """No leading zero on the first field — ``0:09`` is nine seconds."""
    assert _readalong._clock(seconds) == shown


def test_the_total_is_shown_before_any_audio_is_fetched() -> None:
    """
    ``preload="none"`` means the browser knows nothing about the file until
    the reader presses play. A player that waited for metadata would show
    ``0:00`` beside a sixty-four-minute recording — exactly when a reader is
    deciding whether to commit to it. The duration is measured server-side
    from the cues, so it can simply be written in.
    """
    html = player(seconds=3817.361)
    assert 'data-ra-duration="3817.361"' in html
    assert ">1:03:37</span>" in html
    assert 'preload="none"' in html


def test_the_bar_remembers_where_the_reader_got_to() -> None:
    """
    A sixty-minute article is not finished in one sitting, and starting
    over at the top is how nobody comes back. Keyed by path rather than by
    the whole URL, so a campaign link's query string does not turn the same
    article into a different recording.
    """
    assert "localStorage" in JS
    assert "location.pathname" in JS
    assert "localStorage.removeItem" in JS, (
        "a finished recording must forget its position, or 'continue' lands "
        "on the closing word"
    )


def test_the_bar_publishes_its_own_height() -> None:
    """
    The page has to keep its last paragraph out from under a fixed bar, and
    the bar is the only thing that knows how tall it is — the height
    depends on the host page's font. A guess that is a few pixels short
    hides the end of the article, which is the one place a reader will not
    think to look for a bar.
    """
    assert "--ra-bar" in JS and "offsetHeight" in JS
    assert "--ra-bar" in CSS and "padding-bottom" in CSS


def test_the_slider_announces_a_time_not_a_thousandth() -> None:
    """
    The range runs 0-1000 because a slider needs integer steps. "Three
    hundred and seventy-two" is not a thing anyone can picture, so what gets
    announced is the clock.
    """
    assert 'aria-valuetext="0:00"' in player()
    assert "setAttribute('aria-valuetext', CLOCK(" in JS


# ── Drawn so it survives a page it has never seen ──────────────────────────


def test_the_play_glyph_is_a_hole_not_a_painted_shape() -> None:
    """
    This component is injected into pages whose background it does not know.
    Painting a pale glyph on a filled disc needs that colour; cutting the
    glyph out of the disc does not, because whatever is behind shows
    through. The failure avoided is a solid disc with no symbol in it.
    """
    assert "mask: var(--ra-glyph)" in CSS
    assert "fill: Canvas" not in CSS
    # And a browser without masks still gets a button, just without a glyph.
    assert "@supports not ((-webkit-mask" in CSS


def test_forced_colours_do_not_erase_the_button() -> None:
    """
    Forced colours drop background images, and the mask goes with them — the
    disc would arrive as a plain square. The circle is drawn with a border
    instead, which forced colours keep.
    """
    forced = CSS[CSS.index("@media (forced-colors: active)"):]
    assert re.search(r"\.ra-play\s*\{[^}]*border-radius:\s*50%", forced)
    assert re.search(r"\.ra-play\s*\{[^}]*border:\s*2px solid ButtonText", forced)


def test_there_is_exactly_one_colour_literal_and_it_is_the_accent() -> None:
    """
    The rule this file started with was "no hex values in the player": the
    component is injected into pages it has never seen, so it inherits the
    text colour rather than choosing one. That rule was right about
    everything except the accent, which is the one colour a player is
    allowed to have — and leaving it as `currentColor` produced a grey
    control that looked like nobody had decided anything.

    So the rule becomes: one literal, used as the *default* of the public
    `--ra-accent` hook, and nothing else hard-coded. More than one means a
    second colour crept in somewhere a host page cannot reach.
    """
    player_css = CSS[CSS.index("/* The player"):CSS.index("/* The highlight.")]
    literals = set(re.findall(r"#[0-9a-fA-F]{3,8}\b", player_css))
    assert literals == {ACCENT}, f"colour literals in the player: {sorted(literals)}"


def test_the_accent_is_a_hook_a_host_page_can_actually_reach() -> None:
    """
    The defect this is written for, and it was invisible in the markup.

    `--ra-accent` was first *declared* on `.ra-player` with a default. A
    custom property declared on an element shadows whatever an ancestor
    set, so a site that styled `:root { --ra-accent: … }` would find the
    player ignoring it — a hook that exists and does nothing, which is
    worse than no hook because it is documented. Caught by rendering six
    colour variants and finding all six identical.

    It is read with a default at the use site instead, and the element
    declares only the internal variable derived from it.
    """
    assert "--ra-accent:" not in CSS, (
        "--ra-accent is declared in the stylesheet, which shadows whatever "
        "a host page sets on an ancestor"
    )
    assert f"var(--ra-accent, {ACCENT})" in CSS


def test_the_accent_clears_contrast_on_a_light_and_a_dark_page() -> None:
    """
    Why this particular colour, and the reason it is not a preference.

    The player is injected into pages whose background it does not know, so
    the accent has to clear 3:1 — the threshold for a non-text interface
    element — against a light page *and* a dark one. The obvious
    alternatives fail one side: a violet deep enough to look right on white
    falls to about 2:1 on black, and a brighter teal fails on white.
    """

    def _channel(value: float) -> float:
        value /= 255
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    def _luminance(colour: str) -> float:
        colour = colour.lstrip("#")
        red, green, blue = (int(colour[i:i + 2], 16) for i in (0, 2, 4))
        return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)

    def _ratio(one: str, other: str) -> float:
        a, b = _luminance(one), _luminance(other)
        return (max(a, b) + 0.05) / (min(a, b) + 0.05)

    assert _ratio(ACCENT, "#ffffff") >= 3.0, "the accent fails on a light page"
    assert _ratio(ACCENT, "#0f0f10") >= 3.0, "the accent fails on a dark page"


def test_the_skip_glyph_leaves_its_middle_empty() -> None:
    """
    Two versions of this icon were wrong, and only at real size: a filled
    disc with "15" over it, then an open ring drawn tight enough that the
    digits touched it. The ring is the thing that must not be filled, and
    it must be wide enough to hold a number.
    """
    glyph = _readalong._SKIP_GLYPH
    assert 'fill="none"' in glyph, "the ring is filled; the number has nowhere to go"
    radius = re.search(r"A([\d.]+) ", glyph)
    assert radius and float(radius.group(1)) >= 9.0, (
        "the ring is drawn too tight for the digits it has to contain"
    )


# ── The colours come from the page ─────────────────────────────────────────

LIGHT = (
    "<html><head><style>body{background:#ffffff;color:#111111}"
    ".muted{color:#858585}.muted2{color:#858585}.muted3{color:#858585}"
    ".chip{background-color:#F7FABE}</style></head><body><p>x</p></body></html>"
)
DARK = (
    "<html><head><style>body{background:#111113;color:#f2f2f7}"
    ".chip{background-color:#5EEAD4}</style></head><body><p>x</p></body></html>"
)


def test_a_framework_default_is_not_the_pages_accent() -> None:
    """
    The rule the extraction rests on: a colour on the right of a **custom
    property definition** is skipped, a colour inside a real declaration is
    kept.

    Without it, `--framer-link-text-color: rgb(0, 153, 255)` — a framework
    default sitting on every rich-text block of a page, which the site then
    overrides — is counted thirty-one times and wins. The player ends up
    wearing a colour that is painted nowhere on the page.
    """
    html = (
        '<p style="--framer-link-text-color:rgb(0, 153, 255)">a</p>'
        '<p style="--framer-link-text-color:rgb(0, 153, 255)">b</p>'
        '<p style="--framer-link-text-color:rgb(0, 153, 255)">c</p>'
        '<a style="background-color:var(--token-x, rgb(247, 250, 190))">chip</a>'
    )
    assert _readalong.page_palette(html).get("accent") == "#F7FABE"


def test_a_token_fallback_inside_a_real_property_still_counts() -> None:
    """
    `background-color: var(--token-…, #F7FABE)` is how a design tool writes
    a named token, and a named token is about as close to "the author chose
    this" as a stylesheet gets. Skipping it along with the definitions
    would throw away the one colour worth having.
    """
    html = '<a style="background-color:var(--token-x, #F7FABE)">chip</a>'
    assert _readalong.page_palette(html).get("accent") == "#F7FABE"


@pytest.mark.parametrize(
    ("html", "paper", "ink"),
    [(LIGHT, "#FFFFFF", "#111111"), (DARK, "#111113", "#F2F2F7")],
)
def test_paper_and_ink_are_told_apart_by_property_not_by_lightness(
    html: str, paper: str, ink: str
) -> None:
    """
    Luminance alone gets a dark page exactly backwards: there the
    background is the dark colour and the text the light one, so "dark
    means ink" hands the player the page's own background to paint a button
    with — an invisible control on the pages least able to spare one.
    """
    palette = _readalong.page_palette(html)
    assert palette["paper"] == paper
    assert palette["ink"] == ink


def test_an_accent_too_pale_to_fill_is_kept_where_it_works() -> None:
    """
    An accent has two jobs and a page's accent is usually only good at one.
    A pale chip colour is the page's own voice as a wash and 1.09:1 as a
    filled button. So the wash keeps it and the fill takes the page's ink —
    which is the page's own arrangement, a pale chip with dark type on it.
    """
    colours = _readalong.player_colours(_readalong.page_palette(LIGHT))
    assert colours["--ra-tint"] == "#F7FABE"
    assert colours["--ra-accent"] == "#111111"


def test_an_accent_that_can_fill_does_fill() -> None:
    colours = _readalong.player_colours(_readalong.page_palette(DARK))
    assert colours["--ra-accent"] == "#5EEAD4"


def test_a_page_that_says_nothing_keeps_the_components_own_default() -> None:
    """Dressing a page in a guess is worse than the restrained version."""
    assert _readalong.player_colours(_readalong.page_palette("<p>plain</p>")) == {}


def test_the_bar_stands_on_the_pages_paper_not_the_browsers() -> None:
    """
    `Canvas` is the browser's idea of a page background, and it is white on
    any page that is dark through its own stylesheet without declaring
    `color-scheme`. That is not a rare page — it is every hand-built dark
    theme — and a white bar across the foot of one is a slab of light.
    """
    assert "var(--ra-paper, Canvas)" in CSS
    assert _readalong.player_colours(_readalong.page_palette(DARK))["--ra-paper"] == (
        "#111113"
    )


def test_the_muted_grey_does_not_win_the_ink() -> None:
    """
    The trap this rule exists for, and the first two versions fell into it.

    A page declares its caption grey far more often than its body colour —
    sixteen occurrences against one, on the page this was built against —
    so "most common neutral" hands the player a mid-grey, which is the
    exact thing the whole colour pass was asked to stop. Darkness instead
    of frequency gets a dark page backwards. The colour a page sets type in
    is the one furthest from its background, and that holds either way up.
    """
    palette = _readalong.page_palette(LIGHT)
    assert palette["ink"] == "#111111", "the caption grey won the ink"
    assert _readalong.player_colours(palette)["--ra-accent"] == "#111111"
