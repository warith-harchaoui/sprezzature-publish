"""
test_readalong_can_be_taken_back_out — the two repairs a narrated page needs.

``build`` writes a voice into a page and refuses to write one onto prose that
moved while the recording was running. That net is reliable, and it covers one
order of events. Two other things happen in the world and neither was covered
here before:

* **A sentence needs correcting after the page has a voice.** The timings live
  in the page, one ``data-start`` per sentence, so editing the prose moves
  every sentence after the edit out from under its timestamp. The repair is to
  take the player out, edit, and record again -- which needs a way to take the
  player out. Every caller was writing that by hand; on one site it was written
  from scratch three times in three days, and each rewrite walked into the same
  two traps, both tested here.

* **A page is edited after it ships.** Nothing fires then. The markers stay,
  their times stay, and every time now points at the wrong sentence, which is
  worse than no highlight because it is confidently wrong. ``check`` is the
  only thing that catches it, and it reads only what was shipped.

What the traps are, since the tests are named after them: a pattern that stops
at the first ``</div>`` cuts the player in half, because the player holds seven
nested ``<div>`` of its own; and unwrapping a ``<span class="ra-s">`` by
deleting the tag *and* its content silently deletes the sentence.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import _narrate
import _readalong
import pytest

OPENING = '<span class="ra-s" id="ra-{index}" data-start="{start:.3f}">'
CLOSING = "</span>"

VTT = (
    "WEBVTT\n\n"
    "0\n00:00:00.000 --> 00:00:01.000\nFirst one.\n\n"
    "1\n00:00:01.500 --> 00:00:02.500\nSecond one.\n"
)


@pytest.fixture
def cues() -> list[_readalong.VttCue]:
    return _readalong.parse_vtt(VTT)


def wrapped(page: str, cues: list[_readalong.VttCue]) -> str:
    return _readalong.wrap_sentences(
        page,
        cues,
        split=_narrate.split_sentences,
        scope="article",
        opening=OPENING,
        closing=CLOSING,
    )


class TestItComesBackOutExactly:
    """Stripping what ``build`` wrote must return the page byte for byte.

    Anything less and the repair loop is lossy: strip, edit one word, record,
    and the page has quietly drifted in ways nobody asked for.
    """

    def test_a_round_trip_is_the_identity(self, cues):
        page = "<article><p>First one. Second one.</p></article>"
        back, markers = _readalong.strip_player(wrapped(page, cues))
        assert back == page
        assert markers == 2

    def test_a_page_with_no_read_along_is_left_alone(self):
        page = "<article><p>Nothing to undo here.</p></article>"
        back, markers = _readalong.strip_player(page)
        assert back == page
        assert markers == 0

    def test_the_sentence_survives_its_span(self):
        """The trap: deleting the tag *and* its content deletes the prose."""
        page = '<p><span class="ra-s" id="ra-0" data-start="0.000">Kept.</span></p>'
        back, _ = _readalong.strip_player(page)
        assert back == "<p>Kept.</p>"

    def test_nested_divs_do_not_cut_the_player_in_half(self):
        """The trap: stopping at the first ``</div>`` leaves the tail behind."""
        page = '<div class="ra-player"><div><div>controls</div></div></div>\n<p>Prose.</p>'
        back, _ = _readalong.strip_player(page)
        assert "ra-player" not in back
        assert "controls" not in back
        assert back == "<p>Prose.</p>"

    def test_an_unclosed_player_is_refused_rather_than_guessed(self):
        with pytest.raises(_readalong.ReadAlongMismatch):
            _readalong.strip_player('<div class="ra-player"><p>no end')


class TestItCatchesAPageEditedAfterItShipped:
    """``check``'s whole reason for existing."""

    def test_a_page_and_its_cues_agree(self, cues):
        page = "<article><p>First one. Second one.</p></article>"
        assert _readalong.disagreements(wrapped(page, cues), cues) == []

    def test_an_edited_sentence_is_reported_with_where_it_parts(self, cues):
        page = "<article><p>First one. Second one.</p></article>"
        edited = wrapped(page, cues).replace("Second one.", "Second two.")
        found = _readalong.disagreements(edited, cues)
        assert len(found) == 1
        # The position matters: two sentences differing at their thirtieth
        # word look identical in a report that prints the first sixty
        # characters of each.
        assert "ra-1" in found[0]
        assert "Second two." in found[0]

    def test_a_missing_marker_is_counted(self, cues):
        page = "<article><p>First one. Second one.</p></article>"
        short = wrapped(page, cues)
        short = short[: short.index('<span class="ra-s" id="ra-1"')] + "</p></article>"
        assert any("against" in line for line in _readalong.disagreements(short, cues))

    def test_a_cue_with_no_marker_can_be_tolerated(self, cues):
        """A narration says "End quote." aloud; the page never says it."""
        page = "<article><p>First one. Second one.</p></article>"
        spoken = _readalong.parse_vtt(VTT + "\n2\n00:00:03.000 --> 00:00:03.500\nEnd quote.\n")
        assert _readalong.disagreements(wrapped(page, cues), spoken)
        assert _readalong.disagreements(wrapped(page, cues), spoken, tolerate=("End quote.",)) == []

    def test_a_template_tag_does_not_hide_a_marker(self, cues):
        """On a PHP page the ``?>`` of a template tag closes a ``[^>]*`` early.

        Stripping HTML before the template language therefore cuts the marker's
        own tag in half and loses its ``data-start``.
        """
        page = "<article><p>First one. Second one.</p></article>"
        with_template = wrapped(page, cues).replace(
            "<article>", '<article data-src="<?= ASSETS ?>/x.png">'
        )
        assert _readalong.disagreements(with_template, cues) == []


class TestTheCommandLine:
    """The two flags, including what they refuse."""

    def test_strip_writes_a_page_without_the_player(self, tmp_path, cues):
        import readalong

        page = tmp_path / "post.html"
        page.write_text(
            wrapped("<article><p>First one. Second one.</p></article>", cues), encoding="utf-8"
        )
        out = readalong.strip(page, tmp_path / "built")
        assert "ra-s" not in out.read_text(encoding="utf-8")
        # The input is never modified in place: a live page is not a draft.
        assert "ra-s" in page.read_text(encoding="utf-8")

    def test_check_reads_the_narration_beside_the_page(self, tmp_path, cues):
        import readalong

        page = tmp_path / "post.html"
        page.write_text(
            wrapped("<article><p>First one. Second one.</p></article>", cues), encoding="utf-8"
        )
        narration = tmp_path / "audio"
        narration.mkdir()
        (narration / "narration.vtt").write_text(VTT, encoding="utf-8")
        assert readalong.check(page, narration) == []
