#!/usr/bin/env python3
"""
audit_site
==========

Audit an **emitted** site — and repair what has one deterministic repair.

Every other tool in this package writes something: pages, an icon set, the
indexes crawlers read. This one is the return trip. It opens what is
actually there and says what a search engine, a social-preview card or a
generative engine will fail to find — then, with ``--fix``, writes back the
part of that which can be derived rather than invented.

It takes a **local directory**, a single HTML file, or a **live URL**. There
is no Markdown anywhere in its contract: a site somebody else built, or one
built here years ago, is the normal case rather than the exception. The
Markdown path stays where it belongs, in ``lint_markdown``, which gates the
source *before* anything renders it.

What it checks
--------------

Per page (``SITE0xx``) — the ``<head>`` surfaces that decide whether a page
is findable and shareable: ``<title>``, ``description``, ``canonical``,
``lang``, ``viewport``, the Open Graph set, the Twitter Card, JSON-LD,
``theme-color``, and the icon / manifest links.

Per site (``SITE1xx``) — the files that live beside the pages:
``robots.txt`` (and whether it names the sitemap), ``sitemap.xml`` (and
whether it still matches the pages on disk), ``llms.txt``, a feed, and the
icon set as the ``favicons`` tool emits it.

What ``--fix`` will write, and what it refuses to
-------------------------------------------------

The dividing line is **derived vs. invented**, the same one
``lint_markdown`` draws around its ``--ai`` suggestions: a rewrite that can
be computed from what the page already says is applied; a sentence that
needs a judgement is reported with the command that drafts it.

Written:

* ``canonical`` — from ``--base-url`` and the file's own path.
* ``viewport``, and ``lang`` when ``--lang`` says which.
* ``og:title`` / ``og:description`` / ``og:url`` / ``og:type`` — mirrored
  from the page's own ``<title>``, ``description`` and canonical.
* ``twitter:card`` / ``twitter:title`` / ``twitter:description`` — mirrored
  from the Open Graph set (``summary_large_image`` when an ``og:image``
  exists, ``summary`` otherwise).
* the icon and manifest ``<link>``s — copied from the ``head.html`` the
  ``favicons`` tool already wrote, or synthesised from the icon files
  actually present.
* ``theme-color``, when ``--theme-color`` says which.
* ``robots.txt`` and ``sitemap.xml`` — regenerated through
  :mod:`site_indexes`, so there is one implementation of each, not two.
* the folk GEO tags (``ai-content``, ``ai-overview-priority``,
  ``geo-ranking``) are **removed**: they are blog-post inventions, not
  specifications. See ``references/seo-essentials.md``.

Refused, and reported instead: the text of ``<title>`` and
``description``, the choice of ``og:image``, the JSON-LD ``@type`` and body,
and the ``llms.txt`` summary. Those come from
``sprezzature-publish-meta`` and ``sprezzature-publish-indexes``, where a
person reviews them before they land in a file.

What it deliberately does not own
---------------------------------

**Image alt text and accessibility.** ``sprezzature-accessibility`` already
reads raw HTML with no Markdown behind it, and its ``--fix-alt`` drafts the
alt from the image and the surrounding page. This tool does not duplicate
a line of it; it only checks ``og:image:alt``, which is a social-preview
surface rather than an accessibility one, and prints the command to run.

On a remote URL
---------------

A URL is **reported, never repaired**: ``--fix`` against a URL is a usage
error, not a silent no-op. Fetching covers the page plus the origin's
``robots.txt``, ``sitemap.xml`` and ``llms.txt``.

Specs honored
-------------

Every rule cites a specification or the search engine's own documentation;
where no such document exists, the rule says so rather than pretending.
``references/audit-site.md`` carries the rule-by-rule table. The short list:

* HTML — WHATWG HTML Living Standard (``lang``, ``title``, metadata names,
  ``theme-color``, ``rel=icon``): https://html.spec.whatwg.org/
* Canonical URLs — RFC 6596: https://datatracker.ietf.org/doc/html/rfc6596
* Open Graph — https://ogp.me/
* Twitter Cards — https://developer.x.com/en/docs/twitter-for-websites/cards/overview/markup
* Structured data — JSON-LD 1.1 (W3C Rec) + schema.org
* Icons and PWA — W3C Web Application Manifest: https://www.w3.org/TR/appmanifest/
* Apple touch icon — Apple, Configuring Web Applications
* robots.txt — RFC 9309 (IETF Proposed Standard, 2022):
  https://datatracker.ietf.org/doc/html/rfc9309
* Sitemaps — https://www.sitemaps.org/protocol.html
* llms.txt — https://llmstxt.org/ (a proposal, not a standards-body document)
* Feeds — RFC 4287 (Atom 1.0) / RSS 2.0

Three rules have no specification behind them and say so: the
description-length window (observed rendering, hence a warning), the folk
GEO tags (the absence of a spec *is* the finding), and ``SITE112``, a house
rule about this package's own commonest failure.

Usage
-----
::

    # A site somebody else built, on disk
    python scripts/audit_site.py public/ --base-url https://example.com

    # The same, repairing what is derivable
    python scripts/audit_site.py public/ --base-url https://example.com --fix

    # See what --fix would change, touching nothing
    python scripts/audit_site.py public/ --base-url https://example.com --dry-run

    # A live page
    python scripts/audit_site.py https://example.com/about

    # For CI
    python scripts/audit_site.py public/ --base-url https://example.com --format json

Exit code
---------
* 0 — no errors (warnings and notes do not affect it).
* 1 — one or more errors.
* 2 — nothing to audit, or ``--fix`` asked against a URL.

Notes
-----
* Python 3.10+, standard library only. Fetching a URL uses ``urllib``.
* Idempotent: running ``--fix`` twice changes nothing the second time.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import http.client
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _click import run_command, sprezzature_command  # noqa: E402
from site_indexes import (  # noqa: E402
    WEB_OUTPUT_DIRS,
    _format_url,
    _today_iso,
    discover_pages,
    render_robots,
    render_sitemap,
)

# ── Severity levels ────────────────────────────────────────────────────────

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclass
class Finding:
    """One audit finding, and the one command that resolves it.

    ``path`` holds a file path or a URL, so the JSON shape stays the one
    ``lint_markdown`` emits and a CI parser reads both without branching.
    """

    path: str
    line: int  # 1-indexed; 0 when the finding is about the site, not a line
    rule: str  # short id e.g. "SITE004"
    severity: str  # ERROR / WARNING / INFO
    message: str
    remedy: str = ""  # what to run, or "" when --fix handles it


# ── What a page says about itself ──────────────────────────────────────────

#: Open Graph properties ogp.me calls required. ``og:image`` is required
#: too, but it names a file nobody can derive, so it is tracked apart.
OG_REQUIRED: tuple[str, ...] = ("og:title", "og:type", "og:url", "og:description")

#: Meta names that blog posts claim generative engines read. None of them
#: appear in any specification; see references/seo-essentials.md.
FOLK_GEO_NAMES: frozenset[str] = frozenset(
    {"ai-content", "ai-overview-priority", "geo-ranking", "ai-index", "llm-content"}
)

#: Google's stated bounds for a useful meta description, in characters.
DESCRIPTION_MIN, DESCRIPTION_MAX = 120, 155


@dataclass
class PageFacts:
    """Everything the audit needs to know about one page's ``<head>``."""

    lang: str | None = None
    html_line: int = 0
    title: str | None = None
    names: dict[str, str] = field(default_factory=dict)  # <meta name=…>
    properties: dict[str, str] = field(default_factory=dict)  # <meta property=…>
    links: dict[str, str] = field(default_factory=dict)  # rel → href (first wins)
    # Every (rel, href) pair, because a correct <head> carries several
    # rel="icon" lines — the .ico and one PNG per size — and a map keyed
    # on rel alone cannot tell which of them a page already has.
    link_pairs: list[tuple[str, str]] = field(default_factory=list)
    folk_tags: list[tuple[str, int]] = field(default_factory=list)  # (name, line)
    has_jsonld: bool = False
    has_head: bool = False


