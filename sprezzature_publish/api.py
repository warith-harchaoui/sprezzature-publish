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

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import RedirectResponse
except ImportError as exc:  # pragma: no cover - dependency guard
    raise ImportError(
        "The FastAPI HTTP surface requires the [api] extra. "
        "Install with: pip install 'sprezzature-publish[api]'"
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

    Needs nothing beyond the standard library, which is why it is the one
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
            detail="rendering needs the [html] extra: pip install 'sprezzature-publish[html]'",
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
            "pip install 'sprezzature-publish[prose]'",
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
