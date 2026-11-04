"""
test_cta_ground_truth — the CTA detector measured against hand labels.

The detector only proposes: the author declares the CTAs in ``ctas.yaml``.
But a proposal that misses the site's booking button, or offers a book's
``/book`` URL as one, makes the author type what the tool should have
offered. So it is measured, on copies of two real sites labelled once by
reading them (``tests/fixtures/cta/labels.yaml``), and the numbers are
printed on every run, not only asserted.

The floors are below today's figures on purpose: they catch a regression,
not a one-point drift. The traps under ``never`` are asserted one by one,
because each of them is a mistake the detector made first.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

from pathlib import Path

import cta
import pytest
import yaml
from _content import read_site

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cta"
LABELS = yaml.safe_load((FIXTURES / "labels.yaml").read_text(encoding="utf-8"))
SITES = sorted(LABELS["cta"])

#: Measured 2026-11-04: precision 1.00 and recall 1.00 on both sites.
PRECISION_FLOOR = 0.85
RECALL_FLOOR = 0.85


def predicted_pairs(site: str) -> set[tuple[str, str]]:
    """Every (page, destination) the detector calls a CTA on one site."""
    pages = read_site(FIXTURES / site)
    hosts = cta.site_hosts(pages)
    return {
        (page.path, occ.dest)
        for page in pages
        for occ in cta.score_page(page, hosts)
        if occ.score >= cta.THRESHOLD and occ.dest
    }


def labelled_pairs(section: str, site: str) -> set[tuple[str, str]]:
    return {
        (page, dest) for page, dests in (LABELS[section].get(site) or {}).items() for dest in dests
    }


@pytest.mark.parametrize("site", SITES)
def test_precision_and_recall_hold(site):
    predicted = predicted_pairs(site)
    truth = labelled_pairs("cta", site)
    hits = predicted & truth
    precision = len(hits) / len(predicted) if predicted else 0.0
    recall = len(hits) / len(truth)
    print(
        f"\n{site}: precision {precision:.2f} ({len(hits)}/{len(predicted)}), "
        f"recall {recall:.2f} ({len(hits)}/{len(truth)})"
    )
    for page, dest in sorted(predicted - truth):
        print(f"  false positive  {page}  {dest}")
    for page, dest in sorted(truth - predicted):
        print(f"  missed          {page}  {dest}")
    assert precision >= PRECISION_FLOOR, sorted(predicted - truth)
    assert recall >= RECALL_FLOOR, sorted(truth - predicted)


def kind_of(dest: str) -> str:
    return "install" if " " in dest else cta.classify(dest)[0]


@pytest.mark.parametrize("site", SITES)
def test_no_kind_of_cta_is_lost_entirely(site):
    """A global floor forgives a whole category going missing.

    Two mail links out of 26 is 92 % recall, above the floor, and it is
    every contact route on the site. So each kind keeps half its own.
    """
    predicted = predicted_pairs(site)
    by_kind: dict[str, set[tuple[str, str]]] = {}
    for pair in labelled_pairs("cta", site):
        by_kind.setdefault(kind_of(pair[1]), set()).add(pair)
    lost = {
        kind: sorted(pairs - predicted)
        for kind, pairs in by_kind.items()
        if len(pairs & predicted) / len(pairs) < 0.5
    }
    assert not lost, lost


@pytest.mark.parametrize("site", SITES)
def test_no_known_trap_is_called_a_cta(site):
    caught = predicted_pairs(site) & labelled_pairs("never", site)
    assert not caught, caught


@pytest.mark.parametrize("site", SITES)
def test_the_first_candidate_is_the_one_the_site_is_for(site):
    candidates = cta.detect_ctas(read_site(FIXTURES / site))
    assert candidates, "nothing detected"
    assert candidates[0].url == LABELS["top"][site], [c.url for c in candidates[:5]]


def test_every_trap_is_read_at_all():
    """The `never` pairs must be read at all, or the trap test proves nothing."""
    for site in SITES:
        read = {
            (page.path, cta.normalize(act.href, page.path, cta.site_hosts([page])))
            for page in read_site(FIXTURES / site)
            for act in page.actionables
            if act.href
        }
        missing = labelled_pairs("never", site) - read
        assert not missing, f"{site}: trap never read, so never tested: {missing}"


@pytest.mark.parametrize(
    ("dest", "kind"),
    [
        ("https://tobyord.com/book", "page"),
        ("/book", "book"),
        ("/en/book.html", "book"),
        ("https://canonical.com/blog/x", "page"),
        ("https://cal.com/someone", "book"),
        ("/docs/62_newsletter.html", "page"),
        ("/newsletter", "subscribe"),
        ("/demo/screenshots", "page"),
        ("https://example.org/pricing", "page"),
        ("/pricing", "buy"),
        ("https://buy.stripe.com/abc", "buy"),
    ],
)
def test_paths_count_on_the_site_services_anywhere(dest, kind):
    assert cta.classify(dest)[0] == kind


def test_an_absolute_link_to_the_site_itself_is_internal():
    hosts = frozenset({"example.org"})
    assert cta.normalize("https://www.example.org/book/", "", hosts) == "/book"
    assert cta.classify(cta.normalize("https://example.org/book", "", hosts))[0] == "book"


def test_a_folder_of_kits_is_one_line():
    kits = [
        cta.Candidate(f"kit {n}", f"/kits/{n}.zip", "download", "evaluate", 11.0, [f"{n}.html"], [])
        for n in "abc"
    ]
    star = cta.Candidate("star", "https://github.com/a/b", "star", "evaluate", 14.0, ["i.html"], [])
    folded = cta.families([*kits, star])
    assert [c.url for c in folded] == ["https://github.com/a/b", "/kits/*.zip"]
    assert folded[1].pages == ["a.html", "b.html", "c.html"]