class HeadScanner(HTMLParser):
    """Collect the ``<head>`` facts the audit rules read.

    A parser rather than a pile of regexes because attribute order, quoting
    style and self-closing slashes are all author's choice, and a regex that
    tolerates every spelling stops being readable long before it stops being
    wrong.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.facts = PageFacts()
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record one opening tag's contribution to :class:`PageFacts`."""
        a = {k.lower(): (v or "") for k, v in attrs}
        line = self.getpos()[0]
        if tag == "html":
            self.facts.lang = a.get("lang") or None
            self.facts.html_line = line
        elif tag == "head":
            self.facts.has_head = True
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = a.get("name", "").lower()
            prop = a.get("property", "").lower()
            content = a.get("content", "")
            if name in FOLK_GEO_NAMES:
                self.facts.folk_tags.append((name, line))
            elif name:
                self.facts.names.setdefault(name, content)
            # Twitter's own docs use name=, Open Graph uses property=, and
            # half the web mixes them. Index both spellings under the key
            # the rules ask for rather than making every rule ask twice.
            if prop:
                self.facts.properties.setdefault(prop, content)
            if name.startswith(("og:", "twitter:")):
                self.facts.properties.setdefault(name, content)
        elif tag == "link":
            rel = a.get("rel", "").lower().strip()
            if rel:
                href = a.get("href", "")
                self.facts.links.setdefault(rel, href)
                self.facts.link_pairs.append((rel, href))
        elif tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self.facts.has_jsonld = True

    def handle_endtag(self, tag: str) -> None:
        """Close the title so stray text after ``</title>`` is not collected."""
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        """Accumulate the document title's text."""
        if self._in_title:
            self.facts.title = ((self.facts.title or "") + data).strip() or None


