"""
test_audit_site — coverage for ``scripts/audit_site.py``.

The audit is the half of this package that reads what the other half wrote,
so most of what is worth testing here is a boundary rather than a happy
path: what ``--fix`` is allowed to write, what it must refuse, and whether
running it twice is a no-op.

Three of these exist because the tool got them wrong first. The icon paste
dropped every ``rel="icon"`` after the first, because it deduplicated on the
relation and a correct ``<head>`` carries several. The sitemap check
compared against a directory walk wider than the one the generator uses,
which would have reported build junk as a missing page. And ``discover_pages``
read only Markdown under ``docs/``, so an existing site whose docs are HTML
was absent from every sitemap this package generated.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from pathlib import Path

import audit_site as au
import pytest
import site_indexes as si

# A page with a title and a description and nothing else: the shape of a
# site somebody built by hand years ago, which is this tool's whole point.
BARE = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Example — Acme</title>
  <meta name="description" content="A page long enough to sit comfortably inside the window Google shows, which is roughly one plain sentence of real prose.">
</head>
<body><h1>Example</h1></body>
</html>
"""


def rules(findings: list[au.Finding]) -> set[str]:
    """The rule ids in a finding list, for set comparisons."""
    return {f.rule for f in findings}


# ── What the audit sees ────────────────────────────────────────────────────


class TestAuditPage:
    def test_a_bare_page_is_missing_the_findable_surfaces(self):
        found = rules(au.audit_page("p.html", au.scan_page(BARE), have_base_url=True))
        # lang, canonical and a favicon link are errors; the social and
        # structured-data surfaces are warnings.
        assert {"SITE001", "SITE006", "SITE013"} <= found
        assert {"SITE007", "SITE008", "SITE010", "SITE011"} <= found
        # It has a title and a usable description, so those stay quiet.
        assert "SITE002" not in found and "SITE003" not in found

    def test_a_short_description_is_a_warning_not_an_error(self):
        page = BARE.replace(
            BARE.split('content="')[1].split('"')[0],
            "Too short.",
        )
        found = rules(au.audit_page("p.html", au.scan_page(page), have_base_url=True))
        assert "SITE004" in found

    def test_a_document_with_no_head_stops_at_the_first_finding(self):
        found = au.audit_page("p.html", au.scan_page("<p>hi</p>"), have_base_url=True)
        assert [f.rule for f in found] == ["SITE000"]

    def test_the_folk_geo_tags_are_named_as_folklore(self):
        page = BARE.replace(
            "</head>", '  <meta name="ai-overview-priority" content="high">\n</head>'
        )
        findings = au.audit_page("p.html", au.scan_page(page), have_base_url=True)
        folk = [f for f in findings if f.rule == "SITE016"]
        assert len(folk) == 1
        assert "not in any specification" in folk[0].message

    def test_twitter_name_and_og_property_spellings_both_count(self):
        """Half the web writes ``og:`` with ``name=`` and Twitter with
        ``property=``. A page that did so was being told it had neither."""
        page = BARE.replace(
            "</head>",
            '  <meta name="og:title" content="X">\n'
            '  <meta property="twitter:card" content="summary">\n</head>',
        )
        facts = au.scan_page(page)
        assert "og:title" in facts.properties
        assert "twitter:card" in facts.properties


# ── What --fix may write, and what it must refuse ──────────────────────────


class TestPlanInsertions:
    def test_it_mirrors_what_the_page_already_says(self):
        lines = au.plan_insertions(
            au.scan_page(BARE),
            root=None,
            page_rel=Path("index.html"),
            base_url="https://example.com",
            theme_color="",
            og_image="",
        )
        joined = "\n".join(lines)
        assert 'rel="canonical" href="https://example.com/"' in joined
        assert 'property="og:title" content="Example — Acme"' in joined
        assert 'property="og:url" content="https://example.com/"' in joined
        assert 'name="twitter:card" content="summary"' in joined

    def test_it_invents_nothing_when_the_page_says_nothing(self):
        """The line this tool must not cross. A page with no title and no
        description gets findings and the command that drafts them — never a
        title derived from a filename."""
        empty = "<html><head><meta charset='utf-8'></head><body></body></html>"
        lines = au.plan_insertions(
            au.scan_page(empty),
            root=None,
            page_rel=Path("index.html"),
            base_url="https://example.com",
            theme_color="",
            og_image="",
        )
        joined = "\n".join(lines)
        assert "og:title" not in joined
        assert "og:description" not in joined
        assert "twitter:title" not in joined
        # og:image names a file nobody can derive.
        assert "og:image" not in joined

    def test_an_og_image_upgrades_the_twitter_card(self):
        lines = au.plan_insertions(
            au.scan_page(BARE),
            root=None,
            page_rel=Path("index.html"),
            base_url="https://example.com",
            theme_color="",
            og_image="https://example.com/card.png",
        )
        assert any('content="summary_large_image"' in ln for ln in lines)


