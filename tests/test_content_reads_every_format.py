"""
test_content_reads_every_format — the site reader behind cta, faq, findable.

A site keeps its content in HTML, PHP templates, Markdown and data files.
The one CTA that mattered on the calibration site sat in ``layouts/nav.php``,
and its FAQ-like entries in JSON. Each case below is a shape the reader has
to see, or a thing it has to leave out, written small enough to read.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json

import _content as c


def kinds(page):
    return [(a.kind, a.text, c.decode_href(a.href)) for a in page.actionables]


# ── FAQ, in every form it takes ────────────────────────────────────────────


def test_a_faq_heading_in_html_is_read_with_its_answers():
    page = c.read_html(
        "<main><h2>Frequently asked questions</h2>"
        "<h3>Is it free?</h3><p>Yes, under BSD-3.</p>"
        "<h3>Does it run offline?</h3><p>Yes.</p></main>",
        "a.html",
    )
    assert [(f.question, f.answer) for f in page.faq] == [
        ("Is it free?", "Yes, under BSD-3."),
        ("Does it run offline?", "Yes."),
    ]
    assert page.faq_heading_line


def test_a_french_faq_heading_counts_too():
    page = c.read_html("<h2>Questions fréquentes</h2><h3>C'est gratuit ?</h3><p>Oui.</p>", "a.html")
    assert [f.question for f in page.faq] == ["C'est gratuit ?"]


def test_details_and_definition_lists_are_faqs():
    page = c.read_html(
        "<details><summary>Is it free?</summary><p>Yes.</p></details>"
        "<dl><dt>Does it run offline?</dt><dd>Yes, entirely.</dd></dl>",
        "a.html",
    )
    assert {(f.question, f.origin) for f in page.faq} >= {
        ("Is it free?", "details"),
        ("Does it run offline?", "dl"),
    }


def test_a_faq_only_in_json_ld_is_kept_apart_from_the_visible_one():
    ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": "What is it?",
                "acceptedAnswer": {"@type": "Answer", "text": "<p>A <b>suite</b>.</p>"},
            }
        ],
    }
    page = c.read_html(
        f'<head><script type="application/ld+json">{json.dumps(ld)}</script></head>'
        "<body><h1>Home</h1></body>",
        "index.html",
    )
    assert page.faq == []
    assert [(f.question, f.answer) for f in page.jsonld_faq] == [("What is it?", "A suite.")]
    assert "FAQPage" in page.jsonld_types


def test_a_faq_in_markdown_is_read_and_located():
    text = "# Title\n\nIntro.\n\n## FAQ\n\n### Is it free?\n\nYes.\n"
    page = c.read_markdown(text, "a.md")
    assert [f.question for f in page.faq] == ["Is it free?"]
    assert page.faq_heading_line == 5
    assert page.faq[0].line == 7


def test_question_and_answer_pairs_in_data_are_a_faq():
    page = c.read_text(
        "faq:\n  - question: Is it free?\n    answer: Yes.\n  - question: Not a question\n"
        "    answer: ignored\n",
        "data/faq.yaml",
    )
    assert page is not None
    assert [(f.question, f.origin) for f in page.faq] == [("Is it free?", "data")]


# ── Actionable elements ────────────────────────────────────────────────────


def test_an_entity_encoded_mailto_reads_as_a_mailto():
    page = c.read_html(
        '<a href="&#109;&#97;&#105;&#108;&#116;&#111;&#58;a&#37;&#52;&#48;b.org">Write</a>',
        "a.html",
    )
    assert c.decode_href(page.actionables[0].href) == "mailto:a@b.org"


def test_a_php_template_prints_its_html_and_names_its_includes():
    text = (
        "<?php require __DIR__ . '/header.php'; ?>\n"
        '<nav><a href="https://calendly.com/x/y" class="bg-blue-600 px-4 py-2">'
        "<?= $label ?>Book</a></nav>\n"
        "<?php include 'footer.php';\n"
        "?>\n"
    )
    page = c.read_text(text, "layouts/nav.php")
    assert page is not None and page.fmt == "php"
    assert page.includes == ["header.php", "footer.php"]
    [act] = page.actionables
    assert (act.text, act.landmark, act.line) == ("Book", "nav", 2)


def test_a_button_with_no_text_is_named_by_its_aria_label():
    page = c.read_html(
        '<main><a href="k.zip" download aria-label="Download the archive">⬇</a></main>', "a.html"
    )
    [act] = page.actionables
    assert "download" in act.attrs
    assert act.text == "Download the archive"


def test_a_search_form_is_not_an_actionable_and_a_lead_form_is():
    page = c.read_html(
        '<form role="search" action="/search"><input type="search" name="q"></form>'
        '<form action="https://buttondown.com/x"><input type="email" name="email">'
        '<button type="submit">Subscribe</button></form>',
        "a.html",
    )
    forms = [a for a in page.actionables if a.kind == "form"]
    assert [c.decode_href(f.href) for f in forms] == ["https://buttondown.com/x"]


def test_an_install_command_in_a_code_block_is_an_actionable():
    page = c.read_markdown("Install:\n\n```bash\n$ pip install sprezzature\n```\n", "a.md")
    assert ("install", "pip install sprezzature", "") in kinds(page)


def test_the_hero_is_main_before_its_first_h2():
    page = c.read_html(
        '<main><h1>X</h1><a href="/start">Start</a><h2>More</h2><a href="/docs">Docs</a></main>',
        "a.html",
    )
    assert [(a.text, a.hero) for a in page.actionables] == [("Start", True), ("Docs", False)]


def test_a_label_printed_twice_by_an_animated_export_is_read_once():
    page = c.read_html('<a href="/c"><span>Contact</span><span>Contact</span></a>', "a.html")
    assert page.actionables[0].text == "Contact"


def test_urls_in_data_are_destinations_with_their_label():
    page = c.read_text(
        json.dumps({"items": [{"title": "Portfolio", "url": "/portfolio"}, {"id": "x"}]}),
        "data/items.json",
    )
    assert page is not None
    assert kinds(page) == [("data", "Portfolio", "/portfolio")]


# ── What is not content ────────────────────────────────────────────────────


def test_lockfiles_build_folders_and_minified_files_are_skipped(tmp_path):
    (tmp_path / "index.html").write_text('<a href="/x">X</a>', encoding="utf-8")
    (tmp_path / "package-lock.json").write_text('{"url": "https://registry/x"}', encoding="utf-8")
    (tmp_path / "app.min.json").write_text('{"url": "/y"}', encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "a.html").write_text("<a href='/z'>Z</a>", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "b.html").write_text("<a href='/z'>Z</a>", encoding="utf-8")
    assert [p.path for p in c.read_site(tmp_path)] == ["index.html"]


def test_a_data_file_that_does_not_parse_is_not_content():
    assert c.read_text("{not json", "broken.json") is None


def test_php_line_numbers_survive_stripping():
    text = "<?php\n$a = 1;\n$b = 2;\n?>\n<p>Hello there, reader.</p>\n"
    assert c.strip_php(text).splitlines()[4] == "<p>Hello there, reader.</p>"
