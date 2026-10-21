# Contributing

## Setup

```bash
git clone https://github.com/warith-harchaoui/sprezzature-publish
cd sprezzature-publish
pip install -e ".[dev,all,api,mcp]"
```

That is the line CI runs. The development dependencies live in the `dev`
extra in `pyproject.toml` rather than in a `requirements-dev.txt`, so there
is one list and the workflow installs it by name.

## Tests

```bash
pytest
```

The `tests/eval/` suite is excluded from the default run: it calls a local
model, so it is slow and it needs one installed. Ask for it by name when
you want it.

## Lint

`ruff` is the Python linter and formatter this project uses: it reads the
source without running it and flags style issues (unused imports, wrong
quote style, and the like) in one fast pass.

```bash
ruff check .
```

## Adding a tool

1. Write `scripts/<tool>.py` with a `main()` and a parser built through
   `scripts/_argparse.py` (or `scripts/_click.py` for a click tool), so it
   inherits `--version` and the shared help shape.
2. Register it in `[project.scripts]` in `pyproject.toml` as
   `sprezzature-publish-<tool>`. Both front doors read that table, so this
   one line is what puts the tool behind `make-site <tool>` and
   `sprezzature-publish <tool>`.
3. If it needs anything outside the standard library, add an extra named
   after it rather than widening the base install. See `CODING.md`.
4. Add a test in `tests/`: at least one input that should produce output,
   one that should be refused.
5. Document it in the table in `README.md` and `LISEZMOI.md`, in both
   languages, and add a worked invocation to `EXAMPLES.md`. The parity test
   and the documented-commands test both fail if you do one and not the
   other.

## Code standards

See `CODING.md`. NumPy docstrings, full typing, ~25-30% comment density,
and standard library only in the lint and the indexes.

## Prose standards

English prose (README, docstrings, comments) follows WRITING.md:
https://gist.github.com/warith-harchaoui/f45304d066abc81dd7d4f059a1f4e45f

French prose (LISEZMOI) follows ECRITURE.md:
https://gist.github.com/warith-harchaoui/7cc42b038e86c5195ec09f0531111ba4

No punctuation dashes, no machine tells ("Moreover", "In conclusion",
reflexive "not only X but also Y"). Acronyms glossed on first use.

## Releases

Releases live in `CHANGELOG.md`, tagged `vX.Y.Z` in git, and published as
GitHub releases.

## Authorship

Sole author: [Warith HARCHAOUI](https://www.linkedin.com/in/warith-harchaoui/).
External contributions are welcome. Open an issue or pull request on GitHub.

## License

[BSD-3-Clause](LICENSE).
