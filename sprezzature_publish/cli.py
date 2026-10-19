"""
The argparse command line — ``make-site``.

Nine tools ship here, each with its own command, and that is the right shape
for a build script: `sprezzature-publish-lint` in a pre-commit hook,
`sprezzature-publish-icons` once when the logo changes. What nine separate
commands do not give you is a way to find out what this package does without
reading its README.

So this is the front door. ``make-site`` lists the tools, says what each one
is for, and dispatches to it — the same engine, reached by a name you can
guess. ``sprezzature_publish.cli_click`` is its twin, reading the same flags
with click.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import argparse
import importlib
import sys

from sprezzature_publish_scripts._argparse import make_parser

#: Every tool, with the one line that says when to reach for it. The table is
#: the dispatcher *and* the help text, so a tool cannot be listed and
#: unreachable, or reachable and undocumented.
TOOLS: dict[str, tuple[str, str]] = {
    "lint": (
        "lint_markdown",
        "Audit the Markdown before anything renders it, and fix what has one "
        "safe repair. Standard library only.",
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
        "Open Graph, Twitter Card and Schema.org JSON-LD for a page, drafted "
        "by a local model.",
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
        "Bind a narration to a page so the sentence being spoken is "
        "highlighted as it is read.",
    ),
}


def build_parser() -> argparse.ArgumentParser:
    """The parser, built separately so a test can read it without running it."""
    width = max(len(name) for name in TOOLS)
    catalogue = "\n".join(
        f"  {name:<{width}}  {summary}" for name, (_, summary) in TOOLS.items()
    )
    parser = make_parser(
        prog="make-site",
        description=(
            "Turn a folder of Markdown into a site somebody can find. One "
            "front door over the nine tools this package ships; each is also "
            "its own command, which is what a build script should call."
        ),
        epilog=(
            f"Tools:\n{catalogue}\n"
            "\n"
            "Examples:\n"
            "  make-site lint docs/\n"
            "  make-site html README.md --out-dir site/\n"
            "  make-site icons logo.png --out-dir site/icons/\n"
            "\n"
            "Every flag after the tool name belongs to that tool; run\n"
            "`make-site <tool> --help` to see them.\n"
        ),
    )
    parser.add_argument(
        "tool",
        choices=sorted(TOOLS),
        help="Which tool to run. See the list below.",
    )
    # Everything after the tool name belongs to the tool, including flags
    # this parser also defines. Without REMAINDER, `make-site lint --help`
    # would print *this* help rather than the lint's, which is the opposite
    # of what the reader asked for.
    parser.add_argument(
        "rest",
        nargs=argparse.REMAINDER,
        help="Arguments passed through to the tool.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """
    Dispatch to one of the nine tools.

    Parameters
    ----------
    argv : list of str or None, optional
        Argument vector without ``argv[0]``. Reads ``sys.argv`` when ``None``.

    Returns
    -------
    int
        Whatever the dispatched tool returns.
    """
    args = build_parser().parse_args(argv)
    module_name, _ = TOOLS[args.tool]
    try:
        module = importlib.import_module(
            f"sprezzature_publish_scripts.{module_name}"
        )
    except ImportError as exc:  # pragma: no cover - dependency guard
        sys.stderr.write(
            f"{args.tool}: its dependencies are an optional extra so the lint "
            f"stays dependency-free. Install them with: "
            f"pip install 'sprezzature-publish[all]'\n  ({exc})\n"
        )
        return 2

    # The tools read sys.argv themselves — they were commands before they were
    # sub-commands, and they still are. Handing them a rewritten argv is what
    # lets both be true.
    saved = sys.argv
    try:
        sys.argv = [f"make-site {args.tool}", *args.rest]
        return int(module.main() or 0)
    finally:
        sys.argv = saved


if __name__ == "__main__":
    sys.exit(main())
