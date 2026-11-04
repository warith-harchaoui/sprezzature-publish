"""
test_findable — the joint SEO + GEO + AEO report, ordered by the CTAs.

A rule that is an error on a money page and silence elsewhere is the
reason this report exists, so most cases below compare the same defect on
the two kinds of page.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json

import findable as fd
from _content import read_site
from cta import CtaPlan, CtaSpec

PLAN = CtaPlan(
    offer="Local captions.",
    organization="Acme",
    ctas=[CtaSpec("Book a demo", "https://calendly.com/acme/demo", "", "decide", True)],
)

MONEY = """<!doctype html><html lang="en"><head><title>Acme</title>{head}</head>
<body><header><a href="/">Acme</a></header><main><h1>Acme</h1>
<p>Acme writes captions in 3 minutes for an hour of audio.</p>
<a href="https://calendly.com/acme/demo" class="bg-blue-600 px-4 py-2 text-white">Book a demo</a>
</main></body></html>
"""

POST = """<!doctype html><html lang="en"><head><title>A post</title>{head}</head>
<body><main><h1>Notes</h1><p>Acme handles speech. Acme is local.</p></main></body></html>
"""


def build(tmp_path, money_head="", post_head="", plan=PLAN):
    (tmp_path / "index.html").write_text(MONEY.format(head=money_head), encoding="utf-8")
    (tmp_path / "post.html").write_text(POST.format(head=post_head), encoding="utf-8")
    return fd.findable(read_site(tmp_path), plan, root=tmp_path)


def rule_on(report, rule, path):
    return [t for t in report.findings if t.finding.rule == rule and t.finding.path == path]


def test_nosnippet_is_an_error_on_a_money_page_and_a_warning_elsewhere(tmp_path):
    meta = '<meta name="robots" content="nosnippet">'
    report = build(tmp_path, meta, meta)
    assert rule_on(report, "FIND001", "index.html")[0].finding.severity == "error"
    assert rule_on(report, "FIND001", "post.html")[0].finding.severity == "warning"


def test_noindex_matters_only_on_a_money_page(tmp_path):
    meta = '<meta name="robots" content="noindex">'
    report = build(tmp_path, meta, meta)
    assert rule_on(report, "FIND002", "index.html")
    assert not rule_on(report, "FIND002", "post.html")


def test_a_money_page_outside_the_sitemap_is_an_error(tmp_path):
    (tmp_path / "sitemap.xml").write_text(
        "<urlset><url><loc>https://acme.test/post.html</loc></url></urlset>", encoding="utf-8"
    )
    report = build(tmp_path)
    assert rule_on(report, "FIND003", "index.html")


def test_a_canonical_pointing_elsewhere_is_an_error(tmp_path):
    report = build(tmp_path, '<link rel="canonical" href="https://acme.test/other.html">')
    assert rule_on(report, "FIND004", "index.html")
    ok = build(tmp_path, '<link rel="canonical" href="https://acme.test/">')
    assert not rule_on(ok, "FIND004", "index.html")


def test_money_page_findings_come_first_and_carry_their_goals(tmp_path):
    report = build(tmp_path)
    assert report.money_pages == ["index.html"]
    assert report.findings[0].money
    faq_missing = rule_on(report, "FIND005", "index.html")[0]
    assert faq_missing.goals == ("aeo",)


def test_a_page_that_names_the_offer_and_never_links_it_is_reported(tmp_path):
    report = build(tmp_path)
    assert rule_on(report, "FIND007", "post.html")


def test_llms_txt_without_the_primary_cta_is_reported(tmp_path):
    (tmp_path / "llms.txt").write_text("# Acme\n\n> Local captions.\n", encoding="utf-8")
    assert [t.finding.rule for t in build(tmp_path).findings].count("FIND008") == 1
    (tmp_path / "llms.txt").write_text(
        "# Acme\n\n> Local captions. Book: https://calendly.com/acme/demo\n", encoding="utf-8"
    )
    assert "FIND008" not in [t.finding.rule for t in build(tmp_path).findings]


def test_two_names_for_one_organisation_are_reported(tmp_path):
    ld = (
        '<script type="application/ld+json">{"@type": "Organization", "name": "ACME Inc."}</script>'
    )
    report = build(tmp_path, ld)
    assert [t for t in report.findings if t.finding.rule == "FIND009"]


def test_no_declared_cta_is_said_not_guessed(tmp_path):
    report = build(tmp_path, plan=None)
    assert not report.declared
    assert "CTA000" in [t.finding.rule for t in report.findings]


def test_a_page_with_facts_is_not_advised_to_add_them(tmp_path):
    report = build(tmp_path)  # "3 minutes" is a number
    assert not rule_on(report, "FIND006", "index.html")


def test_the_cli_reports_json_and_fails_on_errors(tmp_path, capsys):
    build(tmp_path, '<meta name="robots" content="noindex">')
    (tmp_path / "ctas.yaml").write_text(
        "organization: Acme\nprimary: {label: Book a demo, url: 'https://calendly.com/acme/demo'}\n",
        encoding="utf-8",
    )
    assert fd.main([str(tmp_path), "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["money_pages"] == ["index.html"]
    assert any(
        f["rule"] == "FIND002" and f["goals"] == ["seo", "geo", "aeo"] for f in data["findings"]
    )


def test_fix_never_writes_to_a_url():
    assert fd.main(["https://example.org", "--fix"]) == 2
