#!/usr/bin/env python3
"""
findable
========

One report for search, generative and answer engines, ordered by what the
site is for.

The three disciplines share their foundations. Google says it outright:
"the same foundations of good SEO apply to generative AI search", and the
levers overlap — crawlable visible text, an answer before the detail, facts
with their source, a page that may be shown with a snippet. So this is one
run, not three tools: the site is read once (every format, through
:mod:`_content`), the declared calls to action are read once
(``ctas.yaml``, from :mod:`cta`), and every finding is tagged with **each**
goal it serves.

Ordered by the CTAs, not by goal
--------------------------------
The declared CTAs define the *money pages*: the pages that carry one, and
the page a CTA lands on. Their findings come first, and some rules are
errors there and nothing elsewhere: a blog post may be ``noindex``; the
pricing page may not.

What it runs
------------
* the existing head and index rules of :mod:`audit_site` (``SITE…``);
* the CTA audit of :mod:`cta` (``CTA…``) and the FAQ audit of :mod:`faq`
  (``FAQ…``);
* the rules below, which only make sense once the CTAs are known.

``FIND001`` (warning; error on a money page) — ``nosnippet`` or
``max-snippet:0``. Google: a page must be "eligible to be shown in Google
Search with a snippet" to appear in its AI features.
``FIND002`` (error) — a money page is ``noindex``.
``FIND003`` (error) — a money page is missing from ``sitemap.xml``.
``FIND004`` (error) — a money page's canonical points at another page.
``FIND005`` (warning) — a money page has no FAQ.
``FIND006`` (info) — a money page states no number, quotation or cited
source. GEO only: AGGARWAL et al. (KDD 2024) measured these three as the
levers that raise visibility in generative answers. Never an error.
``FIND007`` (warning) — a page names the offer and links to no money page.
``FIND008`` (warning) — ``llms.txt`` does not carry the primary CTA.
``FIND009`` (warning) — the organisation is named differently across pages.

``--fix`` writes what the parts already fix deterministically — head tags,
``robots.txt`` and ``sitemap.xml`` (with ``--base-url``), FAQ markup — and
nothing a person has to write. A URL is read, never written.

Exit code
---------
* 0 — no errors.
* 1 — at least one error.
* 2 — nothing to read, or a URL that could not be fetched.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_site as au  # noqa: E402
import faq  # noqa: E402
from _click import run_command, sprezzature_command  # noqa: E402
from _content import PageContent, read_site, read_text  # noqa: E402
from audit_site import ERROR, INFO, WARNING, Finding  # noqa: E402
from cta import (  # noqa: E402
    CtaPlan,
    audit_ctas,
    load_ctas,
    money_pages,
    normalize,
    partials,
    site_hosts,
)

SEO, GEO, AEO = "seo", "geo", "aeo"
ALL: tuple[str, ...] = (SEO, GEO, AEO)

#: Which goals each existing rule serves. A rule missing here is SEO.
GOALS: dict[str, tuple[str, ...]] = {
    "SITE000": ALL,
    "SITE001": ALL,
    "SITE002": ALL,
    "SITE003": (SEO, AEO),
    "SITE004": (SEO,),
    "SITE006": ALL,
    "SITE011": (SEO,),
    "SITE016": (GEO,),
    "SITE100": ALL,
    "SITE101": (SEO,),
    "SITE102": ALL,
    "SITE103": ALL,
    "SITE105": (GEO,),
    "CTA000": ALL,
    "CTA001": ALL,
    "CTA002": ALL,
    "FAQ001": (AEO, GEO),
    "FAQ002": (AEO,),
    "FAQ003": (AEO,),
    "FAQ004": (AEO,),
    "FIND001": ALL,
    "FIND002": ALL,
    "FIND003": (SEO, GEO),
    "FIND004": ALL,
    "FIND005": (AEO,),
    "FIND006": (GEO,),
    "FIND007": (SEO,),
    "FIND008": (GEO,),
    "FIND009": (GEO, AEO),
}


@dataclass
class Tagged:
    """A finding, the goals it serves, and whether it is on a money page."""

    finding: Finding
    goals: tuple[str, ...]
    money: bool = False

    def as_dict(self) -> dict[str, object]:
        f = self.finding
        return {
            "path": f.path,
            "line": f.line,
            "rule": f.rule,
            "severity": f.severity,
            "message": f.message,
            "remedy": f.remedy,
            "goals": list(self.goals),
            "money_page": self.money,
        }


@dataclass
class Report:
    """The joint report: declared CTAs, money pages, findings in order."""

    declared: bool
    money_pages: list[str]
    findings: list[Tagged] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(t.finding.severity == ERROR for t in self.findings)


# ── The rules that need the CTAs ───────────────────────────────────────────


def _page_url(path: str) -> str:
    """``fr/index.html`` → ``/fr``, ``a/b.html`` → ``/a/b.html``."""
    return normalize("/" + path)


def _sitemap_paths(root: Path) -> set[str] | None:
    sitemap = root / "sitemap.xml"
    if not sitemap.is_file():
        return None
    locs = au._sitemap_locs(sitemap.read_text(encoding="utf-8", errors="replace"))
    return {normalize(urllib.parse.urlsplit(loc).path or "/") for loc in locs}


def _robots_tokens(page: PageContent) -> set[str]:
    return {t.strip() for t in re.split(r"[,\s]+", page.robots) if t.strip()}


def _has_fact(page: PageContent) -> bool:
    """A number, a quotation, or a link to a source off the site."""
    text = page.text
    if faq.numbers(text):
        return True
    if re.search(r"[“«\"][^”»\"]{20,}[”»\"]", text):
        return True
    hosts = site_hosts([page])
    return any(
        a.href.startswith(("http://", "https://"))
        and urllib.parse.urlsplit(a.href).netloc.lower().removeprefix("www.") not in hosts
        and a.landmark not in {"nav", "header", "footer"}
        for a in page.actionables
    )


def cta_rules(
    pages: list[PageContent], plan: CtaPlan | None, money: list[str], root: Path | None
) -> list[Finding]:
    """``FIND001`` to ``FIND009``: the findability of what the site is for."""
    out: list[Finding] = []
    money_set = set(money)
    shell = partials(pages)
    sitemap = _sitemap_paths(root) if root is not None else None

    for page in pages:
        if not page.is_page or page.path in shell:
            continue
        tokens = _robots_tokens(page)
        is_money = page.path in money_set
        if "nosnippet" in tokens or "max-snippet:0" in tokens:
            out.append(
                Finding(
                    page.path,
                    0,
                    "FIND001",
                    ERROR if is_money else WARNING,
                    "robots meta forbids a snippet ("
                    + ", ".join(sorted(tokens & {"nosnippet", "max-snippet:0"}))
                    + "); Google shows in its AI features only pages eligible for one.",
                    "remove it unless hiding the text is the point",
                )
            )
        if not is_money:
            continue
        if "noindex" in tokens or "none" in tokens:
            out.append(
                Finding(
                    page.path,
                    0,
                    "FIND002",
                    ERROR,
                    "A money page is noindex: no engine will show it.",
                    "remove noindex from this page",
                )
            )
        if sitemap is not None and _page_url(page.path) not in sitemap:
            out.append(
                Finding(
                    page.path,
                    0,
                    "FIND003",
                    ERROR,
                    "A money page is missing from sitemap.xml.",
                    "--fix --base-url https://… regenerates it",
                )
            )
        if page.canonical:
            target = normalize(urllib.parse.urlsplit(page.canonical).path or "/")
            if target not in {_page_url(page.path), _page_url(page.path).removesuffix(".html")}:
                out.append(
                    Finding(
                        page.path,
                        0,
                        "FIND004",
                        ERROR,
                        f"A money page names another page as canonical ({page.canonical}).",
                        "point the canonical at this page",
                    )
                )
        if not page.faq:
            out.append(
                Finding(
                    page.path,
                    page.main_end_line,
                    "FIND005",
                    WARNING,
                    "A money page has no FAQ: the questions between a reader and the CTA "
                    "go unanswered here, and answer engines find nothing to quote.",
                    "sprezzature-publish-faq <site>",
                )
            )
        if not _has_fact(page):
            out.append(
                Finding(
                    page.path,
                    0,
                    "FIND006",
                    INFO,
                    "No number, quotation or cited source on this money page. Generative "
                    "engines cite pages with facts (AGGARWAL et al., KDD 2024).",
                    "",
                )
            )

    if plan and plan.organization and money_set:
        name = plan.organization.lower()
        targets = {_page_url(m) for m in money_set} | {
            _page_url(m).removesuffix(".html") for m in money_set
        }
        hosts = site_hosts(pages)
        for page in pages:
            if not page.is_page or page.path in shell or page.path in money_set:
                continue
            if page.text.lower().count(name) < 2:
                continue
            links = {normalize(a.href, page.path, hosts) for a in page.actionables if a.href}
            if not links & targets:
                out.append(
                    Finding(
                        page.path,
                        0,
                        "FIND007",
                        WARNING,
                        f"This page names {plan.organization} and links to no money page.",
                        f"link {sorted(money_set)[0]} with words that say what it is",
                    )
                )

    primary = plan.primary if plan else None
    llms = root / "llms.txt" if root is not None else None
    if primary and llms is not None and llms.is_file():
        body = llms.read_text(encoding="utf-8", errors="replace")
        if primary.url not in body and normalize(primary.url) not in body:
            out.append(
                Finding(
                    "llms.txt",
                    0,
                    "FIND008",
                    WARNING,
                    f"llms.txt does not carry the primary CTA ({primary.url}); an agent "
                    "acting for a reader cannot hand it over.",
                    f"sprezzature-publish-indexes … --cta '{primary.label}={primary.url}'",
                )
            )

    names = Counter(
        page.jsonld_names[t]
        for page in pages
        for t in ("Organization", "Corporation", "LocalBusiness")
        if page.jsonld_names.get(t)
    )
    if plan and plan.organization:
        names.update([plan.organization])
    if len(names) > 1:
        out.append(
            Finding(
                "",
                0,
                "FIND009",
                WARNING,
                "The organisation is named "
                + " / ".join(f"'{n}'" for n, _ in names.most_common(4))
                + "; engines attach answers to one name.",
                "use one name everywhere, the one in ctas.yaml",
            )
        )
    return out


# ── The joint run ──────────────────────────────────────────────────────────


def _html_findings(root: Path, *, base_url: str) -> list[Finding]:
    html_pages = au.gather_pages(root)
    out: list[Finding] = []
    if not html_pages:
        return out
    base = au.site_root(root, html_pages)
    for path in html_pages:
        facts = au.scan_page(path.read_text(encoding="utf-8", errors="replace"))
        try:
            where = path.relative_to(base).as_posix()
        except ValueError:
            where = path.name
        out.extend(au.audit_page(where, facts, have_base_url=bool(base_url)))
    for f in au.audit_indexes(base, base_url):
        out.append(f)
    return out


def findable(
    pages: list[PageContent],
    plan: CtaPlan | None,
    *,
    root: Path | None = None,
    base_url: str = "",
    head_findings: list[Finding] | None = None,
) -> Report:
    """Run every rule on one reading of the site and order the result.

    Parameters
    ----------
    pages : list of PageContent
        The site, read once.
    plan : CtaPlan or None
        The declared CTAs; ``None`` is reported (``CTA000``), not guessed.
    root : Path, optional
        The site folder, for the index files. ``None`` for pages sent over
        HTTP, which have no folder.
    base_url : str
        The public origin, when known.
    head_findings : list of Finding, optional
        The ``SITE…`` findings, when the caller already has them; computed
        from ``root`` otherwise.

    Returns
    -------
    Report
        Money pages first, then errors before warnings before advice.
    """
    money = money_pages(pages, plan) if plan and plan.ctas else []
    raw: list[Finding] = []
    if head_findings is not None:
        raw += head_findings
    elif root is not None:
        raw += _html_findings(root, base_url=base_url)
    raw += audit_ctas(pages, plan or CtaPlan())
    raw += faq.audit_faq(pages, organization=plan.organization if plan else "")
    raw += cta_rules(pages, plan, money, root)

    money_set = set(money)
    tagged = [
        Tagged(f, GOALS.get(f.rule, (SEO,)), f.path in money_set or f.path.endswith(tuple(money)))
        for f in raw
    ]
    rank = {ERROR: 0, WARNING: 1, INFO: 2}
    tagged.sort(
        key=lambda t: (not t.money, rank.get(t.finding.severity, 3), t.finding.rule, t.finding.path)
    )
    return Report(declared=bool(plan and plan.ctas), money_pages=money, findings=tagged)


def render_text(report: Report, per_rule: int = 6) -> str:
    """The report as text: money pages first, at most ``per_rule`` lines a rule."""
    lines = []
    if report.money_pages:
        lines.append("Money pages: " + ", ".join(report.money_pages[:8]))
    else:
        lines.append(
            "No money pages: declare the CTAs first (sprezzature-publish-cta), "
            "so the report knows what the site is for."
        )
    shown: Counter[str] = Counter()
    total = Counter(t.finding.rule for t in report.findings)
    section = None
    for t in report.findings:
        head = "On money pages" if t.money else "Elsewhere"
        if head != section:
            section = head
            lines.append(f"\n{head}:")
        f = t.finding
        shown[f.rule] += 1
        if shown[f.rule] > per_rule:
            continue
        where = f"{f.path}:{f.line}" if f.line else (f.path or "site")
        lines.append(f"{where}: {f.severity}: {f.rule} [{'+'.join(t.goals)}]: {f.message}")
        if f.remedy:
            lines.append(f"    → {f.remedy}")
        if shown[f.rule] == per_rule and total[f.rule] > per_rule:
            lines.append(f"    … and {total[f.rule] - per_rule} more {f.rule} (--format json)")
    goals = Counter(g for t in report.findings for g in t.goals)
    lines.append(
        f"\n{len(report.findings)} finding(s), {report.errors} error(s); "
        + ", ".join(f"{g.upper()} {goals[g]}" for g in ALL)
    )
    return "\n".join(lines)


def fix_site(root: Path, *, base_url: str, lang: str) -> list[str]:
    """Apply every deterministic repair the parts already know. Returns paths."""
    written: list[str] = []
    html_pages = au.gather_pages(root)
    base = au.site_root(root, html_pages) if html_pages else root
    for path in html_pages:
        text = path.read_text(encoding="utf-8", errors="replace")
        facts = au.scan_page(text)
        try:
            rel = path.relative_to(base)
        except ValueError:
            rel = Path(path.name)
        insertions = au.plan_insertions(
            facts, root=base, page_rel=rel, base_url=base_url, theme_color="", og_image=""
        )
        new = au.apply_fix(text, facts, insertions, lang)
        if new != text:
            path.write_text(new, encoding="utf-8")
            written.append(rel.as_posix())
    if base_url:
        written += [p.name for p in au._fix_indexes(base, base_url, dry_run=False)]
    written += faq.fix_faq(read_site(root), root)
    return written


# ── CLI ────────────────────────────────────────────────────────────────────


@sprezzature_command(
    "sprezzature-publish-findable",
    help=(
        "One report for search, generative and answer engines (SEO, GEO, AEO), "
        "ordered by the site's declared calls to action: money pages first, each "
        "finding tagged with every goal it serves. --fix applies the "
        "deterministic repairs; a URL is only ever read."
    ),
    epilog=(
        "Examples:\n\n"
        "\b\n"
        "  sprezzature-publish-findable site/\n"
        "  sprezzature-publish-findable site/ --ctas ctas.yaml --base-url https://example.org --fix\n"
        "  sprezzature-publish-findable https://example.org/pricing\n"
        "  sprezzature-publish-findable site/ --format json\n"
    ),
)
@click.argument("target")
@click.option(
    "--ctas",
    "ctas_path",
    type=click.Path(path_type=Path),
    default=None,
    help="The declared CTAs. Default: ctas.yaml in the site folder, when present.",
)
@click.option("--base-url", default="", help="The site's public origin, e.g. https://example.org.")
@click.option("--lang", default="", help="With --fix: the lang attribute to add where missing.")
@click.option("--fix", is_flag=True, help="Apply the deterministic repairs, then report.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format. Default: text.",
)
def cli(target: str, ctas_path: Path | None, base_url: str, lang: str, fix: bool, fmt: str) -> int:
    """Report what stands between the site and the engines, CTA first."""
    if au.is_url(target):
        if fix:
            click.echo("sprezzature-publish-findable: --fix cannot write to a URL.", err=True)
            return 2
        status, body = au.fetch(target)
        if status != 200 or not body:
            click.echo(f"sprezzature-publish-findable: could not fetch {target}", err=True)
            return 2
        path = urllib.parse.urlsplit(target).path.lstrip("/") or "index.html"
        page = read_text(body, path if "." in Path(path).name else path + "/index.html", "html")
        plan = load_ctas(ctas_path) if ctas_path and ctas_path.is_file() else None
        parsed = urllib.parse.urlsplit(target)
        heads = au.audit_page(target, au.scan_page(body), have_base_url=True)
        heads += au.audit_remote_indexes(f"{parsed.scheme}://{parsed.netloc}")
        report = findable([page] if page else [], plan, head_findings=heads)
    else:
        root = Path(target)
        if not root.exists():
            click.echo(f"sprezzature-publish-findable: no such path: {root}", err=True)
            return 2
        site = root if root.is_dir() else root.parent
        if fix:
            for p in fix_site(site, base_url=base_url, lang=lang):
                click.echo(f"→ repaired {p}", err=True)
        pages = read_site(root)
        if not pages:
            click.echo(f"sprezzature-publish-findable: nothing to read under {root}", err=True)
            return 2
        ctas_file = ctas_path or (site / "ctas.yaml")
        plan = load_ctas(ctas_file) if ctas_file.is_file() else None
        report = findable(pages, plan, root=site, base_url=base_url)

    if fmt == "json":
        click.echo(
            json.dumps(
                {
                    "declared": report.declared,
                    "money_pages": report.money_pages,
                    "findings": [t.as_dict() for t in report.findings],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        click.echo(render_text(report))
    return 1 if report.errors else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    return run_command(cli, argv)


if __name__ == "__main__":
    raise SystemExit(main())