def scan_page(text: str) -> PageFacts:
    """Parse one HTML document and return its ``<head>`` facts."""
    scanner = HeadScanner()
    scanner.feed(text)
    scanner.close()
    return scanner.facts


# ── Per-page rules ─────────────────────────────────────────────────────────


def audit_page(where: str, facts: PageFacts, *, have_base_url: bool) -> list[Finding]:
    """Check one page's ``<head>`` against the findability surfaces.

    Parameters
    ----------
    where : str
        File path or URL, used as the finding's location.
    facts : PageFacts
        Output of :func:`scan_page`.
    have_base_url : bool
        Whether ``--base-url`` was supplied. Without it a canonical URL
        cannot be derived, so the remedy changes rather than the verdict.

    Returns
    -------
    list of Finding
        Findings in rule order.
    """
    out: list[Finding] = []

    def add(rule: str, sev: str, msg: str, remedy: str = "") -> None:
        out.append(Finding(where, 0, rule, sev, msg, remedy))

    if not facts.has_head:
        add("SITE000", ERROR, "No <head> element — nothing here is findable.")
        return out

    # ── The base every page must have ─────────────────────────────────
    if not facts.lang:
        out.append(
            Finding(
                where,
                facts.html_line,
                "SITE001",
                ERROR,
                "<html> has no lang attribute — screen readers and search "
                "engines both guess, and both guess wrong.",
                "--fix --lang <code>",
            )
        )
    if not facts.title:
        add(
            "SITE002",
            ERROR,
            "No <title>. Nothing derives it; a page needs a human to name it.",
            "sprezzature-publish-meta <page> --site-name '<brand>'",
        )
    description = facts.names.get("description", "").strip()
    if not description:
        add(
            "SITE003",
            ERROR,
            'No <meta name="description">.',
            "sprezzature-publish-meta <page> --site-name '<brand>'",
        )
    elif not DESCRIPTION_MIN <= len(description) <= DESCRIPTION_MAX:
        add(
            "SITE004",
            WARNING,
            f"Description is {len(description)} characters; Google shows "
            f"roughly {DESCRIPTION_MIN}–{DESCRIPTION_MAX}.",
            "sprezzature-publish-meta <page>",
        )
    if "viewport" not in facts.names:
        add("SITE005", WARNING, "No viewport meta — the page will not scale on a phone.")
    if "canonical" not in facts.links:
        add(
            "SITE006",
            ERROR,
            'No <link rel="canonical"> — duplicate URLs compete with each other.',
            "" if have_base_url else "--fix --base-url https://…",
        )

    # ── Open Graph: the social preview ────────────────────────────────
    missing_og = [p for p in OG_REQUIRED if p not in facts.properties]
    if missing_og:
        derivable = facts.title and description
        add(
            "SITE007",
            WARNING,
            f"Open Graph incomplete: missing {', '.join(missing_og)}. Links "
            "shared to LinkedIn, Slack, iMessage, WhatsApp and Discord all "
            "read these.",
            "" if derivable else "fix <title> and description first — og mirrors them",
        )
    if "og:image" not in facts.properties:
        add(
            "SITE008",
            WARNING,
            "No og:image — the shared card will be a bare line of text.",
            "pass --og-image <url>, or draft one with sprezzature-publish-meta",
        )
    elif not facts.properties.get("og:image:alt", "").strip():
        add(
            "SITE009",
            INFO,
            "og:image has no og:image:alt. This is the preview card's "
            "description, not the page's — sprezzature-accessibility owns "
            "the images inside the page.",
            "sprezzature-publish-meta <page>   # returns og_image_alt",
        )
    if "twitter:card" not in facts.properties:
        add("SITE010", WARNING, "No twitter:card — X renders the link unstyled.")

    # ── Structured data and chrome ────────────────────────────────────
    if not facts.has_jsonld:
        add(
            "SITE011",
            WARNING,
            "No JSON-LD block. Generative engines read structured data to "
            "decide what a page *is* before deciding whether to cite it.",
            "sprezzature-publish-meta <page>   # returns schema_type",
        )
    if "theme-color" not in facts.names:
        add(
            "SITE012",
            INFO,
            "No theme-color — mobile browser chrome will not match the site.",
            "--fix --theme-color '#RRGGBB'",
        )

    # ── Icons, as seen from the page ──────────────────────────────────
    if not any(r.startswith("icon") or r == "shortcut icon" for r in facts.links):
        add("SITE013", ERROR, "No favicon link of any kind in <head>.")
    if "apple-touch-icon" not in facts.links:
        # Apple documents two fallbacks, and a modern one that inverts the
        # advice: the root directory is searched for `apple-touch-icon.png`
        # when no link element names one, and the manifest icons take
        # precedence *only* when no apple-touch-icon is declared in the head.
        # So a page carrying a manifest has made a choice, not a mistake.
        # https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html
        if "manifest" in facts.links:
            add(
                "SITE014",
                INFO,
                "No apple-touch-icon link. With a manifest present this is a "
                "choice Apple supports — its icons take precedence precisely "
                "when no apple-touch-icon is declared here.",
            )
        else:
            add(
                "SITE014",
                WARNING,
                "No apple-touch-icon link and no manifest — iOS falls back to "
                "/apple-touch-icon.png, and screenshots the page if that is "
                "missing too.",
            )
    if "manifest" not in facts.links:
        add("SITE015", WARNING, "No web app manifest link — the site cannot be installed.")

    # ── Tags that look like GEO and are not ───────────────────────────
    for name, line in facts.folk_tags:
        out.append(
            Finding(
                where,
                line,
                "SITE016",
                INFO,
                f'<meta name="{name}"> is not in any specification — no '
                "engine reads it. See references/seo-essentials.md.",
                "",
            )
        )
    return out


