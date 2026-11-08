"""
Every model call goes to the server ``OLLAMA_URL`` names.

The tools print "Cannot reach Ollama at ``OLLAMA_URL``" when a call fails, but
``best_engine_ai_helper.llm.chat`` left to itself resolves its own server: with
``OLLAMA_URL`` set anywhere but the default, the message named one server and
the request went to another. ``lint --ai`` went further and posted to Ollama's
HTTP API by hand, outside the routing every other call takes.

Each check points ``OLLAMA_URL`` at a server that does not exist, intercepts
the HTTP layer, and reads where the request was actually sent.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import _ollama
import faq
import lint_markdown
import pytest

ELSEWHERE = "http://ollama.elsewhere.test:9999"


@pytest.fixture
def elsewhere(monkeypatch):
    monkeypatch.setattr(_ollama, "OLLAMA_URL", ELSEWHERE)
    monkeypatch.setenv("SPREZZATURE_NO_CACHE", "1")
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "message": {"role": "assistant", "content": json.dumps(["a"])},
        "response": json.dumps(["a"]),
        "done": True,
    }
    resp.raise_for_status.return_value = None
    with patch("requests.post", return_value=resp) as post:
        yield post


def _urls(post) -> list[str]:
    return [str(c.args[0] if c.args else c.kwargs.get("url")) for c in post.call_args_list]


def test_the_engine_names_ollama_url(elsewhere) -> None:
    engine = _ollama.ollama_engine("qwen3-vl:8b")
    assert engine["base_url"] == ELSEWHERE
    assert engine["llm"]["model"] == "qwen3-vl:8b"


def test_the_faq_drafter_calls_ollama_url(elsewhere) -> None:
    drafter = faq.model_drafter(no_cache=True)
    assert drafter is not None
    drafter("Say a.")
    urls = _urls(elsewhere)
    assert urls and all(u.startswith(ELSEWHERE) for u in urls), urls


def test_lint_ai_calls_ollama_url_through_best_engine(elsewhere) -> None:
    import best_engine_ai_helper.llm as llm

    with patch.object(llm, "chat", wraps=llm.chat) as chat:
        lint_markdown.ai_caption_latex("E = mc^2", "en", "qwen3-vl:8b")
    assert chat.called, "lint --ai bypassed best-engine-ai-helper"
    urls = _urls(elsewhere)
    assert urls and all(u.startswith(ELSEWHERE) for u in urls), urls
