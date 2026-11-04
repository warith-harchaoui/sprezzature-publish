#!/usr/bin/env python3
"""
_content
========

Read a site the way an answer engine would, whatever it is written in.

The CTA detector, the FAQ builder and the joint findability report all need
the same three things from a site: the **text** a reader sees (to ground an
answer), the **actionable elements** (to find the calls to action), and any
**FAQ** already there (to improve it rather than write a second one). This
module reads them once, from every format a real site keeps its content in.

Why every format, and not only rendered HTML
--------------------------------------------
A site is rarely a folder of HTML. On the site this was calibrated on, the
booking button lives in ``layouts/nav.php``, the portfolio in
``data/*.json`` rendered by PHP, and the posts in Markdown. Reading only the
``.html`` files would have missed the one CTA that matters. So:

* **HTML and PHP** — the ``<?php … ?>`` blocks are dropped and the rest is
  parsed as HTML. A template is content: what it prints is what the reader
  sees, minus the parts a server fills in.
* **Markdown** — rendered through the ``markdown`` package (a base
  dependency), then read as HTML, so inline HTML, ``<details>`` and links in
  either spelling are all seen by one parser rather than two.
* **JSON and YAML** — every string is walked. A key that names a URL
  (``url``, ``link``, ``href``) is a destination, and its sibling ``title`` /
  ``label`` / ``text`` is the words on it. A ``question`` / ``answer`` pair
  is a FAQ entry.

Skipped, because they are not content: lockfiles (one ``package-lock.json``
held 480 URLs on the calibration site, none of them a page), dependency and
build folders, minified bundles, and the configuration JSON every project
carries (``package.json``, ``tsconfig.json``, a web manifest).

Nothing here decides anything. It records **evidence** — tag, text, classes,
inline style, landmark, position — and leaves the judgement to the tools
that read it.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# ── What is read, and what is not ──────────────────────────────────────────

#: Suffixes read as content, mapped to the reader that handles them.
FORMATS: dict[str, str] = {
    ".html": "html",
    ".htm": "html",
    ".php": "php",
    ".md": "md",
    ".markdown": "md",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
}

#: Directories that hold dependencies, caches or a build of something else.
SKIP_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        "vendor",
        "bower_components",
        ".git",
        ".hg",
        ".svn",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".private",
        ".cache",
        ".next",
        ".nuxt",
        ".svelte-kit",
        ".parcel-cache",
        "build",
        "coverage",
        "target",
    }
)

#: Files that look like data and are configuration or a lock.
SKIP_FILES: frozenset[str] = frozenset(
    {
        "package-lock.json",
        "npm-shrinkwrap.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "composer.lock",
        "composer.json",
        "poetry.lock",
        "pipfile.lock",
        "package.json",
        "tsconfig.json",
        "jsconfig.json",
        "manifest.json",
        "site.webmanifest",
        ".eslintrc.json",
        ".prettierrc.json",
        "renovate.json",
        "vercel.json",
        "netlify.json",
        "firebase.json",
        "docker-compose.yml",
        "docker-compose.yaml",
        "mkdocs.yml",
        "_config.yml",
        "pubspec.yaml",
        ".pre-commit-config.yaml",
    }
)

#: Above this size a file is generated data, not something a person wrote.
MAX_BYTES: int = 3 * 1024 * 1024

# ── The records ────────────────────────────────────────────────────────────


@dataclass
class Passage:
    """One block of visible text, under the heading it sits beneath."""

    heading: str
    text: str
    line: int = 0


@dataclass
class Actionable:
    """One thing a reader can act on, with the evidence a detector reads.

    ``kind`` is ``link``, ``button``, ``form`` (a form that collects a lead),
    ``install`` (an install command in a code block — a CTA with no link on
    a tool site) or ``data`` (a URL in a JSON or YAML record that a template
    renders). Nothing here says whether it is a CTA.
    """

    kind: str
    text: str
    href: str = ""
    line: int = 0
    tag: str = ""
    classes: str = ""
    style: str = ""
    attrs: dict[str, str] = field(default_factory=dict)
    landmark: str = ""  # header / nav / main / footer / aside / ""
    hero: bool = False  # inside <main>, before its first <h2>
    order: int = 0  # position among the page's actionables


@dataclass
class FaqItem:
    """One question with its answer, and where it was found."""

    question: str
    answer: str
    origin: str  # heading / details / dl / data / jsonld
    line: int = 0


@dataclass
class PageContent:
    """Everything the CTA, FAQ and findability tools read from one file."""

    path: str  # relative to the site root, POSIX
    fmt: str  # html / php / md / json / yaml
    title: str = ""
    lang: str = ""
    passages: list[Passage] = field(default_factory=list)
    actionables: list[Actionable] = field(default_factory=list)
    faq: list[FaqItem] = field(default_factory=list)
    jsonld_faq: list[FaqItem] = field(default_factory=list)
    jsonld_types: list[str] = field(default_factory=list)
    jsonld_names: dict[str, str] = field(default_factory=dict)  # @type → name
    robots: str = ""  # <meta name=robots|googlebot>, lower-cased, joined
    canonical: str = ""
    faq_heading_line: int = 0  # 0 when the page has no FAQ heading
    main_end_line: int = 0  # line of </main>, for proposing a placement
    # Files a PHP template pulls in (``include 'layouts/nav.php'``). The
    # booking button of a PHP site sits in the nav partial, so a page
    # carries it only through this list.
    includes: list[str] = field(default_factory=list)
    source: str = ""  # the text the parser read, kept for --fix

    @property
    def is_page(self) -> bool:
        """True for a file a reader lands on, false for a data file."""
        return self.fmt in {"html", "php", "md"}

    @property
    def text(self) -> str:
        """The page's visible text, one passage per line."""
        return "\n".join(p.text for p in self.passages)


