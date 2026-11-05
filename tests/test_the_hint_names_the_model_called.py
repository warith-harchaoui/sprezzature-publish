"""
When the model is unreachable, the hint names the model the call asked for.

``meta`` and ``plain`` told the reader to run ``best-engine-ai-helper pull``
"for this machine's model". That command ranks the hardware and pulls the
best model it finds, while both tools ask for one fixed tag
(``pick_default_model``, ``qwen3-vl:8b``): on most machines the hint pulled a
model the next call would not use, and the call failed again.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import _ollama
import meta_from_ollama
import plain_language
import pytest


def _unreachable(*_args, **_kwargs):
    raise RuntimeError("connection refused")


@pytest.fixture
def fixed_model(monkeypatch) -> str:
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("SPREZZATURE_NO_CACHE", "1")
    return _ollama.pick_default_model()


def test_plain_names_the_model_it_asked_for(fixed_model, monkeypatch, capsys) -> None:
    monkeypatch.setattr(plain_language, "_llm_chat", _unreachable)
    with pytest.raises(SystemExit) as exit_:
        plain_language.rewrite("Leverage our synergies today.", lang="en")
    assert exit_.value.code == 2
    err = capsys.readouterr().err
    assert f"ollama pull {fixed_model}" in err
    assert "best-engine-ai-helper pull" not in err


def test_meta_names_the_model_it_asked_for(fixed_model, monkeypatch, capsys) -> None:
    monkeypatch.setattr(meta_from_ollama, "_llm_chat", _unreachable)
    code = meta_from_ollama.main(["--goal", "Landing page for a lab", "--lang", "en", "--no-cache"])
    assert code == 2
    err = capsys.readouterr().err
    assert f"ollama pull {fixed_model}" in err
    assert "best-engine-ai-helper pull" not in err
