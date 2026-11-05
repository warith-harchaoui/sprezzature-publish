"""
test_faq — the FAQ builder and its audit.

The builder's promise is narrow: no answer without a passage of the site
behind it, no number the passages do not state, and the markup built from
the very text the reader sees. Most tests below hold one of those three.
The model is never called: ``chat`` is injected.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json

import _content as c
import faq
import pytest
from cta import CtaPlan, CtaSpec

HOME = """<!doctype html><html lang="en"><head><title>Acme — local captions</title></head>
<body><main>
<h1>Acme</h1>
<p>Acme turns recorded speech into captions on your own machine.</p>
<h2>Pricing</h2>
<p>Acme is free and open source under the BSD-3 licence, with no paid tier.</p>
<h2>Privacy</h2>
<p>Acme runs offline: your audio and your data never leave the laptop.</p>
<a href="https://calendly.com/acme/demo" class="bg-blue-600 px-4 py-2 text-white">Book a demo</a>
</main></body></html>
"""

GALLERY = """<!doctype html><html lang="en"><head><title>Charts — Acme</title></head>
<body><main><h1>Charts</h1>
<p>Candlestick charts draw the open, high, low and close price of each bar.</p>
</main></body></html>
"""

PLAN = CtaPlan(
    offer="Local captions.",
    organization="Acme",
    ctas=[CtaSpec("Book a demo", "https://calendly.com/acme/demo", "", "decide", True)],
)


def site(*docs: tuple[str, str]) -> list[c.PageContent]:
    return [page for path, text in docs if (page := c.read_text(text, path)) is not None]


def answers(build: faq.FaqBuild) -> dict[str, faq.Answer]:
    return {a.question: a for a in build.items}


def test_a_question_the_site_answers_is_answered_from_its_words():
    build = faq.build_faq(site(("index.html", HOME), ("charts.html", GALLERY)), PLAN)
    cost = answers(build)["How much does Acme cost?"]
    assert "BSD-3" in cost.answer
    assert cost.drafted_by == "extract"
    assert cost.sources[0].page == "index.html"


def test_a_deciding_answer_ends_on_the_declared_cta():
    build = faq.build_faq(site(("index.html", HOME)), PLAN)
    cost = answers(build)["How much does Acme cost?"]
    assert cost.next_step == "[Book a demo](https://calendly.com/acme/demo)"


def test_a_price_axis_in_a_chart_gallery_does_not_answer_what_it_costs():
    build = faq.build_faq(
        site(
            ("index.html", "<html lang=en><title>Acme</title><main><h1>Acme</h1></main></html>"),
            ("charts.html", GALLERY),
        ),
        PLAN,
    )
    assert "How much does Acme cost?" not in answers(build)
    assert "How much does Acme cost?" in {g.question for g in build.gaps}


def test_what_the_site_cannot_answer_goes_to_the_gap_report():
    build = faq.build_faq(site(("index.html", HOME)), PLAN)
    gaps = {g.question for g in build.gaps}
    assert "How does Acme compare with the alternatives?" in gaps
    assert not gaps & set(answers(build))


def test_a_model_answer_with_an_unsourced_number_is_thrown_away():
    def chat(prompt: str) -> str:
        assert "QUESTION: How much does Acme cost?" in prompt or "QUESTION:" in prompt
        return json.dumps({"answer": "Acme costs 49 euros a month.", "sources": [1]})

    build = faq.build_faq(site(("index.html", HOME)), PLAN, chat=chat)
    cost = answers(build)["How much does Acme cost?"]
    assert "49" not in cost.answer
    assert cost.drafted_by == "extract"
    assert any("49" in n for n in cost.notes)


def test_a_model_answer_with_sourced_facts_is_kept():
    def chat(prompt: str) -> str:
        return json.dumps({"answer": "Acme is free, under the BSD-3 licence.", "sources": [1]})

    build = faq.build_faq(site(("index.html", HOME)), PLAN, chat=chat)
    assert answers(build)["How much does Acme cost?"].drafted_by == "model"


def test_a_model_that_is_down_falls_back_to_the_extract():
    def chat(prompt: str) -> str:
        raise RuntimeError("connection refused")

    build = faq.build_faq(site(("index.html", HOME)), PLAN, chat=chat)
    assert answers(build)["How much does Acme cost?"].drafted_by == "extract"


def test_a_hint_ranks_first_and_merges_with_the_checklist(tmp_path):
    hints = tmp_path / "q.csv"
    hints.write_text("Does Acme work offline?,40\nhello\nIs Acme free,12\n", encoding="utf-8")
    read = faq.read_hints(hints)
    assert [(q.text, q.count) for q in read] == [
        ("Does Acme work offline?", 40),
        ("Is Acme free?", 12),
    ]
    build = faq.build_faq(site(("index.html", HOME)), PLAN, read)
    assert build.items[0].origin == "hint"


def test_the_authors_question_survives_the_checklists_wording():
    """'Who is X for?' and 'What is X?' share one content word, and only one."""
    assert not faq.similar("Who is Acme for?", "What is Acme?")
    assert faq.similar("How much does Acme cost?", "How much does Acme cost")


def test_a_faq_only_in_markup_becomes_the_visible_section():
    ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "What is Acme?",
                "acceptedAnswer": {"@type": "Answer", "text": "Acme makes captions locally."},
            }
        ],
    }
    page = HOME.replace(
        "</head>", f'<script type="application/ld+json">{json.dumps(ld)}</script></head>'
    )
    build = faq.build_faq(site(("index.html", page)), PLAN)
    assert answers(build)["What is Acme?"].drafted_by == "existing"


def test_the_markup_is_built_from_the_visible_text():
    build = faq.build_faq(site(("index.html", HOME)), PLAN)
    md = faq.render_faq_markdown(build)
    ld = json.loads(md.split('<script type="application/ld+json">', 1)[1].split("</script>")[0])
    visible = [line[4:] for line in md.splitlines() if line.startswith("### ")]
    assert [e["name"] for e in ld["mainEntity"]] == visible
    first = ld["mainEntity"][0]["acceptedAnswer"]["text"]
    assert first in faq._md_to_text(md)


def test_the_html_fragment_carries_the_same_questions():
    build = faq.build_faq(site(("index.html", HOME)), PLAN)
    fragment = faq.render_faq_html(build)
    page = c.read_html(f"<main>{fragment}</main>", "x.html")
    assert [f.question for f in page.jsonld_faq] == [i.question for i in build.items]
    assert not faq.audit_faq([page])


def test_no_answer_in_the_wrong_language():
    fr = '<html lang="fr"><title>Acme</title><main><p>Acme est gratuit, sous licence BSD-3, sans offre payante.</p></main></html>'
    pages = site(
        ("fr/index.html", fr),
        ("index.html", "<html lang=en><title>Acme</title><main><h1>Acme</h1></main></html>"),
    )
    build = faq.build_faq(pages, PLAN, lang="en")
    assert "How much does Acme cost?" not in answers(build)


def test_placement_prefers_the_money_page_and_its_end_of_main():
    build = faq.build_faq(site(("index.html", HOME), ("charts.html", GALLERY)), PLAN)
    assert [p.page for p in build.placements] == ["index.html"]
    assert build.placements[0].line


# ── Audit ──────────────────────────────────────────────────────────────────


def _ld(*pairs: tuple[str, str]) -> str:
    node = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs
        ],
    }
    return f'<script type="application/ld+json">{json.dumps(node)}</script>'


def rules(findings):
    return sorted({f.rule for f in findings})


def test_faq_only_in_markup_is_an_error():
    page = c.read_html(f"<head>{_ld(('Q?', 'A.'))}</head><body><p>Hi.</p></body>", "a.html")
    assert rules(faq.audit_faq([page])) == ["FAQ002"]


def test_markup_that_disagrees_with_the_visible_faq_is_an_error_and_fixable(tmp_path):
    text = (
        f"<html><head>{_ld(('Is it free?', 'No.'))}</head><body><main>"
        "<h2>FAQ</h2><h3>Is it free?</h3><p>Yes, under BSD-3.</p></main></body></html>"
    )
    (tmp_path / "a.html").write_text(text, encoding="utf-8")
    pages = c.read_site(tmp_path)
    assert rules(faq.audit_faq(pages)) == ["FAQ003"]
    assert faq.fix_faq(pages, tmp_path) == ["a.html"]
    again = c.read_site(tmp_path)
    assert faq.audit_faq(again) == []
    assert faq.fix_faq(again, tmp_path) == []  # twice is a no-op


def test_the_fix_leaves_a_mixed_graph_alone(tmp_path):
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "name": "Acme"},
            {
                "@type": "FAQPage",
                "mainEntity": [
                    {
                        "@type": "Question",
                        "name": "Is it free?",
                        "acceptedAnswer": {"@type": "Answer", "text": "No."},
                    }
                ],
            },
        ],
    }
    text = (
        f'<head><script type="application/ld+json">{json.dumps(graph)}</script></head>'
        "<main><h2>FAQ</h2><h3>Is it free?</h3><p>Yes.</p></main>"
    )
    (tmp_path / "a.html").write_text(text, encoding="utf-8")
    assert faq.fix_faq(c.read_site(tmp_path), tmp_path) == []


def test_one_question_marked_up_on_two_pages_is_a_warning():
    a = c.read_html(
        f"<head>{_ld(('Q?', 'A.'))}</head><main><h2>FAQ</h2><h3>Q?</h3><p>A.</p></main>", "a.html"
    )
    b = c.read_html(
        f"<head>{_ld(('Q?', 'A.'))}</head><main><h2>FAQ</h2><h3>Q?</h3><p>A.</p></main>", "b.html"
    )
    assert rules(faq.audit_faq([a, b])) == ["FAQ004"]


def test_a_number_no_other_page_states_is_a_warning():
    a = c.read_html(
        "<main><h2>FAQ</h2><h3>How fast?</h3><p>It is 12 times faster.</p></main>", "a.html"
    )
    b = c.read_html(
        "<main><p>A page about something else entirely, with words.</p></main>", "b.html"
    )
    assert rules(faq.audit_faq([a, b])) == ["FAQ001"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1 885 pages", {"1885"}), ("1,885 and 40 %", {"1885", "40"}), ("v2", set())],
)
def test_numbers_are_compared_without_their_separators(text, expected):
    assert faq.numbers(text) == expected


# ── Lessons from a real site (deraison.ai, 2026-11-05) ───────────────────

# The shape a hand-built FAQ takes: each question an <h3> inside a
# <summary>, the section closed by a call to action with no heading of its
# own, then the site's footer.
ACCORDION = """<!doctype html><html lang="fr"><body><main>
<section id="faq"><h2>Questions fréquentes</h2>
<details open><summary><h3>Que fait Acme ?</h3></summary><p>Acme fait des sous-titres.</p></details>
<details><summary><h3>Combien coûte Acme ?</h3></summary><p>Acme est gratuit.</p></details>
<div><p>Prêt ?</p><a href="https://calendly.com/acme">Réserver un appel</a></div>
</section></main>
<footer><h2>Parlons de votre projet</h2><p>Écrivez-nous.</p></footer></body></html>
"""


def test_the_last_answer_ends_with_its_section():
    """The CTA after the last question is not part of its answer."""
    page = c.read_html(ACCORDION, "index.html")
    found = {f.question: f.answer for f in page.faq}
    assert found["Combien coûte Acme ?"] == "Acme est gratuit."
    assert all("Réserver" not in a for a in found.values())


def test_a_question_inside_a_summary_is_read_once():
    page = c.read_html(ACCORDION, "index.html")
    questions = [f.question for f in page.faq]
    assert questions.count("Que fait Acme ?") == 1


def test_a_bibliography_never_answers_a_question():
    """Extracted answers came from reference notes on the calibration site."""
    page = c.read_html(
        "<main><h1>Acme</h1><p>Acme turns recorded speech into captions locally.</p>"
        "<h2>Bibliography</h2><p>How Acme works, how to train it, data security. medium.com</p>"
        "</main>",
        "index.html",
    )
    texts = [s.text for s in faq.corpus([page])]
    assert any("captions locally" in t for t in texts)
    assert not any("medium.com" in t for t in texts)


def test_an_answer_too_long_to_quote_is_a_warning():
    long = " ".join(["Acme does one more thing here."] * 5)
    page = c.read_html(f"<main><h2>FAQ</h2><h3>What is Acme?</h3><p>{long}</p></main>", "a.html")
    assert "FAQ005" in rules(faq.audit_faq([page]))


def test_an_answer_that_does_not_name_the_organisation_first_is_a_warning():
    page = c.read_html(
        "<main><h2>FAQ</h2><h3>What happens when I book?</h3>"
        "<p>You pick a slot. A quote follows.</p></main>",
        "a.html",
    )
    assert "FAQ005" in rules(faq.audit_faq([page], organization="Acme"))
    named = c.read_html(
        "<main><h2>FAQ</h2><h3>What happens when I book?</h3>"
        "<p>To book a call with Acme, you pick a slot. A quote follows.</p></main>",
        "a.html",
    )
    assert "FAQ005" not in rules(faq.audit_faq([named], organization="Acme"))