# ── Per-site rules ─────────────────────────────────────────────────────────

#: The icon set ``favicons.py`` emits, mapped to the severity of its
#: absence. Kept in step with that script's ``PNG_SIZES`` / ``ICO_SIZES``;
#: ``test_audit_site.py`` fails if the two drift apart.
ICON_SET: dict[str, str] = {
    "favicon.ico": ERROR,
    "favicon-16.png": WARNING,
    "favicon-32.png": WARNING,
    "favicon-48.png": INFO,
    "icon-192.png": WARNING,
    "icon-512.png": WARNING,
    "icon-maskable-512.png": INFO,
    "apple-touch-icon.png": WARNING,
    "site.webmanifest": WARNING,
}

#: Feed file names in the wild. Any one of them satisfies the feed check.
FEED_NAMES: tuple[str, ...] = ("feed.atom", "atom.xml", "feed.xml", "rss.xml", "feed.rss")


#: ``<loc>`` with an optional namespace prefix. ``render_sitemap`` builds
#: the document through ElementTree, which serialises the sitemaps.org
#: namespace as ``<ns0:loc>``; a pattern anchored on the bare tag matched
#: nothing, so every sitemap this package writes read as empty and the sync
#: check reported all of its pages as missing.
LOC_RE = re.compile(r"<(?:[\w.-]+:)?loc>(.*?)</(?:[\w.-]+:)?loc>", re.S)


def _sitemap_locs(text: str) -> set[str]:
    """Extract the ``<loc>`` values from a sitemap document.

    Parsed with a regex rather than ElementTree on purpose: a sitemap that
    is malformed should still yield the URLs it does contain, so the sync
    check reports a drift rather than dying on someone else's XML.
    """
    return {m.group(1).strip() for m in LOC_RE.finditer(text)}


def audit_indexes(root: Path, base_url: str) -> list[Finding]:
    """Check the files that sit beside the pages: robots, sitemap, llms, feed.

    Parameters
    ----------
    root : Path
        Directory holding the emitted site.
    base_url : str
        Site origin. Empty when ``--base-url`` was not supplied, which
        downgrades the sitemap sync check to "cannot be verified".

    Returns
    -------
    list of Finding
    """
    out: list[Finding] = []
    where = str(root)
    gen = f"sprezzature-publish-indexes --root {root} --base-url {base_url or 'https://…'}"

    robots = root / "robots.txt"
    if not robots.is_file():
        out.append(Finding(where, 0, "SITE100", ERROR, "No robots.txt.", gen))
    else:
        body = robots.read_text(encoding="utf-8", errors="replace")
        if "sitemap:" not in body.lower():
            out.append(
                Finding(
                    where,
                    0,
                    "SITE101",
                    WARNING,
                    "robots.txt does not name the sitemap, so a crawler has to guess the URL.",
                    "",
                )
            )

    sitemap = root / "sitemap.xml"
    if not sitemap.is_file():
        out.append(Finding(where, 0, "SITE102", ERROR, "No sitemap.xml.", gen))
    elif base_url:
        listed = _sitemap_locs(sitemap.read_text(encoding="utf-8", errors="replace"))
        expected = {_format_url(base_url, p) for p in discover_pages(root)}
        missing = sorted(expected - listed)
        stale = sorted(listed - expected)
        if missing:
            shown = ", ".join(missing[:5]) + (" …" if len(missing) > 5 else "")
            out.append(
                Finding(
                    where,
                    0,
                    "SITE103",
                    ERROR,
                    f"{len(missing)} page(s) exist but are not in sitemap.xml: {shown}",
                    "",
                )
            )
        if stale:
            shown = ", ".join(stale[:5]) + (" …" if len(stale) > 5 else "")
            out.append(
                Finding(
                    where,
                    0,
                    "SITE104",
                    WARNING,
                    f"{len(stale)} sitemap entr(y/ies) point at pages that no "
                    f"longer exist: {shown}",
                    "",
                )
            )

    if not (root / "llms.txt").is_file():
        out.append(
            Finding(
                where,
                0,
                "SITE105",
                WARNING,
                "No llms.txt. It is the one artifact generative engines look "
                "for by name, and it needs a summary a person writes.",
                gen,
            )
        )
    if not any((root / name).is_file() for name in FEED_NAMES):
        out.append(
            Finding(
                where,
                0,
                "SITE106",
                INFO,
                "No feed. A site that publishes anything dated should offer one.",
                f"{gen} --feed-from posts    # or: sprezzature-publish-changelog",
            )
        )
    return out


