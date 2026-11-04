"""
The HTTP surface — what a build server, or an agent, calls.

Three routes, chosen for what crosses a network boundary well: text in, text
out. Linting Markdown, rendering it and rewriting prose at a reading grade
all have that shape. Generating a favicon set does not — it is a folder of
binaries keyed by filename — so it stays a command rather than being offered
here with an invented download protocol.

A note on the temporary files. The lint and the renderer take a ``Path``,
because they were written for a folder of documents and that is still their
main job: a site is built from files. The routes write the posted text to a
scratch file and hand that over. The alternative was to split each tool into
a text half and a file half, which would have been two code paths for one
behaviour — exactly what this suite spent the week removing. One scratch
file, deleted in a ``finally``, is the smaller cost.

``GET /health`` answers the question worth asking before a batch run: which
optional halves this deployment actually has. A lint-only install is a
supported shape, and discovering by 500 that nobody installed a Markdown
engine is not a good way to find out.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path
from typing import Any

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import RedirectResponse
except ImportError as exc:  # pragma: no cover - dependency guard
    raise ImportError(
        "The FastAPI HTTP surface could not import fastapi, which is a base "
        "dependency since 2026-11-01 -- so this is a broken install rather "
        "than a missing extra. Reinstall with: "
        "pip install 'sprezzature-publish'"
    ) from exc

from pydantic import BaseModel, Field

from sprezzature_publish import __version__

app = FastAPI(
    title="sprezzature-publish",
    version=__version__,
    summary="Markdown in, a page somebody can find out.",
    description=(
        "The text-shaped half of this package, served. Linting, rendering "
        "and plain-language rewriting cross a network boundary cleanly; the "
        "favicon set and the narration do not, and remain commands."
    ),
)

#: Which optional halves this deployment actually has. Probed rather than
#: assumed, because the extras are the whole point of the packaging.
_FEATURES: dict[str, str] = {
    "html": "markdown",
    "prose": "best_engine_ai_helper",
}


def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


class LintRequest(BaseModel):
    """Markdown to audit, as text."""

    markdown: str = Field(description="The document's contents.")
    name: str = Field(
        default="document.md",
        description="Filename to report findings against. Only affects the "
        "messages; the content is what is linted.",
    )


class RenderRequest(BaseModel):
    """Markdown to turn into a page."""

    markdown: str = Field(description="The document's contents.")
    title: str = Field(default="", description="Page title; derived when empty.")
    site_name: str = Field(default="", description="Shown in the page chrome.")
    lang: str = Field(default="en", description="BCP-47 base tag for the page.")
    description: str = Field(default="", description="Meta description for the rendered page.")


class AuditRequest(BaseModel):
    """An emitted page to audit, as text."""

    html: str = Field(description="The page's contents.")
    page_path: str = Field(
        default="index.html",
        description="Path the page will be served at, relative to the site "
        "root. Used with base_url to derive the canonical URL.",
    )
    base_url: str = Field(
        default="",
        description="Site origin, e.g. https://example.com. Without it the "
        "canonical URL cannot be derived, only reported as missing.",
    )
    lang: str = Field(
        default="",
        description="BCP-47 tag written into <html lang> when fix is set and "
        "the page has none. Reported and left alone when empty.",
    )
    theme_color: str = Field(default="", description="theme-color to write when fix is set.")
    og_image: str = Field(default="", description="Preview image URL to write when fix is set.")
    fix: bool = Field(
        default=False,
        description="Also return the repaired page. Nothing is written to "
        "disk — the caller decides what to do with the text.",
    )


class PlainRequest(BaseModel):
    """Prose to rewrite at a reading grade."""

    text: str = Field(description="The prose to rewrite.")
    target_grade: int = Field(default=8, ge=1, le=16, description="Target reading grade.")
    lang: str | None = Field(default=None, description="BCP-47 base tag. Detected when omitted.")
    preserve: list[str] = Field(
        default_factory=list,
        description="Terms to keep verbatim — names, APIs, anything a "
        "simplification would quietly get wrong.",
    )


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get(
    "/health",
    tags=["meta"],
    operation_id="health",
    summary="Check which halves of this package are installed here",
)
def health() -> dict:
    """Liveness, plus which optional extras this deployment actually has."""
    return {
        "status": "ok",
        "version": __version__,
        "features": {name: _installed(mod) for name, mod in _FEATURES.items()},
    }


@app.post(
    "/v1/lint",
    tags=["actions"],
    operation_id="lint_markdown",
    summary="Find what is wrong with a Markdown document",
)
def lint(request: LintRequest) -> dict:
    """Audit Markdown and report every finding.

    Needs nothing beyond click and the standard library, which is why it is the one
    route that always answers. ``render_mermaid`` and the AI pass are off:
    both reach outside this process, and a lint route that silently shells
    out to a diagram renderer is not the millisecond gate it advertises.
    """
    from sprezzature_publish_scripts.lint_markdown import lint_file

    with tempfile.TemporaryDirectory() as scratch:
        document = Path(scratch) / Path(request.name).name
        document.write_text(request.markdown, encoding="utf-8")
        findings, _notes = lint_file(
            document,
            render_mermaid=False,
            out_dir=None,
            fix=False,
            ai=False,
            ai_lang="en",
            ai_model="",
        )

    return {
        "findings_total": len(findings),
        "findings": [
            {
                "rule": f.rule,
                "line": f.line,
                "severity": f.severity,
                "message": f.message,
            }
            for f in findings
        ],
    }


@app.post(
    "/v1/audit",
    tags=["actions"],
    operation_id="audit_site",
    summary="Find what will keep an emitted page from being found or shared",
)
def audit(request: AuditRequest) -> dict:
    """Audit one page's head surfaces, and optionally return it repaired.

    The counterpart of ``/v1/lint``: that one gates the Markdown before it
    renders, this one opens what came out — or a page that never had a
    Markdown source at all, which is the normal shape of improving somebody
    else's site.

    Two rules of the command line still hold here. Repairs are **derived,
    never invented**: a page with no ``<title>`` gets a finding, not a
    guessed one. And the icon and manifest checks are skipped, because they
    read files from a site directory and this route is handed one page of
    text — ``sprezzature-publish-audit`` on the directory covers those.

    Nothing is written: with ``fix`` set, the repaired document comes back
    in the response for the caller to store.
    """
    from sprezzature_publish_scripts.audit_site import (
        apply_fix,
        audit_page,
        plan_insertions,
        scan_page,
    )

    facts = scan_page(request.html)
    findings = [
        f
        for f in audit_page(request.page_path, facts, have_base_url=bool(request.base_url))
        # SITE013/014/015 ask whether the icon files exist beside the page.
        # Over HTTP there is no beside.
        if f.rule not in {"SITE013", "SITE014", "SITE015"}
    ]

    body: dict = {
        "findings_total": len(findings),
        "findings": [
            {
                "rule": f.rule,
                "line": f.line,
                "severity": f.severity,
                "message": f.message,
                "remedy": f.remedy,
            }
            for f in findings
        ],
    }
    if request.fix:
        insertions = plan_insertions(
            facts,
            root=None,
            page_rel=Path(request.page_path),
            base_url=request.base_url,
            theme_color=request.theme_color,
            og_image=request.og_image,
        )
        repaired = apply_fix(request.html, facts, insertions, request.lang)
        body["html"] = repaired
        body["changed"] = repaired != request.html
    return body


@app.post(
    "/v1/render",
    tags=["actions"],
    operation_id="render_markdown",
    summary="Turn a Markdown document into a page",
)
def render(request: RenderRequest) -> dict:
    """Render Markdown to a standalone HTML page."""
    if not _installed("markdown"):
        raise HTTPException(
            status_code=503,
            detail="rendering needs the [html] extra: pip install 'sprezzature-publish'",
        )
    from sprezzature_publish_scripts.md_to_html import convert_one

    with tempfile.TemporaryDirectory() as scratch:
        root_dir = Path(scratch)
        source = root_dir / "document.md"
        source.write_text(request.markdown, encoding="utf-8")
        out_dir = root_dir / "out"
        out_dir.mkdir()
        conversion = convert_one(
            source,
            out_dir,
            title=request.title,
            site_name=request.site_name,
            lang=request.lang,
            description=request.description,
            katex_base="",
        )
        # `Conversion` reports its own outcome — `ok` plus a message — rather
        # than raising, because the command line converts a folder and wants
        # to carry on past one bad file. Over HTTP there is one file, so the
        # message becomes the response.
        if not conversion.ok or not conversion.dst.is_file():
            raise HTTPException(
                status_code=502 if "mermaid" in conversion.message.lower() else 500,
                detail=conversion.message or "the renderer produced no page",
            )
        return {"html": conversion.dst.read_text(encoding="utf-8")}


@app.post(
    "/v1/plain",
    tags=["actions"],
    operation_id="rewrite_plainly",
    summary="Rewrite prose at a target reading grade",
)
def plain(request: PlainRequest) -> dict:
    """Rewrite prose more plainly, keeping the terms the caller names.

    ``draft`` is always true, and says so in every response. A reading-grade
    target is a measurement of sentence length and word frequency; it is not
    a promise that the meaning survived, and only a person who knows the
    subject can check that.
    """
    if not _installed("best_engine_ai_helper"):
        raise HTTPException(
            status_code=503,
            detail="the plain-language rewrite needs the [prose] extra: "
            "pip install 'sprezzature-publish'",
        )
    from sprezzature_publish_scripts.plain_language import rewrite

    return {
        "text": rewrite(
            request.text,
            target_grade=request.target_grade,
            lang=request.lang,
            preserve=request.preserve or None,
        ),
        "draft": True,
    }


# ── What the site is for: CTAs, FAQ, the joint report ──────────────────────


class SitePage(BaseModel):
    """One file of a site, sent as text."""

    path: str = Field(
        description="Path relative to the site root, e.g. pricing.html or "
        "layouts/nav.php. Its suffix picks the reader: html, php, md, json, yaml."
    )
    content: str = Field(description="The file's contents.")


class SiteRequest(BaseModel):
    """A site, as its files, and the calls to action it declares."""

    pages: list[SitePage] = Field(description="Every content file worth reading.")
    ctas: dict | None = Field(
        default=None,
        description="The declared CTAs, in the shape of ctas.yaml: offer, "
        "organization, primary {label, url, audience, stage}, secondary [...]. "
        "Ask the user for them; without them nothing is ranked by what the "
        "site is for, and the response says so.",
    )


class FaqRequest(SiteRequest):
    """A site to draft a FAQ for, or to audit."""

    hints: list[str] = Field(
        default_factory=list,
        description="Real questions, optionally 'question,count'; they rank first.",
    )
    top: int = Field(default=8, ge=1, le=20, description="Items in the section.")
    lang: str = Field(default="", description="en or fr; detected when empty.")
    llm: bool = Field(
        default=False,
        description="Draft answers with the local model. Off by default over "
        "HTTP: the extractive answer is deterministic and costs nothing.",
    )
    audit: bool = Field(default=False, description="Audit the existing FAQs instead.")


class FindableRequest(SiteRequest):
    """A site to report on."""

    base_url: str = Field(default="", description="The public origin, when known.")


def _read_pages(pages: list[SitePage]) -> list:
    from sprezzature_publish_scripts._content import read_text

    out = [read_text(p.content, p.path) for p in pages]
    return [p for p in out if p is not None]


def _plan(raw: dict | None) -> Any:
    from sprezzature_publish_scripts.cta import plan_from_dict

    return plan_from_dict(raw) if raw else None


def _findings(findings: list) -> list[dict]:
    return [
        {
            "path": f.path,
            "line": f.line,
            "rule": f.rule,
            "severity": f.severity,
            "message": f.message,
            "remedy": f.remedy,
        }
        for f in findings
    ]


_NO_CTAS = (
    "No calls to action were declared. Ask the user which one action the site "
    "exists for (and any secondary ones), then send them as `ctas`."
)


@app.post(
    "/v1/cta",
    tags=["actions"],
    operation_id="find_calls_to_action",
    summary="Find a site's calls to action and check every page against the declared ones",
)
def find_ctas(request: SiteRequest) -> dict:
    """Rank the CTAs a site already offers; audit the pages against ``ctas``.

    Detection only proposes. The candidates are what to show the user when
    asking which CTA the site is for; once ``ctas`` is sent, the findings say
    which pages lack it.
    """
    from dataclasses import asdict

    from sprezzature_publish_scripts.cta import audit_ctas, detect_ctas, money_pages

    pages = _read_pages(request.pages)
    plan = _plan(request.ctas)
    body: dict = {"candidates": [asdict(c) for c in detect_ctas(pages)[:10]]}
    if plan and plan.ctas:
        body["money_pages"] = money_pages(pages, plan)
        body["findings"] = _findings(audit_ctas(pages, plan))
    else:
        body["note"] = _NO_CTAS
    return body


@app.post(
    "/v1/faq",
    tags=["actions"],
    operation_id="build_faq",
    summary="Draft the FAQ a site is missing, grounded in its own pages, or audit it",
)
def build_faq_route(request: FaqRequest) -> dict:
    """Draft the FAQ section as Markdown and HTML, with its gap report.

    Every answer comes from a passage of the pages sent, and every number
    in it from that passage; a question the pages cannot answer is listed
    under ``gaps``, never answered. With ``audit``, the existing FAQs and
    their FAQPage markup are checked instead. Nothing is written.
    """
    from sprezzature_publish_scripts.faq import (
        Question,
        audit_faq,
        build_faq,
        faq_jsonld,
        model_drafter,
        render_faq_html,
        render_faq_markdown,
        stage_of,
    )

    pages = _read_pages(request.pages)
    if request.audit:
        return {"findings": _findings(audit_faq(pages))}
    plan = _plan(request.ctas)
    hints = []
    for raw in request.hints:
        text, _, count = raw.rpartition(",")
        if not (text and count.strip().isdigit()):
            text, count = raw, "0"
        hints.append(Question(text.strip(), stage_of(text), "hint", int(count)))
    chat = model_drafter() if request.llm else None
    built = build_faq(pages, plan, hints, top=request.top, lang=request.lang, chat=chat)
    body: dict = {
        "markdown": render_faq_markdown(built),
        "html": render_faq_html(built),
        "jsonld": faq_jsonld(built.items),
        "items": [
            {
                "question": i.question,
                "answer": i.answer,
                "next_step": i.next_step,
                "stage": i.stage,
                "drafted_by": i.drafted_by,
                "sources": [s.page for s in i.sources],
                "notes": i.notes,
            }
            for i in built.items
        ],
        "gaps": [{"question": g.question, "stage": g.stage} for g in built.gaps],
        "placements": [
            {"page": p.page, "line": p.line, "reason": p.reason} for p in built.placements
        ],
        "draft": True,
    }
    if plan is None:
        body["note"] = _NO_CTAS
    return body


@app.post(
    "/v1/findable",
    tags=["actions"],
    operation_id="report_findability",
    summary="One SEO, GEO and AEO report on a site, ordered by its calls to action",
)
def findable_route(request: FindableRequest) -> dict:
    """The joint report on the pages sent, money pages first.

    Head rules run on every HTML page sent; the index files (robots.txt,
    sitemap.xml, llms.txt) are only checked by the command on a folder,
    since a list of pages has no folder to look in.
    """
    from sprezzature_publish_scripts.audit_site import audit_page, scan_page
    from sprezzature_publish_scripts.findable import findable

    pages = _read_pages(request.pages)
    heads = []
    for page in pages:
        if page.fmt == "html":
            heads += [
                f
                for f in audit_page(
                    page.path, scan_page(page.source), have_base_url=bool(request.base_url)
                )
                if f.rule not in {"SITE013", "SITE014", "SITE015"}
            ]
    plan = _plan(request.ctas)
    report = findable(pages, plan, base_url=request.base_url, head_findings=heads)
    body: dict = {
        "declared": report.declared,
        "money_pages": report.money_pages,
        "findings": [t.as_dict() for t in report.findings],
    }
    if plan is None:
        body["note"] = _NO_CTAS
    return body
