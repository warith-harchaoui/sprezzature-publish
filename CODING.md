# CODING.md

Coding standards for sprezzature-publish.

Key rules: NumPy-style docstrings on every function, full typing
(`from __future__ import annotations` at the top of every file), roughly
25-30% comment density explaining *why* a non-obvious line does what it
does, ruff-clean (`ruff check .`), no bare `except Exception` without a
comment saying why the broad catch is intentional.

## The dependency rule, which is the one that is easy to break

Two tools are standard library only, and that is a published promise rather
than an accident:

* `scripts/lint_markdown.py`. It runs in milliseconds in a minimal
  container, which is the whole reason it is worth putting in a pre-commit
  hook. One import of `markdown` or `Pillow` would end that.
* `scripts/site_indexes.py`. It writes `robots.txt`, `sitemap.xml`,
  `llms.txt`, a feed and `humans.txt`, all of them text.

Everything heavier belongs behind an extra named after the tool that needs
it (`[html]`, `[icons]`, `[prose]`), so that an install says what it is for.
A new import in either of those two files is a review question, not a
detail.

## The two names share one table

`make-site` and `sprezzature-publish` are two spellings of one click front
door — the argparse twin was dropped on 2026-10-25 — and both resolve
against one table of tools. A tool added to one and
not the other is a half-shipped tool, and
`tests/test_the_surfaces_agree.py` fails on it. Add the entry point in
`pyproject.toml` and the table picks it up.

## Documented commands are tested commands

`tests/test_the_documented_commands_run.py` parses every fenced `bash`
block in `README.md`, `LISEZMOI.md` and `EXAMPLES.md`, and asks each
parser whether it accepts the flags on the line. A command line in the
prose is an instruction to a reader, so it is checked like one. Four lines
were wrong before that test existed, and reading them had not caught it.