def audit_icon_files(root: Path) -> list[Finding]:
    """Check the icon set on disk against what ``favicons.py`` emits."""
    out: list[Finding] = []
    where = str(root)
    missing = [(name, sev) for name, sev in ICON_SET.items() if not (root / name).is_file()]
    if len(missing) == len(ICON_SET):
        out.append(
            Finding(
                where,
                0,
                "SITE110",
                ERROR,
                "No icon set at all — not one of the files favicons emits is here.",
                f"sprezzature-publish-icons <logo> --out {root}",
            )
        )
        return out
    for name, sev in missing:
        out.append(
            Finding(
                where,
                0,
                "SITE111",
                sev,
                f"Icon set incomplete: {name} is missing.",
                f"sprezzature-publish-icons <logo> --out {root}",
            )
        )
    return out


# ── Repair ─────────────────────────────────────────────────────────────────

HEAD_CLOSE_RE = re.compile(r"(?P<indent>[ \t]*)</head\s*>", re.I)
HTML_OPEN_RE = re.compile(r"<html(?![\w-])(?P<attrs>[^>]*)>", re.I)


def _esc(value: str) -> str:
    """Escape a string for use inside a double-quoted HTML attribute."""
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def icon_head_lines(root: Path, facts: PageFacts) -> list[str]:
    """Return the icon / manifest ``<link>``s this page is missing.

    Prefers the ``head.html`` that :mod:`favicons` already wrote — which is
    the whole point of that file, and the step everyone forgets — and falls
    back to synthesising from the icon files actually on disk.
    """
    present = set(facts.link_pairs)
    snippet = root / "head.html"
    candidates: list[str] = []
    if snippet.is_file():
        candidates = [
            ln.strip()
            for ln in snippet.read_text(encoding="utf-8", errors="replace").splitlines()
            if ln.strip()
        ]
    else:
        if (root / "favicon.svg").is_file():
            candidates.append('<link rel="icon" href="/favicon.svg" type="image/svg+xml">')
        if (root / "favicon.ico").is_file():
            candidates.append('<link rel="icon" href="/favicon.ico" sizes="any">')
        for size in (32, 16):
            if (root / f"favicon-{size}.png").is_file():
                candidates.append(
                    f'<link rel="icon" href="/favicon-{size}.png" '
                    f'sizes="{size}x{size}" type="image/png">'
                )
        if (root / "apple-touch-icon.png").is_file():
            candidates.append(
                '<link rel="apple-touch-icon" href="/apple-touch-icon.png" sizes="180x180">'
            )
        if (root / "site.webmanifest").is_file():
            candidates.append('<link rel="manifest" href="/site.webmanifest">')

    # Keep only the (rel, href) pairs the page does not already carry, so a
    # second run is a no-op and the several rel="icon" sizes all survive.
    # theme-color lines from head.html belong to the meta planner, not here.
    out: list[str] = []
    for line in candidates:
        rel_m = re.search(r'rel="([^"]+)"', line)
        href_m = re.search(r'href="([^"]+)"', line)
        if not rel_m or not href_m:
            continue
        pair = (rel_m.group(1).lower().strip(), href_m.group(1))
        if pair in present:
            continue
        out.append(line)
        present.add(pair)
    return out


