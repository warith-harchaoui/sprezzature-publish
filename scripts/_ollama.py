"""
_ollama.py — shared Ollama client helpers used by alt_from_ollama,
captions_from_whisper (vocab biasing), and other scripts that talk to a
local Ollama daemon.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import locale
import os

OLLAMA_URL: str = os.environ.get("OLLAMA_URL", "http://localhost:11434")

#: The one authorized model: qwen3-vl:8b (via Ollama). No other tag, no MLX.
DEFAULT_BASE: str = "qwen3-vl:8b"


BANNED_PREFIXES: dict[str, tuple[str, ...]] = {
    "en": ("image of", "picture of", "photo of", "photograph of", "illustration of"),
    "fr": ("image de", "photo de", "photographie de", "illustration de"),
    "es": ("imagen de", "foto de", "fotografía de"),
    "de": ("bild von", "foto von", "darstellung von"),
    "it": ("immagine di", "foto di"),
    "pt": ("imagem de", "foto de"),
    "nl": ("afbeelding van", "foto van"),
    "ar": ("صورة لـ", "صورة من"),
    "ja": ("の画像", "の写真"),
    "zh": ("的图片", "的照片"),
}


#: The language line of a prose prompt (``meta``, ``plain``, ``faq``). It
#: was copied from the alt-text tool with its wording, so every rewrite, meta
#: description and FAQ answer was asked to be "the alt text in English".
LANG_INSTRUCTIONS: dict[str, str] = {
    "en": "Write in English.",
    "fr": "Rédige en français.",
    "es": "Escribe en español.",
    "de": "Schreibe auf Deutsch.",
    "it": "Scrivi in italiano.",
    "pt": "Escreva em português.",
    "nl": "Schrijf in het Nederlands.",
    "ar": "اكتب باللغة العربية.",
    "ja": "日本語で書いてください。",
    "zh": "用中文写。",
}


def ollama_engine(model: str) -> dict:
    """The ``engine=`` to hand ``best_engine_ai_helper.llm.chat`` for this server.

    Every tool here reads ``OLLAMA_URL`` and says "Cannot reach Ollama at
    ``OLLAMA_URL``" when the call fails, but ``chat()`` left to itself resolves
    its own server. With ``OLLAMA_URL`` pointed anywhere but the default, the
    message named one server and the call went to another — the same split
    sprezzature-audio and sprezzature-accessibility closed the same way.
    """
    return {"backend": "ollama", "base_url": OLLAMA_URL, "llm": {"model": model}}


def pick_default_model() -> str:
    """Return the one authorized model tag (``qwen3-vl:8b``).

    ``OLLAMA_MODEL`` is honoured only as a bare test seam so the suite can point
    the resolver at a stub; it is never a user-facing model choice.
    """
    return os.environ.get("OLLAMA_MODEL") or DEFAULT_BASE


def detect_lang() -> str:
    """Detect the desired output language as a two-letter code."""
    raw: str | None = (
        os.environ.get("ALT_LANG") or os.environ.get("LC_ALL") or os.environ.get("LANG")
    )
    if not raw:
        try:
            raw, _ = locale.getlocale()
        except (TypeError, ValueError):
            raw = "en"
    raw = (raw or "en").lower()
    return raw.split("_")[0].split(".")[0][:2]