# ── Small helpers ──────────────────────────────────────────────────────────

_WS = re.compile(r"\s+")


def clean(text: str) -> str:
    """Collapse whitespace and decode any entity a parser left behind."""
    return _WS.sub(" ", html.unescape(text or "")).strip()


def decode_href(href: str) -> str:
    """Decode entities and percent-encoding, so ``mailto:`` reads as one.

    The calibration site carried 77 ``mailto:`` links whose address was
    written ``&#37;&#52;&#48;`` — entity-encoded percent-encoding, an
    anti-spam habit. Classified raw, none of them read as a contact link.
    """
    value = html.unescape(href or "").strip()
    # Twice: an entity can decode to a percent sequence, never the reverse.
    for _ in range(2):
        decoded = urllib.parse.unquote(value)
        if decoded == value:
            break
        value = decoded
    return value


#: A FAQ heading, in the two languages the suite writes.
FAQ_HEADING = re.compile(
    r"^\s*(faqs?|f\.a\.q\.?|frequently asked questions?|common questions|"
    r"questions? (fréquentes?|courantes?)|foire aux questions|"
    r"vos questions|questions et réponses|q\s*&\s*a)\b",
    re.I,
)

#: Install commands, for the CTA a tool site has instead of a button.
INSTALL_COMMAND = re.compile(
    r"^\s*(?:\$\s*)?((?:pip|pip3|pipx|uv pip|uv tool|uv|npm|pnpm|yarn|brew|cargo|"
    r"gem|go|apt|apt-get|conda|mamba|composer)\s+(?:install|add|get)\s+\S.*)$",
    re.M,
)

_PHP = re.compile(r"<\?(?:php|=)?.*?(?:\?>|\Z)", re.S | re.I)


_INCLUDE = re.compile(
    r"\b(?:include|require)(?:_once)?\b[^;'\"]*['\"]([^'\"]+\.(?:php|html?|inc))['\"]", re.I
)


def php_includes(text: str) -> list[str]:
    """The files a PHP template includes, as written (relative or bare)."""
    out: list[str] = []
    for block in _PHP.findall(text):
        out.extend(m.group(1).lstrip("/") for m in _INCLUDE.finditer(block))
    return out


def strip_php(text: str) -> str:
    """Drop the ``<?php … ?>`` blocks and keep everything the template prints.

    Each block is replaced by as many newlines as it held, so the line
    numbers a finding reports still point at the template's own lines.
    """
    return _PHP.sub(lambda m: "\n" * m.group(0).count("\n"), text)


# ── The HTML reader ────────────────────────────────────────────────────────

_VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "source",
        "track",
        "wbr",
    }
)
_BLOCKS = frozenset(
    {"p", "li", "dd", "dt", "td", "th", "blockquote", "pre", "figcaption", "summary", "div"}
)
_LANDMARK_TAGS = {
    "header": "header",
    "nav": "nav",
    "main": "main",
    "footer": "footer",
    "aside": "aside",
}
_LANDMARK_ROLES = {
    "banner": "header",
    "navigation": "nav",
    "main": "main",
    "contentinfo": "footer",
    "complementary": "aside",
}
#: ARIA roles that make any element interactive, per the WAI-ARIA widget list.
_INTERACTIVE_ROLES = frozenset({"button", "link", "menuitem", "tab", "option", "switch"})
_SILENT = frozenset({"script", "style", "template", "noscript", "svg"})


class _Reader(HTMLParser):
    """One pass over an HTML document, collecting the three records.

    A parser rather than regexes for the reason ``audit_site`` gives:
    attribute order and quoting are the author's choice. Nesting is tracked
    with a tolerant stack, because real templates leave elements open and a
    strict tree builder would refuse them.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.landmarks: list[tuple[str, str]] = []  # (tag, landmark)
        self.page = PageContent(path="", fmt="html")
        self.heading = ""
        self._heading_level = 0
        self._heading_buf: list[str] | None = None
        self._title_buf: list[str] | None = None
        self._block_buf: list[str] = []
        self._block_line = 0
        self._silent = 0
        self._seen_h2_in_main = False
        # The actionable being read, and the stack depth that opened it.
        self._act: Actionable | None = None
        self._act_depth = 0
        self._act_alt: list[str] = []
        # Forms: a lead form is a CTA, a search box is not.
        self._form: dict[str, Any] | None = None
        # <pre>/<code>, for install commands.
        self._code_buf: list[str] | None = None
        self._code_line = 0
        # FAQ shapes.
        self._faq_level = 0  # heading level of the open FAQ section, 0 = none
        self._faq_q: tuple[str, int] | None = None
        self._faq_a: list[str] = []
        self._details: list[dict[str, Any]] = []
        self._summary_buf: list[str] | None = None
        self._dt: tuple[str, int] | None = None
        self._dt_buf: list[str] | None = None
        self._dd_buf: list[str] | None = None
        self._jsonld_buf: list[str] | None = None

    # ── landmarks and position ────────────────────────────────────────

    def _landmark(self) -> str:
        return self.landmarks[-1][1] if self.landmarks else ""

    def _in_main(self) -> bool:
        return any(lm == "main" for _, lm in self.landmarks)

    # ── text plumbing ─────────────────────────────────────────────────

    def _flush_block(self) -> None:
        text = clean("".join(self._block_buf))
        self._block_buf = []
        if not text or self._landmark() in {"nav", "footer"}:
            return
        self.page.passages.append(Passage(self.heading, text, self._block_line))
        if self._faq_q is not None:
            self._faq_a.append(text)

    def _close_faq_question(self) -> None:
        if self._faq_q is not None:
            question, line = self._faq_q
            answer = " ".join(self._faq_a).strip()
            if answer:
                self.page.faq.append(FaqItem(question, answer, "heading", line))
        self._faq_q = None
        self._faq_a = []

    # ── HTMLParser hooks ──────────────────────────────────────────────

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        line = self.getpos()[0]
        if tag in _SILENT:
            if tag == "script" and a.get("type", "").lower() == "application/ld+json":
                self._jsonld_buf = []
            self._silent += 1
            if tag not in _VOID:
                self.stack.append(tag)
            return
        if tag == "html":
            self.page.lang = a.get("lang", "")
        elif tag == "title":
            self._title_buf = []
        elif tag == "meta":
            if a.get("name", "").lower() in {"robots", "googlebot"}:
                self.page.robots = (self.page.robots + "," + a.get("content", "").lower()).strip(
                    ","
                )
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.page.canonical = a.get("href", "")

        landmark = _LANDMARK_TAGS.get(tag) or _LANDMARK_ROLES.get(a.get("role", "").lower())
        if tag in _BLOCKS or re.fullmatch(r"h[1-6]", tag):
            self._flush_block()
            self._block_line = line

        if re.fullmatch(r"h[1-6]", tag):
            level = int(tag[1])
            self._heading_buf = []
            self._heading_level = level
            if self._in_main() and level == 2:
                self._seen_h2_in_main = True
        elif tag == "details":
            self._details.append({"q": "", "a": [], "line": line})
        elif tag == "summary" and self._details:
            self._summary_buf = []
        elif tag == "dt":
            self._dt_buf = []
            self._dt = None
        elif tag == "dd" and self._dt is not None:
            self._dd_buf = []
        elif tag in {"pre", "code"} and self._code_buf is None:
            self._code_buf = []
            self._code_line = line
        elif tag == "form":
            self._form = {"line": line, "attrs": a, "lead": False, "search": False}
            if a.get("role", "").lower() == "search":
                self._form["search"] = True
        elif tag == "input" and self._form is not None:
            kind = a.get("type", "text").lower()
            name = (a.get("name", "") + " " + a.get("id", "")).lower()
            if kind == "email" or "email" in name or "mail" == name.strip():
                self._form["lead"] = True
            if kind == "search" or name.strip() in {"q", "s", "query", "search"}:
                self._form["search"] = True
        elif tag == "img" and self._act is not None:
            self._act_alt.append(a.get("alt", ""))

        # An actionable: native link or button, an interactive role,
        # tabindex >= 0, or a click handler — the static subset of what
        # browser-use and Chromium's accessibility tree call interactive.
        if self._act is None and not self._silent:
            role = a.get("role", "").lower()
            tabindex = a.get("tabindex", "")
            interactive = (
                (tag == "a" and "href" in a)
                or tag == "button"
                or (tag == "input" and a.get("type", "").lower() in {"submit", "button"})
                or role in _INTERACTIVE_ROLES
                or (tabindex.lstrip("-").isdigit() and int(tabindex) >= 0 and tag != "a")
                or "onclick" in a
            )
            if interactive:
                kind = "link" if tag == "a" else "button"
                self._act = Actionable(
                    kind=kind,
                    text="",
                    href=a.get("href", "") or a.get("data-href", "") or a.get("formaction", ""),
                    line=line,
                    tag=tag,
                    classes=a.get("class", ""),
                    style=a.get("style", ""),
                    attrs=a,
                    landmark=self._landmark() or ("form" if self._form else ""),
                    hero=self._in_main() and not self._seen_h2_in_main,
                )
                self._act_alt = []
                if tag == "input":
                    self._act.text = a.get("value", "")
                    self._finish_actionable()
                else:
                    self._act_depth = len(self.stack) + 1

        if landmark:
            self.landmarks.append((tag, landmark))
        if tag not in _VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag not in self.stack:
            return
        # Pop to the matching opener: unclosed children close with it.
        while self.stack:
            top = self.stack.pop()
            self._close(top)
            if top == tag:
                break

    def _close(self, tag: str) -> None:
        line = self.getpos()[0]
        if tag in _SILENT:
            self._silent = max(0, self._silent - 1)
            if tag == "script" and self._jsonld_buf is not None:
                self._read_jsonld("".join(self._jsonld_buf))
                self._jsonld_buf = None
            return
        if self._act is not None and len(self.stack) + 1 == self._act_depth:
            self._finish_actionable()
        if self.landmarks and self.landmarks[-1][0] == tag:
            if self.landmarks[-1][1] == "main" and not self.page.main_end_line:
                self.page.main_end_line = line
            self.landmarks.pop()
        if tag == "title" and self._title_buf is not None:
            self.page.title = clean("".join(self._title_buf))
            self._title_buf = None
        elif re.fullmatch(r"h[1-6]", tag) and self._heading_buf is not None:
            text = clean("".join(self._heading_buf))
            self._heading_buf = None
            level = self._heading_level
            if self._faq_level and level <= self._faq_level:
                self._close_faq_question()
                self._faq_level = 0
            if FAQ_HEADING.match(text):
                self._close_faq_question()
                self._faq_level = level
                if not self.page.faq_heading_line:
                    self.page.faq_heading_line = self._block_line
            elif self._faq_level and level > self._faq_level:
                self._close_faq_question()
                self._faq_q = (text, self._block_line)
            if not self.page.title and level == 1:
                self.page.title = text
            self.heading = text
        elif tag in _BLOCKS:
            self._flush_block()
        if tag == "summary" and self._summary_buf is not None and self._details:
            self._details[-1]["q"] = clean("".join(self._summary_buf))
            self._summary_buf = None
        elif tag == "details" and self._details:
            d = self._details.pop()
            answer = clean(" ".join(d["a"]))
            if d["q"] and answer and (d["q"].endswith("?") or self._faq_level):
                self.page.faq.append(FaqItem(d["q"], answer, "details", d["line"]))
        elif tag == "dt" and self._dt_buf is not None:
            self._dt = (clean("".join(self._dt_buf)), line)
            self._dt_buf = None
        elif tag == "dd" and self._dd_buf is not None and self._dt is not None:
            question, qline = self._dt
            answer = clean("".join(self._dd_buf))
            if question.endswith("?") and answer:
                self.page.faq.append(FaqItem(question, answer, "dl", qline))
            self._dd_buf = None
        elif tag in {"pre", "code"} and self._code_buf is not None:
            code = "".join(self._code_buf)
            self._code_buf = None
            for m in INSTALL_COMMAND.finditer(code):
                self.page.actionables.append(
                    Actionable(
                        kind="install",
                        text=m.group(1).strip(),
                        line=self._code_line,
                        tag=tag,
                        landmark=self._landmark(),
                        hero=self._in_main() and not self._seen_h2_in_main,
                    )
                )
        elif tag == "form" and self._form is not None:
            form = self._form
            self._form = None
            if form["lead"] and not form["search"]:
                self.page.actionables.append(
                    Actionable(
                        kind="form",
                        text=form["attrs"].get("aria-label", "") or "form",
                        href=form["attrs"].get("action", ""),
                        line=form["line"],
                        tag="form",
                        classes=form["attrs"].get("class", ""),
                        attrs=form["attrs"],
                        landmark=self._landmark(),
                        hero=self._in_main() and not self._seen_h2_in_main,
                    )
                )
            else:
                # A search box's submit button is not a call to action.
                self.page.actionables = [
                    x
                    for x in self.page.actionables
                    if not (x.landmark == "form" and x.line >= form["line"])
                ]

    def _finish_actionable(self) -> None:
        act = self._act
        self._act = None
        if act is None:
            return
        act.text = _undouble(clean(act.text))
        if not re.search(r"\w", act.text):
            # Icon-only buttons ("⬇") carry their words in an attribute.
            act.text = (
                clean(
                    act.attrs.get("aria-label")
                    or act.attrs.get("title")
                    or " ".join(x for x in self._act_alt if x)
                )
                or act.text
            )
        act.order = len(self.page.actionables)
        self.page.actionables.append(act)

    def handle_data(self, data: str) -> None:
        if self._jsonld_buf is not None:
            self._jsonld_buf.append(data)
        if self._silent:
            return
        if self._title_buf is not None:
            self._title_buf.append(data)
            return
        if self._act is not None:
            self._act.text += data
        if self._heading_buf is not None:
            self._heading_buf.append(data)
        else:
            self._block_buf.append(data)
        if self._summary_buf is not None:
            self._summary_buf.append(data)
        elif self._details:
            self._details[-1]["a"].append(data)
        if self._dt_buf is not None:
            self._dt_buf.append(data)
        if self._dd_buf is not None:
            self._dd_buf.append(data)
        if self._code_buf is not None:
            self._code_buf.append(data)

    def close(self) -> None:
        super().close()
        self._flush_block()
        self._close_faq_question()

    # ── JSON-LD ───────────────────────────────────────────────────────

    def _read_jsonld(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except ValueError:
            return
        for node in _jsonld_nodes(data):
            types = node.get("@type", [])
            types = [types] if isinstance(types, str) else list(types or [])
            self.page.jsonld_types.extend(t for t in types if isinstance(t, str))
            for t in types:
                if isinstance(t, str) and isinstance(node.get("name"), str):
                    self.page.jsonld_names.setdefault(t, node["name"])
            if "FAQPage" in types:
                for q in _as_list(node.get("mainEntity")):
                    if not isinstance(q, dict):
                        continue
                    answer = q.get("acceptedAnswer") or {}
                    if isinstance(answer, list):
                        answer = answer[0] if answer else {}
                    text = answer.get("text", "") if isinstance(answer, dict) else ""
                    self.page.jsonld_faq.append(
                        FaqItem(clean(str(q.get("name", ""))), _strip_tags(text), "jsonld")
                    )


def _undouble(text: str) -> str:
    """``ContactContact`` → ``Contact``.

    Animated exports (Framer, Webflow) print a label twice, one copy per
    hover state, and the parser reads both as one string.
    """
    half = len(text) // 2
    if len(text) % 2 == 0 and half and text[:half] == text[half:]:
        return text[:half]
    return text


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _jsonld_nodes(data: Any) -> list[dict[str, Any]]:
    """Every node of a JSON-LD document, through lists and ``@graph``."""
    out: list[dict[str, Any]] = []
    for item in _as_list(data):
        if isinstance(item, dict):
            out.append(item)
            out.extend(_jsonld_nodes(item.get("@graph")))
    return out


def _strip_tags(text: str) -> str:
    """Answer text in JSON-LD may carry markup; compare the words only.

    A tag closed before a full stop or a comma leaves no space before it;
    the French space before ``?`` ``!`` ``:`` ``;`` is the author's, and kept.
    """
    return re.sub(r"\s+([.,])", r"\1", clean(re.sub(r"<[^>]+>", " ", text or "")))


def read_html(text: str, path: str = "", fmt: str = "html") -> PageContent:
    """Read one HTML (or PHP, once stripped) document.

    Parameters
    ----------
    text : str
        The document.
    path : str
        Where it lives, relative to the site root; carried into every record.
    fmt : str
        ``html`` or ``php``. A PHP file has its code blocks removed first.

    Returns
    -------
    PageContent
        Text passages, actionable elements, FAQ items and JSON-LD facts.
    """
    body = strip_php(text) if fmt == "php" else text
    reader = _Reader()
    try:
        reader.feed(body)
        reader.close()
    except AssertionError:  # pragma: no cover - HTMLParser on broken markup
        pass
    page = reader.page
    page.path, page.fmt, page.source = path, fmt, text
    if fmt == "php":
        page.includes = php_includes(text)
    return page


# ── Markdown ───────────────────────────────────────────────────────────────

_FRONTMATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)


def read_markdown(text: str, path: str = "") -> PageContent:
    """Read a Markdown document by rendering it and reading the HTML.

    One parser for both spellings of a link, and for the raw HTML Markdown
    allows inline. Line numbers are recovered afterwards by searching the
    source, since the renderer does not keep them.
    """
    body = _FRONTMATTER.sub("", text, count=1)
    try:
        import markdown

        rendered = markdown.markdown(body, extensions=["fenced_code", "tables", "md_in_html"])
    except ImportError:  # pragma: no cover - markdown is a base dependency
        rendered = "<pre>" + html.escape(body) + "</pre>"
    page = read_html("<main>" + rendered + "</main>", path, "html")
    page.fmt, page.source = "md", text
    lines = text.splitlines()
    for record in [*page.passages, *page.actionables, *page.faq]:
        needle = getattr(record, "question", None) or getattr(record, "text", "")
        record.line = _line_of(lines, needle) or record.line
    if page.faq:
        page.faq_heading_line = _line_of(lines, "#", pattern=FAQ_HEADING) or 0
    return page


def _line_of(lines: list[str], needle: str, pattern: re.Pattern[str] | None = None) -> int:
    """First source line holding ``needle`` (or a heading matching ``pattern``)."""
    probe = (needle or "")[:40]
    for i, line in enumerate(lines, 1):
        if pattern is not None:
            if line.lstrip().startswith("#") and pattern.match(line.lstrip("# ").strip()):
                return i
        elif probe and probe in line:
            return i
    return 0


# ── JSON and YAML ──────────────────────────────────────────────────────────

_URL_KEYS = ("url", "href", "link", "permalink", "website", "homepage", "cta_url", "button_url")
_LABEL_KEYS = ("label", "title", "text", "name", "cta", "button", "caption")
_QUESTION_KEYS = ("question", "q", "title", "name")
_ANSWER_KEYS = ("answer", "a", "response", "reponse", "réponse", "text")


def read_data(obj: Any, path: str = "", fmt: str = "json") -> PageContent:
    """Walk a JSON or YAML document for destinations, FAQ entries and prose.

    Parameters
    ----------
    obj : Any
        The parsed document.
    path : str
        Where it lives, relative to the site root.
    fmt : str
        ``json`` or ``yaml``.

    Returns
    -------
    PageContent
        A data record: actionables of kind ``data``, FAQ items of origin
        ``data``, and every sentence-length string as a passage.
    """
    page = PageContent(path=path, fmt=fmt)

    def label_of(node: dict[str, Any]) -> str:
        for key in _LABEL_KEYS:
            value = node.get(key)
            if isinstance(value, str) and value.strip():
                return clean(value)
            if isinstance(value, dict):  # i18n maps: {"en": "...", "fr": "..."}
                first = next((v for v in value.values() if isinstance(v, str)), "")
                if first:
                    return clean(first)
        return ""

    def walk(node: Any, heading: str) -> None:
        if isinstance(node, dict):
            lowered = {str(k).lower(): v for k, v in node.items()}
            q = next((lowered[k] for k in _QUESTION_KEYS if isinstance(lowered.get(k), str)), None)
            ans = next((lowered[k] for k in _ANSWER_KEYS if isinstance(lowered.get(k), str)), None)
            if q and ans and q.strip().endswith("?") and q is not ans:
                page.faq.append(FaqItem(clean(q), _strip_tags(ans), "data"))
            for key in _URL_KEYS:
                value = lowered.get(key)
                if isinstance(value, str) and re.match(r"^(https?:|mailto:|tel:|/|\.\.?/)", value):
                    page.actionables.append(
                        Actionable(
                            kind="data",
                            text=label_of(lowered),
                            href=value,
                            tag=key,
                            attrs={k: v for k, v in lowered.items() if isinstance(v, str)},
                            order=len(page.actionables),
                        )
                    )
            title = label_of(lowered) or heading
            for value in node.values():
                walk(value, title)
        elif isinstance(node, list):
            for value in node:
                walk(value, heading)
        elif isinstance(node, str):
            text = _strip_tags(node)
            # Sentences, not slugs, ids or colour codes.
            if len(text) >= 40 and " " in text:
                page.passages.append(Passage(heading, text))

    walk(obj, "")
    return page


# ── The site ───────────────────────────────────────────────────────────────


def read_file(path: Path, root: Path) -> PageContent | None:
    """Read one file under ``root``, or ``None`` when it is not content."""
    fmt = FORMATS.get(path.suffix.lower())
    if fmt is None or path.name.lower() in SKIP_FILES or ".min." in path.name.lower():
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = path.name
    return read_text(text, rel, fmt)


def read_text(text: str, path: str, fmt: str | None = None) -> PageContent | None:
    """Read a document already in memory, as the HTTP surface receives it.

    Parameters
    ----------
    text : str
        The document's contents.
    path : str
        Its path relative to the site root; the suffix picks the reader when
        ``fmt`` is not given.
    fmt : str or None
        One of :data:`FORMATS`' values.

    Returns
    -------
    PageContent or None
        ``None`` for a data file that does not parse.
    """
    fmt = fmt or FORMATS.get(Path(path).suffix.lower(), "html")
    if fmt in {"html", "php"}:
        return read_html(text, path, fmt)
    if fmt == "md":
        return read_markdown(text, path)
    try:
        if fmt == "json":
            obj = json.loads(text)
        else:
            import yaml

            obj = yaml.safe_load(text)
    except Exception:  # noqa: BLE001 - any parse failure means "not data we can read"
        return None
    page = read_data(obj, path, fmt)
    page.source = text
    return page


def iter_files(root: Path) -> list[Path]:
    """Every content file under ``root``, skipping what is not content."""
    if root.is_file():
        return [root]
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.suffix.lower() not in FORMATS or not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts[:-1]
        if any(part in SKIP_DIRS or part.startswith(".") for part in rel_parts):
            continue
        out.append(p)
    return sorted(out)


def read_site(root: Path) -> list[PageContent]:
    """Read every content file of a site, in every format it is written in.

    Parameters
    ----------
    root : Path
        The site's folder, or one file.

    Returns
    -------
    list of PageContent
        One record per file that holds content, in path order.
    """
    base = root if root.is_dir() else root.parent
    pages: list[PageContent] = []
    for path in iter_files(root):
        page = read_file(path, base)
        if page is not None:
            pages.append(page)
    return pages