def plan_insertions(
    facts: PageFacts,
    *,
    root: Path | None,
    page_rel: Path | None,
    base_url: str,
    theme_color: str,
    og_image: str,
) -> list[str]:
    """Decide which ``<head>`` lines ``--fix`` may legitimately write.

    Every line below is **derived** from something the page or the operator
    already supplied. Nothing here invents prose: a page with no ``<title>``
    gets no ``og:title``, it gets a finding and a command to run.

    Returns
    -------
    list of str
        Lines to insert, in head order. Empty when nothing is derivable.
    """
    add: list[str] = []
    title = facts.title or ""
    description = facts.names.get("description", "").strip()

    canonical = facts.links.get("canonical", "")
    if not canonical and base_url and page_rel is not None:
        canonical = _format_url(base_url, page_rel)
        add.append(f'<link rel="canonical" href="{_esc(canonical)}">')

    if "viewport" not in facts.names:
        add.append(
            '<meta name="viewport" content="width=device-width, '
            'initial-scale=1, viewport-fit=cover">'
        )
    if theme_color and "theme-color" not in facts.names:
        add.append(f'<meta name="theme-color" content="{_esc(theme_color)}">')

    image = facts.properties.get("og:image", "") or og_image
    if og_image and "og:image" not in facts.properties:
        add.append(f'<meta property="og:image" content="{_esc(og_image)}">')

    if title and "og:title" not in facts.properties:
        add.append(f'<meta property="og:title" content="{_esc(title)}">')
    if description and "og:description" not in facts.properties:
        add.append(f'<meta property="og:description" content="{_esc(description)}">')
    if "og:type" not in facts.properties:
        # ogp.me's own default when the property is absent. Mirroring the
        # spec default is derivation; guessing "article" from a folder name
        # would not be.
        add.append('<meta property="og:type" content="website">')
    if canonical and "og:url" not in facts.properties:
        add.append(f'<meta property="og:url" content="{_esc(canonical)}">')

    if "twitter:card" not in facts.properties:
        card = "summary_large_image" if image else "summary"
        add.append(f'<meta name="twitter:card" content="{card}">')
    if title and "twitter:title" not in facts.properties:
        add.append(f'<meta name="twitter:title" content="{_esc(title)}">')
    if description and "twitter:description" not in facts.properties:
        add.append(f'<meta name="twitter:description" content="{_esc(description)}">')

    if root is not None:
        add.extend(icon_head_lines(root, facts))
    return add


def apply_fix(text: str, facts: PageFacts, insertions: list[str], lang: str) -> str:
    """Rewrite one page: drop the folk tags, set ``lang``, insert the lines.

    The document is edited in place rather than re-serialised. A formatter
    that reflows somebody else's HTML to add four meta tags has done more
    damage than the missing tags ever did.
    """
    new = text

    # 1. Folk GEO tags: remove the whole tag, and the line if it held nothing else.
    if facts.folk_tags:
        names = "|".join(re.escape(n) for n, _ in facts.folk_tags)
        new = re.sub(
            rf'^[ \t]*<meta\s+name=["\'](?:{names})["\'][^>]*>[ \t]*\r?\n',
            "",
            new,
            flags=re.I | re.M,
        )
        new = re.sub(rf'<meta\s+name=["\'](?:{names})["\'][^>]*>', "", new, flags=re.I)

    # 2. lang on <html>, only when the operator named one.
    if lang and not facts.lang:
        m = HTML_OPEN_RE.search(new)
        if m:
            new = f'{new[: m.start()]}<html lang="{_esc(lang)}"{m.group("attrs")}>{new[m.end() :]}'

    # 3. The derived head lines, immediately before </head>.
    if insertions:
        m = HEAD_CLOSE_RE.search(new)
        if m:
            indent = m.group("indent") + "  "
            block = "".join(f"{indent}{line}\n" for line in insertions)
            new = new[: m.start()] + block + new[m.start() :]
    return new


# ── Gathering what to audit ────────────────────────────────────────────────

#: Directories never worth walking for emitted pages.
EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".private",
    }
)

#: How long to wait on a remote fetch, in seconds. Matches meta_from_ollama.
FETCH_TIMEOUT: int = 15

#: Sent on every fetch. A site that blocks unknown agents should see who
#: this is rather than a bare Python default.
USER_AGENT: str = "sprezzature-publish-audit (+https://sprezzature.ai)"


def is_url(target: str) -> bool:
    """True when the target names a remote page rather than a local path."""
    return target.lower().startswith(("http://", "https://"))


def gather_pages(target: Path) -> list[Path]:
    """Collect the HTML pages under a directory, or the single file given."""
    if target.is_file():
        return [target]
    out: list[Path] = []
    for p in target.rglob("*.html"):
        if p.is_file() and not any(part in EXCLUDE_DIRS for part in p.parts):
            out.append(p)
    return sorted(out)


def site_root(target: Path, pages: list[Path]) -> Path:
    """Pick the directory the site's indexes and icons should live in.

    For a directory target that is the target itself. For a single file,
    it is the file's own directory — unless that directory is one of the
    conventional build outputs' parent, in which case the build output is
    where ``robots.txt`` would be.
    """
    if target.is_dir():
        return target
    parent = target.parent
    if parent.name in WEB_OUTPUT_DIRS:
        return parent
    return parent