class TestApplyFix:
    def test_it_writes_lang_only_when_told_which(self):
        facts = au.scan_page(BARE)
        assert "<html>" in au.apply_fix(BARE, facts, [], "")
        assert '<html lang="en">' in au.apply_fix(BARE, facts, [], "en")

    def test_it_removes_the_folk_geo_tags(self):
        page = BARE.replace("</head>", '  <meta name="geo-ranking" content="1">\n</head>')
        out = au.apply_fix(page, au.scan_page(page), [], "")
        assert "geo-ranking" not in out
        # and nothing else was disturbed
        assert "<title>Example — Acme</title>" in out

    def test_it_does_not_reflow_the_rest_of_the_document(self):
        """A formatter that reflows somebody else's HTML to add four meta
        tags has done more damage than the missing tags ever did."""
        facts = au.scan_page(BARE)
        out = au.apply_fix(BARE, facts, ['<meta name="viewport" content="x">'], "")
        for line in BARE.splitlines():
            if line.strip():
                assert line in out


# ── End to end, on a directory ─────────────────────────────────────────────


@pytest.fixture
def site(tmp_path: Path) -> Path:
    """A two-page site with no indexes and no icons."""
    (tmp_path / "index.html").write_text(BARE, encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.html").write_text(BARE, encoding="utf-8")
    return tmp_path


class TestEndToEnd:
    def test_fix_is_idempotent(self, site: Path):
        args = [str(site), "--base-url", "https://example.com", "--fix", "--lang", "en"]
        assert au.main(args) in (0, 1)
        first = (site / "index.html").read_text(encoding="utf-8")
        assert au.main(args) in (0, 1)
        assert (site / "index.html").read_text(encoding="utf-8") == first

    def test_fix_writes_the_indexes_it_can_derive(self, site: Path):
        au.main([str(site), "--base-url", "https://example.com", "--fix"])
        assert (site / "robots.txt").is_file()
        assert (site / "sitemap.xml").is_file()
        # llms.txt needs a summary a person writes, so it stays a finding.
        assert not (site / "llms.txt").is_file()

    def test_the_sitemap_lists_html_docs_too(self, site: Path):
        """``discover_pages`` read only Markdown under ``docs/``, so an
        existing site whose docs are HTML was silently absent from its own
        sitemap."""
        au.main([str(site), "--base-url", "https://example.com", "--fix"])
        locs = au._sitemap_locs((site / "sitemap.xml").read_text(encoding="utf-8"))
        assert "https://example.com/docs/guide.html" in locs

    def test_a_stale_sitemap_is_reported(self, site: Path):
        (site / "sitemap.xml").write_text(
            '<?xml version="1.0"?><urlset><loc>https://example.com/gone.html</loc></urlset>',
            encoding="utf-8",
        )
        findings = au.audit_indexes(site, "https://example.com")
        found = rules(findings)
        assert "SITE103" in found  # pages that exist and are not listed
        assert "SITE104" in found  # a listing that points at nothing

    def test_build_junk_is_not_reported_as_a_missing_page(self, site: Path):
        """The measure has to place a known-good case on the good side:
        ``discover_pages`` excludes unknown directories on purpose, so a
        stray page under ``logs/`` must not read as a sitemap gap."""
        (site / "logs").mkdir()
        (site / "logs" / "leak.html").write_text(BARE, encoding="utf-8")
        au.main([str(site), "--base-url", "https://example.com", "--fix"])
        findings = au.audit_indexes(site, "https://example.com")
        assert "SITE103" not in rules(findings)

    def test_the_report_describes_the_state_after_the_repair(self, site, capsys):
        """It reported first and repaired second, so ``--fix`` printed a list
        of errors it had just fixed and exited 1 for them."""
        code = au.main([str(site), "--base-url", "https://example.com", "--fix", "--lang", "en"])
        out = capsys.readouterr().out
        assert "SITE001" not in out  # lang: written by this very run
        assert "SITE006" not in out  # canonical: likewise
        assert "SITE100" not in out  # robots.txt: likewise
        # What is left needs a logo or a sentence somebody writes, so the
        # run still fails — honestly.
        assert code == 1
        assert "SITE110" in out

    def test_a_url_refuses_to_be_repaired(self, site: Path):
        assert au.main(["https://example.com", "--fix"]) == 2

    def test_a_missing_path_is_a_usage_error(self, tmp_path: Path):
        assert au.main([str(tmp_path / "nowhere")]) == 2


# ── Icons ──────────────────────────────────────────────────────────────────


class TestIcons:
    @staticmethod
    def _site_with_snippet(capsys) -> Path:
        """A site carrying a generated ``head.html`` that no page references."""
        import tempfile

        root = Path(tempfile.mkdtemp())
        (root / "index.html").write_text(BARE, encoding="utf-8")
        (root / "head.html").write_text(
            '<link rel="icon" href="/favicon.ico" sizes="any">\n', encoding="utf-8"
        )
        return root

    def test_the_expected_set_matches_what_favicons_emits(self):
        """The two lists are written out separately, in two files. This is
        what notices when one of them moves."""
        import favicons as fav

        for size in fav.PNG_SIZES:
            name = f"icon-{size}.png" if size >= 192 else f"favicon-{size}.png"
            assert name in au.ICON_SET, f"favicons emits {name}; the audit does not look for it"
        assert "favicon.ico" in au.ICON_SET
        assert "apple-touch-icon.png" in au.ICON_SET
        assert f"icon-maskable-{fav.MASKABLE_SIZE}.png" in au.ICON_SET

    def test_the_paste_keeps_every_icon_size(self, site: Path):
        """The bug this caught: deduplicating on the relation alone dropped
        every ``rel="icon"`` after the first, and a correct head carries
        several — the .ico plus one PNG per size."""
        (site / "head.html").write_text(
            '<link rel="icon" href="/favicon.ico" sizes="any">\n'
            '<link rel="icon" href="/favicon-32.png" sizes="32x32" type="image/png">\n'
            '<link rel="manifest" href="/site.webmanifest">\n',
            encoding="utf-8",
        )
        lines = au.icon_head_lines(site, au.scan_page(BARE))
        assert len(lines) == 3

    def test_a_generated_head_snippet_nobody_pasted_is_reported(self, capsys):
        """The signature failure of this package: ``favicons`` wrote
        ``head.html``, and nobody ever pasted it into a page."""
        site = self._site_with_snippet(capsys)
        au.main([str(site), "--base-url", "https://example.com", "--format", "json"])
        assert "SITE112" in capsys.readouterr().out

    def test_no_icon_set_at_all_is_one_finding_not_nine(self, site: Path):
        findings = au.audit_icon_files(site)
        assert [f.rule for f in findings] == ["SITE110"]


# ── The contract with the neighbours ───────────────────────────────────────


class TestRouting:
    def test_the_report_names_who_owns_alt_text(self):
        """This tool must not grow an alt-text checker. The note is what
        keeps a clean report from reading as 'my site is fine'."""
        assert "sprezzature-accessibility" in au.ROUTING_NOTE
        assert "--fix-alt" in au.ROUTING_NOTE
        assert "sprezzature-publish-meta" in au.ROUTING_NOTE

    def test_og_image_alt_is_this_tool_s_business(self):
        """The one alt it does own: the social card's, which is a preview
        surface rather than an accessibility one."""
        page = BARE.replace("</head>", '  <meta property="og:image" content="/card.png">\n</head>')
        findings = au.audit_page("p.html", au.scan_page(page), have_base_url=True)
        alt = [f for f in findings if f.rule == "SITE009"]
        assert len(alt) == 1
        assert "sprezzature-accessibility owns the images inside the page" in alt[0].message


# ── discover_pages, which this tool leans on ───────────────────────────────


def test_discover_pages_sees_html_docs(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.html").write_text("<title>G</title>", encoding="utf-8")
    (tmp_path / "docs" / "guide.md").write_text("# G", encoding="utf-8")
    names = {p.as_posix() for p in si.discover_pages(tmp_path)}
    assert {"docs/guide.html", "docs/guide.md"} <= names


# ── Every rule has a citation ──────────────────────────────────────────────


def test_every_rule_is_cited_in_the_reference():
    """A check earns its place by citing a specification, or by saying out
    loud that none exists. A rule that appears in the code and nowhere in
    ``references/audit-site.md`` is an opinion with a rule number."""
    import re

    root = Path(__file__).resolve().parent.parent
    source = (root / "scripts" / "audit_site.py").read_text(encoding="utf-8")
    reference = (root / "references" / "audit-site.md").read_text(encoding="utf-8")

    emitted = set(re.findall(r'"(SITE\d{3})"', source))
    assert emitted, "no rules found in the source — did the quoting change?"
    uncited = sorted(r for r in emitted if r not in reference)
    assert not uncited, f"rules with no entry in references/audit-site.md: {uncited}"


def test_the_reference_cites_no_rule_that_no_longer_exists():
    """The other direction: a citation outliving its rule reads as coverage
    the tool does not have."""
    import re

    root = Path(__file__).resolve().parent.parent
    source = (root / "scripts" / "audit_site.py").read_text(encoding="utf-8")
    reference = (root / "references" / "audit-site.md").read_text(encoding="utf-8")

    emitted = set(re.findall(r'"(SITE\d{3})"', source))
    documented = set(re.findall(r"`(SITE\d{3})`", reference))
    orphans = sorted(documented - emitted)
    assert not orphans, f"cited in the reference, emitted by nothing: {orphans}"


@pytest.mark.parametrize(
    "target",
    [
        "https://[",       # ValueError: Invalid IPv6 URL
        "http://a b/",     # http.client.InvalidURL — not a ValueError
        "https://",        # no host at all
    ],
)
def test_a_typed_url_that_is_not_a_url_comes_back_as_a_failed_fetch(target: str) -> None:
    """``fetch`` promises ``(0, "")`` on failure, and a typo is a failure.

    All three pass ``is_url`` — they start with a scheme — so all three reach
    ``fetch``, and all three used to raise out of it: ``Request(...)`` was
    built on the line *above* the ``try``. The caller is already holding the
    message for this case ("could not fetch … (HTTP no response)"), so what a
    reader got instead was a traceback for a mistyped argument.

    No network: every one of these dies in URL parsing, before a socket.
    """
    assert au.fetch(target) == (0, "")
