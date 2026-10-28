#!/usr/bin/env python3
"""
The catalogue of tools this package ships.

Lifted out of the command line on 2026-10-25, when the argparse front door was
removed and click became the only one. It lives here rather than in ``cli`` so
the catalogue owes nothing to whichever parser reads it — the previous
arrangement had the click module importing ``TOOLS`` from the argparse module,
which is why neither could be deleted without the other.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

#: Every tool, with the one line that says when to reach for it. The table is
#: the dispatcher *and* the help text, so a tool cannot be listed and
#: unreachable, or reachable and undocumented.
TOOLS: dict[str, tuple[str, str]] = {
    "lint": (
        "lint_markdown",
        "Audit the Markdown before anything renders it, and fix what has one "
        "safe repair. Standard library only.",
    ),
    "audit": (
        "audit_site",
        "Audit an emitted site — a directory, a page or a live URL — for the "
        "head meta, icon links and crawler indexes, and repair with --fix "
        "what can be derived rather than invented.",
    ),
    "html": (
        "md_to_html",
        "Markdown → HTML pages, with the Mermaid diagrams rendered.",
    ),
    "icons": (
        "favicons",
        "One logo → the favicon, app-icon and PWA set, plus the <head> "
        "snippet that references them.",
    ),
    "indexes": (
        "site_indexes",
        "robots.txt, sitemap.xml, llms.txt, llms-full.txt, an Atom feed and "
        "humans.txt — what crawlers and language models look for.",
    ),
    "meta": (
        "meta_from_ollama",
        "Open Graph, Twitter Card and Schema.org JSON-LD for a page, drafted by a local model.",
    ),
    "plain": (
        "plain_language",
        "Rewrite prose at a target reading grade, keeping the terms you name.",
    ),
    "changelog": (
        "changelog_feed",
        "A CHANGELOG becomes dated posts and a feed.",
    ),
    "narrate": (
        "narrate_post",
        "Narrate a post with a local voice from sprezzature-audio, and write "
        "the timed track beside the audio.",
    ),
    "readalong": (
        "readalong",
        "Bind a narration to a page so the sentence being spoken is highlighted as it is read.",
    ),
}