def fetch(url: str) -> tuple[int, str]:
    """GET a URL. Returns ``(status, body)``; status 0 means the fetch failed.

    Every failure comes back as ``(0, "")`` — including a URL that is not a
    URL. ``Request(...)`` used to be built on the line above the ``try``,
    which meant two reachable typos escaped as tracebacks from a tool whose
    caller is ready with a message for them: ``https://[`` raises
    ``ValueError: Invalid IPv6 URL`` (and ``ValueError`` is in the clause
    below, so catching it was always the intent), and ``http://a b/`` raises
    ``http.client.InvalidURL``, which is *not* a ``ValueError`` and needs
    naming. Both pass :func:`is_url`, so both reach here.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:  # noqa: S310
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.status, resp.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, OSError, ValueError, http.client.InvalidURL):
        return 0, ""


def audit_remote_indexes(origin: str) -> list[Finding]:
    """Check robots.txt, sitemap.xml and llms.txt on a live origin."""
    out: list[Finding] = []
    status, robots = fetch(urllib.parse.urljoin(origin, "/robots.txt"))
    if status != 200:
        out.append(Finding(origin, 0, "SITE100", ERROR, "No robots.txt at the origin.", ""))
    elif "sitemap:" not in robots.lower():
        out.append(
            Finding(origin, 0, "SITE101", WARNING, "robots.txt does not name the sitemap.", "")
        )
    if fetch(urllib.parse.urljoin(origin, "/sitemap.xml"))[0] != 200:
        out.append(Finding(origin, 0, "SITE102", ERROR, "No sitemap.xml at the origin.", ""))
    if fetch(urllib.parse.urljoin(origin, "/llms.txt"))[0] != 200:
        out.append(
            Finding(
                origin,
                0,
                "SITE105",
                WARNING,
                "No llms.txt at the origin — the one artifact generative engines look for by name.",
                "",
            )
        )
    return out


# ── Reporting ──────────────────────────────────────────────────────────────

#: Printed under the findings. Two neighbours own work this tool refuses to
#: duplicate, and a reader who does not know that reads a clean report as
#: "my site is fine".
ROUTING_NOTE: str = """
— not audited here, and on purpose —
  Image alt text, labels, headings, contrast of state: that is
  sprezzature-accessibility, which reads raw HTML with no Markdown behind
  it and drafts the missing alt itself:
      sprezzature-accessibility-lint <dir> --fix-alt
  The *wording* of <title>, description, og:image:alt and the JSON-LD body:
      sprezzature-publish-meta <page> --site-name '<brand>'
