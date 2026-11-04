"""
test_api_site_routes — /v1/cta, /v1/faq and /v1/findable over HTTP.

The MCP server is these routes, mounted, so what an agent sees is what is
tested here: the pages arrive as text, the CTAs as a parameter, and their
absence is said in the response rather than guessed around.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sprezzature_publish.api import app  # noqa: E402

CLIENT = TestClient(app)

HOME = (
    '<!doctype html><html lang="en"><head><title>Acme</title>'
    '<meta name="robots" content="noindex"></head><body><main><h1>Acme</h1>'
    "<p>Acme is free and open source under the BSD-3 licence, with no paid tier.</p>"
    '<a href="https://calendly.com/acme/demo" class="bg-blue-600 px-4 py-2 text-white">'
    "Book a demo</a></main></body></html>"
)
PAGES = [{"path": "index.html", "content": HOME}]
CTAS = {
    "organization": "Acme",
    "primary": {"label": "Book a demo", "url": "https://calendly.com/acme/demo"},
}


def test_cta_without_declared_ctas_offers_candidates_and_says_what_is_missing():
    body = CLIENT.post("/v1/cta", json={"pages": PAGES}).json()
    assert body["candidates"][0]["url"] == "https://calendly.com/acme/demo"
    assert "Ask the user" in body["note"]


def test_cta_with_declared_ctas_names_the_money_pages():
    body = CLIENT.post("/v1/cta", json={"pages": PAGES, "ctas": CTAS}).json()
    assert body["money_pages"] == ["index.html"]
    assert "note" not in body


def test_faq_answers_from_the_pages_and_ends_on_the_cta():
    body = CLIENT.post("/v1/faq", json={"pages": PAGES, "ctas": CTAS}).json()
    cost = next(i for i in body["items"] if i["question"] == "How much does Acme cost?")
    assert "BSD-3" in cost["answer"]
    assert cost["next_step"] == "[Book a demo](https://calendly.com/acme/demo)"
    assert body["draft"] is True
    assert body["jsonld"]["@type"] == "FAQPage"
    assert any(g["stage"] == "decide" for g in body["gaps"])


def test_faq_audit_reports_markup_without_a_visible_faq():
    ld = (
        '<script type="application/ld+json">{"@type": "FAQPage", "mainEntity": '
        '[{"@type": "Question", "name": "Q?", "acceptedAnswer": {"text": "A."}}]}</script>'
    )
    page = {"path": "a.html", "content": f"<head>{ld}</head><body><p>Hello.</p></body>"}
    body = CLIENT.post("/v1/faq", json={"pages": [page], "audit": True}).json()
    assert [f["rule"] for f in body["findings"]] == ["FAQ002"]


def test_findable_puts_the_money_page_error_first_with_its_goals():
    body = CLIENT.post("/v1/findable", json={"pages": PAGES, "ctas": CTAS}).json()
    first = body["findings"][0]
    assert (first["rule"], first["money_page"]) == ("FIND002", True)
    assert first["goals"] == ["seo", "geo", "aeo"]


def test_every_new_route_has_a_written_summary_and_an_operation_id():
    """FastAPI invents a summary from the function name; the MCP tool shows it."""
    schema = app.openapi()["paths"]
    for path, op in (
        ("/v1/cta", "find_calls_to_action"),
        ("/v1/faq", "build_faq"),
        ("/v1/findable", "report_findability"),
    ):
        post = schema[path]["post"]
        assert post["operationId"] == op
        assert len(post["summary"].split()) >= 6, post["summary"]
