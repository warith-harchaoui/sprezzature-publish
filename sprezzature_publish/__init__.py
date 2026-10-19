"""
sprezzature-publish — a folder of Markdown becomes a site somebody can find.

Point it at a `README.md` and a `docs/` folder and it emits pages, the meta
tags that make them shareable, a favicon set from one logo, the indexes
crawlers and language models look for (`robots.txt`, `sitemap.xml`,
`llms.txt`, an Atom feed), and — when asked — a narrated audio track with a
read-along that highlights the sentence being spoken.

Two halves, as every brick in this suite has:

* **make** — `md_to_html`, `favicons`, `site_indexes`, `changelog_feed`,
  `meta_from_ollama`, `plain_language`, `narrate_post`, `readalong`.
* **audit** — `lint_markdown`, which gates the Markdown before any of it
  runs, and fixes what has one safe repair.

Why a library and not only commands
-----------------------------------
A site is built by a script somebody wrote, in a loop, on a schedule. That
caller should import rather than shell out and parse stdout — which is what
this module is for. The command lines stay the way a person works.

What it does not own
--------------------
The **voices**. Narration synthesis lives in `sprezzature-audio`
(`sprezzature-audio-narrate-openvoice` and `-chatterbox`), because captions
turn sound into timed text and narration turns text into timed sound: one
package owns that modality in both directions. This one owns the document
and the page, and invokes those as subprocesses so their heavy imports never
enter its graph.

Usage example
-------------
>>> from sprezzature_publish import lint_file, convert_one
>>> findings = lint_file(Path("README.md"))          # doctest: +SKIP
>>> convert_one(Path("README.md"), Path("out"))      # doctest: +SKIP

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

__version__ = "1.2.0"
__author__ = "Warith HARCHAOUI"
__email__ = "warithmetics@deraison.ai"
__license__ = "BSD-3-Clause"

from typing import Any  # noqa: E402

#: Names resolved on first use rather than at import, mapped to the module
#: that owns them.
#:
#: This is not laziness for its own sake. The tools in this package have
#: wildly different dependencies — Pillow for the favicon set, a Markdown
#: engine for the pages, an LLM client for the meta tags and the
#: plain-language rewrite — and each is an extra. Importing them all eagerly
#: would make ``import sprezzature_publish`` fail for anyone who installed
#: the package to lint their Markdown, which needs nothing but the standard
#: library.
_EXPORTS: dict[str, str] = {
    # audit
    "lint_file": "lint_markdown",
    "fix_trailing_whitespace": "lint_markdown",
    # make — pages
    "convert_one": "md_to_html",
    "gather_inputs": "md_to_html",
    # make — the things that make a page findable
    "discover_pages": "site_indexes",
    "render_robots": "site_indexes",
    "render_sitemap": "site_indexes",
    "render_llms_txt": "site_indexes",
    "render_atom": "site_indexes",
    # make — icons. Exported as the steps rather than one `build_icons`:
    # a caller generating an icon set usually wants to control the padding
    # and the background themselves, and the command line is the place that
    # already decided those.
    "open_source": "favicons",
    "resize_square": "favicons",
    "make_maskable": "favicons",
    "write_manifest": "favicons",
    "write_head_snippet": "favicons",
    # make — prose
    "rewrite": "plain_language",
    # make — a changelog becomes posts
    "parse_changelog": "changelog_feed",
    "build_posts": "changelog_feed",
    # make — voice and read-along
    "enrich_with_llm": "narrate_post",
    "run_engine": "narrate_post",
    "build": "readalong",
}


def __getattr__(name: str) -> Any:
    """Resolve an export on first use, per PEP 562.

    A caller that only lints never imports Pillow; one that only builds
    icons never imports a Markdown engine. When the extra behind a name is
    missing, the error says which one rather than naming a module the reader
    has never heard of.
    """
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    try:
        module = importlib.import_module(f"sprezzature_publish_scripts.{module_name}")
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ImportError(
            f"`{name}` lives in {module_name}, whose dependencies are an "
            f"optional extra so the lint stays dependency-free. Install them "
            f"with: pip install 'sprezzature-publish[all]'"
        ) from exc
    return getattr(module, name)


__all__ = ["__version__", *sorted(_EXPORTS)]