"""


def render_text(findings: list[Finding]) -> str:
    """Render findings one per line, each followed by its remedy when it has one."""
    lines: list[str] = []
    for f in findings:
        where = f"{f.path}:{f.line}" if f.line else f.path
        lines.append(f"{where}: {f.severity}: {f.rule}: {f.message}")
        if f.remedy:
            lines.append(f"    → {f.remedy}")
    return "\n".join(lines)


def render_json(findings: list[Finding]) -> str:
    """Render findings as the JSON shape ``lint_markdown`` emits, plus ``remedy``."""
    return json.dumps(
        [
            {
                "path": f.path,
                "line": f.line,
                "rule": f.rule,
                "severity": f.severity,
                "message": f.message,
                "remedy": f.remedy,
            }
            for f in findings
        ],
        indent=2,
        ensure_ascii=False,
    )


# ── CLI entry point ────────────────────────────────────────────────────────


@sprezzature_command(
    "sprezzature-publish-audit",
    help=(
        "Audit an emitted site — a local directory, a single page, or a live "
        "URL — for the head meta, icon links and crawler indexes that decide "
        "whether anybody finds it, and repair with --fix what can be derived "
        "rather than invented. No Markdown source required: improving a site "
        "somebody else built is the normal case."
    ),
    epilog=(
        "Examples:\n"
        "  sprezzature-publish-audit public/ --base-url https://example.com\n"
        "  sprezzature-publish-audit public/ --base-url https://example.com --fix --lang en\n"
        "  sprezzature-publish-audit public/ --base-url https://example.com --dry-run\n"
        "  sprezzature-publish-audit https://example.com/about\n"
        "\n"
        "A URL is reported, never repaired: --fix against a URL is an error.\n"
    ),
)
@click.argument("target")
@click.option(
    "--base-url",
    default="",
    metavar="URL",
    help="Site origin, e.g. https://example.com. Needed to derive canonical "
    "URLs and to check the sitemap against the pages on disk.",
)
@click.option(
    "--lang",
    default="",
    metavar="CODE",
    help="BCP 47 code written into <html lang> by --fix when it is missing. "
    "Without it, a missing lang is reported and left alone.",
)
@click.option(
    "--theme-color",
    default="",
    metavar="HEX",
    help="theme-color written by --fix when the page has none.",
)
@click.option(
    "--og-image",
    default="",
    metavar="URL",
    help="Preview image written by --fix when the page has no og:image. "
    "Nothing derives this, so without it the gap is only reported.",
)
@click.option("--fix", is_flag=True, help="Apply the derivable repairs in place. Idempotent.")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print what --fix would change without touching a file. Implies "
    "--fix when used alone. Always exits 0.",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format. Default: text.",
)
def audit(
    target: str,
    base_url: str,
    lang: str,
    theme_color: str,
    og_image: str,
    fix: bool,
    dry_run: bool,
    fmt: str,
) -> int:
    """Audit an emitted site and, with ``--fix``, repair what is derivable."""
    findings: list[Finding] = []

    # ── A live URL: report, never repair ──────────────────────────────
    if is_url(target):
        if fix or dry_run:
            click.echo(
                "sprezzature-publish-audit: --fix cannot write to a URL. Audit "
                "the files on disk, or drop --fix to get a report.",
                err=True,
            )
            return 2
        status, body = fetch(target)
        if status != 200 or not body:
            click.echo(
                f"sprezzature-publish-audit: could not fetch {target} "
                f"(HTTP {status or 'no response'}).",
                err=True,
            )
            return 2
        findings.extend(audit_page(target, scan_page(body), have_base_url=True))
        parsed = urllib.parse.urlparse(target)
        findings.extend(audit_remote_indexes(f"{parsed.scheme}://{parsed.netloc}"))
    else:
        # ── A directory or a single page on disk ──────────────────────
        path = Path(target)
        if not path.exists():
            click.echo(f"sprezzature-publish-audit: no such path: {path}", err=True)
            return 2
        pages = gather_pages(path)
        if not pages:
            click.echo(f"sprezzature-publish-audit: no HTML pages under {path}", err=True)
            return 2
        root = site_root(path, pages)

        # Repair first, then audit what is there *now*. The other order
        # prints a report describing the state before its own repair — a
        # list of errors the run has already fixed, and a non-zero exit for
        # them.
        wrote: list[Path] = []
        would: list[Path] = []
        if fix or dry_run:
            for page in pages:
                text = page.read_text(encoding="utf-8", errors="replace")
                facts = scan_page(text)
                try:
                    rel = page.relative_to(root)
                except ValueError:
                    rel = Path(page.name)
                insertions = plan_insertions(
                    facts,
                    root=root,
                    page_rel=rel,
                    base_url=base_url,
                    theme_color=theme_color,
                    og_image=og_image,
                )
                new_text = apply_fix(text, facts, insertions, lang)
                if new_text == text:
                    continue
                if dry_run:
                    would.append(page)
                else:
                    page.write_text(new_text, encoding="utf-8")
                    wrote.append(page)
            if base_url:
                index_writes = _fix_indexes(root, base_url, dry_run=dry_run)
                (would if dry_run else wrote).extend(index_writes)

        needs_icon_links = False
        for page in pages:
            facts = scan_page(page.read_text(encoding="utf-8", errors="replace"))
            page_findings = audit_page(str(page), facts, have_base_url=bool(base_url))
            findings.extend(page_findings)
            needs_icon_links = needs_icon_links or any(
                f.rule in {"SITE013", "SITE014", "SITE015"} for f in page_findings
            )

        findings.extend(audit_indexes(root, base_url))
        findings.extend(audit_icon_files(root))

        # The signature failure of this package: favicons wrote head.html,
        # and nobody ever pasted it into a page.
        if needs_icon_links and (root / "head.html").is_file():
            findings.append(
                Finding(
                    str(root),
                    0,
                    "SITE112",
                    WARNING,
                    "head.html exists but its links are not in every page — "
                    "the icon set was generated and never referenced.",
                    "--fix pastes it",
                )
            )

        if dry_run:
            click.echo(f"— dry run: {len(would)} file(s) would change —")
            for p in would:
                click.echo(f"  {p}")
        elif fix:
            click.echo(f"— repaired {len(wrote)} file(s) —")
            for p in wrote:
                click.echo(f"  {p}")

    if fmt == "json":
        click.echo(render_json(findings))
    else:
        if findings:
            click.echo(render_text(findings))
        else:
            click.echo("No findings.")
        click.echo(ROUTING_NOTE)

    if dry_run:
        return 0
    return 1 if any(f.severity == ERROR for f in findings) else 0


def _fix_indexes(root: Path, base_url: str, *, dry_run: bool) -> list[Path]:
    """Regenerate robots.txt and sitemap.xml through :mod:`site_indexes`.

    Only these two: they are fully determined by the origin and the pages
    on disk. ``llms.txt`` needs a summary somebody writes, so it stays a
    finding with the command that drafts it.
    """
    changed: list[Path] = []
    sitemap_url = _format_url(base_url, Path("sitemap.xml"))
    wanted = {
        root / "robots.txt": render_robots(base_url, sitemap_url),
        root / "sitemap.xml": render_sitemap(
            base_url, [(p, _today_iso()) for p in discover_pages(root)]
        ),
    }
    for path, body in wanted.items():
        current = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else None
        # The sitemap carries today's date, so compare the URLs it lists
        # rather than the bytes: a same-day rerun must not rewrite the file.
        same = current == body or (
            path.name == "sitemap.xml"
            and current is not None
            and _sitemap_locs(current) == _sitemap_locs(body)
        )
        if same:
            continue
        changed.append(path)
        if not dry_run:
            path.write_text(body, encoding="utf-8")
    return changed


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    return run_command(audit, argv)


if __name__ == "__main__":
    raise SystemExit(main())
