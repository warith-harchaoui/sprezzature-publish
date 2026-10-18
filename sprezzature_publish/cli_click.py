"""
The click command line — ``sprezzature-publish``.

The twin of ``sprezzature_publish.cli``: same nine tools, same dispatch, the
other parser. Both read the single ``TOOLS`` table, so a tool cannot appear
in one front door and be missing from the other — which is the failure a
second command line invites, and the reason this one is eleven lines of
plumbing rather than a second catalogue.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import importlib
import sys

import click

from sprezzature_publish.cli import TOOLS


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    help=(
        "Turn a folder of Markdown into a site somebody can find. Each tool "
        "below is also its own command (sprezzature-publish-lint and so on), "
        "which is what a build script should call."
    ),
)
@click.version_option(package_name="sprezzature-publish")
def main() -> None:  # pragma: no cover - click dispatches
    """Front door over the nine tools this package ships."""


def _attach(name: str, module_name: str, summary: str) -> None:
    """Register one tool as a click sub-command.

    Built in a loop rather than written out nine times: the catalogue lives
    in one table, and a tool added there appears in both command lines
    without anybody remembering to add it twice.
    """

    @main.command(
        name,
        help=summary,
        context_settings={
            "ignore_unknown_options": True,
            "allow_extra_args": True,
        },
    )
    @click.argument("rest", nargs=-1, type=click.UNPROCESSED)
    def _run(rest: tuple[str, ...], _module: str = module_name, _name: str = name) -> None:
        try:
            module = importlib.import_module(f"sprezzature_publish_scripts.{_module}")
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise SystemExit(
                f"{_name}: its dependencies are an optional extra so the lint "
                f"stays dependency-free. Install them with: "
                f"pip install 'sprezzature-publish[all]'\n  ({exc})"
            ) from exc

        # The tools read sys.argv themselves — they were commands before they
        # were sub-commands, and they still are.
        saved = sys.argv
        try:
            sys.argv = [f"sprezzature-publish {_name}", *rest]
            raise SystemExit(int(module.main() or 0))
        finally:
            sys.argv = saved


for _tool, (_module_name, _summary) in TOOLS.items():
    _attach(_tool, _module_name, _summary)


if __name__ == "__main__":
    main()
