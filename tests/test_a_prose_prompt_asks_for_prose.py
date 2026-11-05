"""
A prose prompt does not ask for alt text.

``meta``, ``plain`` and ``faq`` take their language line from
``_ollama.LANG_INSTRUCTIONS``, which was copied from the alt-text tool with its
wording: a meta description, a plain-language rewrite and an FAQ answer were
each asked to be "the alt text in English".

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re

import _ollama
import pytest

_ALT = re.compile(
    r"alt|alternati|代替|替代|البديل",
    re.IGNORECASE,
)


@pytest.mark.parametrize("lang", sorted(_ollama.LANG_INSTRUCTIONS))
def test_the_language_line_names_no_alt_text(lang: str) -> None:
    assert not _ALT.search(_ollama.LANG_INSTRUCTIONS[lang]), _ollama.LANG_INSTRUCTIONS[lang]
