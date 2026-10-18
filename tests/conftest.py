"""
Shared pytest configuration.

Puts ``scripts/`` on ``sys.path`` so the test modules can ``import
md_to_html`` directly, which mirrors how the scripts import each other at run
time: they insert their own folder and import siblings by bare name.
Installed, that folder is ``sprezzature_publish_scripts``; from a clone it is
``scripts/``, and these tests have to work from a clone.

Also isolates the on-disk cache and keeps the content-safety scan out of unit
tests that mock the transport — see :func:`no_content_scan`, which is the one
with teeth.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

# `pyproject.toml` maps `scripts/` to the importable name
# `sprezzature_publish_scripts`, which is how the console scripts and the
# library's lazy exports reach it. That mapping exists only after an install,
# so from a clone the same name has to be bound by hand — otherwise every
# test of a *surface* passes or fails for the wrong reason: not because the
# surface is wrong, but because a clone is not an install.
_scripts = types.ModuleType("sprezzature_publish_scripts")
_scripts.__path__ = [str(REPO_ROOT / "scripts")]
sys.modules.setdefault("sprezzature_publish_scripts", _scripts)


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    """Redirect the on-disk cache to a per-test temp directory."""
    monkeypatch.setenv("SPREZZATURE_CACHE_DIR", str(tmp_path / "sprezzature-skill"))
    monkeypatch.delenv("SPREZZATURE_NO_CACHE", raising=False)


@pytest.fixture(autouse=True)
def no_content_scan(monkeypatch):
    """
    Keep the content-safety scan out of unit tests that mock the transport.

    The Ollama-backed tools call ``best_engine_ai_helper.llm.chat``, which
    since 1.4 scans every prompt and response through an NSFW classifier
    before the request leaves. The classifier is an optional extra, so a bare
    install falls back to a keyword heuristic and nothing happens here.

    But on a machine where ``transformers`` is installed for some other
    reason, the scan loads a 270 MB model from HuggingFace, and these tests go
    from "the Ollama call is mocked" to "the suite downloads a model and needs
    the network". That is a CI job failing for a reason nothing here caused,
    and a local run taking seconds where it should take milliseconds.
    """
    try:
        from best_engine_ai_helper import safety
    except ImportError:  # the dependency is absent — nothing to neutralise
        return
    for name in ("check_text", "check_image"):
        if hasattr(safety, name):
            monkeypatch.setattr(safety, name, lambda *a, **k: None)


@pytest.fixture
def repo_root() -> Path:
    """Return the repository root path."""
    return REPO_ROOT
