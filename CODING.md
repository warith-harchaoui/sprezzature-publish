# CODING.md

Coding standards for sprezzature-publish.

Key rules: NumPy-style docstrings on every function, full typing
(`from __future__ import annotations` at the top of every file), roughly
25-30% comment density explaining *why* a non-obvious line does what it
does, ruff-clean (`ruff check .`), no bare `except Exception` without a
comment saying why the broad catch is intentional.

## The dependency rule, which is the one that is easy to break

Three tools need only click and the standard library, and that is a
published promise rather than an accident:

* `scripts/lint_markdown.py`. It runs in milliseconds in a minimal
  container, which is the whole reason it is worth putting in a pre-commit
  hook. One import of `markdown` or `Pillow` would end that.
* `scripts/site_indexes.py`. It writes `robots.txt`, `sitemap.xml`,
  `llms.txt`, a feed and `humans.txt`, all of them text.
* `scripts/audit_site.py`. It reads a built site or a live URL with
  `html.parser` and `urllib`, and reuses `site_indexes` for its repairs, so
  it audits a site somebody else built on a machine that has nothing else.

Everything heavier is a base dependency since the extras were folded in on
2026-11-01, but none of those three files imports it at module level (the
lint reaches for `mmdc` and a model client only behind `--render-mermaid`
and `--ai`). A new import in any of them is a review question, not a detail,
and `tests/test_the_light_tools_stay_light.py` fails on one.

## The two names share one table

`make-site` and `sprezzature-publish` are two spellings of one click front
door (the argparse twin was dropped on 2026-10-25, and every per-tool
command and the MCP server moved to click on 2026-11-04) and both resolve
against one table of tools. A tool added to one and
not the other is a half-shipped tool, and
`tests/test_the_surfaces_agree.py` fails on it. The table is `TOOLS` in
`sprezzature_publish/_tools.py`; the console script in `pyproject.toml` is a
separate line, and a new tool needs both.

## Documented commands are tested commands

`tests/test_the_documented_commands_run.py` parses every fenced `bash` or
`sh` block in `README.md`, `LISEZMOI.md`, `EXAMPLES.md` and
`references/*.md`, and hands each command line, continuations joined, to
the tool's own click parser without running it: an unknown flag, a missing
required option, an extra argument, a command no console script installs,
or a mode the tool refuses (`readalong --check` with no `--narration`) fails
the suite. A command line in the prose is an instruction to a reader, so it
is checked like one. Four lines were wrong before the first version of that
test existed, and four more passed it while still failing to run, because
it checked only that each flag existed.
