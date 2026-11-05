#!/usr/bin/env python3
"""
faq
===

Help a site build the FAQ that stands between a reader and its call to action.

Most sites have no FAQ, so this tool's job is to **build** the section, not
to mark up one that exists. It drafts the questions, answers each one from
the site's own words, says which questions the site cannot answer yet, and
proposes where the section goes. When a FAQ is already there, it improves
it: same questions first, the missing ones added, the markup checked
against the visible text.

Why the visible text, and not the markup
----------------------------------------
Google stopped showing FAQ rich results on 2026-05-07 and removed their
documentation on 2026-06-15; it also says that "there's no special
schema.org markup you need to add" for generative search. Answer engines
read what a reader reads. So the deliverable is the visible section, and
the ``FAQPage`` JSON-LD is built **from the same text**, on the same page,
once per page. It is never claimed to rank.

Questions, in decreasing weight
-------------------------------
1. A hint file, one question per line, an optional count after a comma
   (``question,count``), whatever produced it: an analytics export, site
   search, a support inbox, sales notes.
2. The questions the site's FAQ already asks.
3. The buyer's objections at the point of decision, from a fixed checklist
   (who is it for, what does it cost, what happens after I click...).
4. Questions the site already asks in its own headings.

Ranked by that evidence, then by funnel stage (decide before evaluate before
learn): the questions between a reader and the declared CTA come first.

Grounded, or not answered
-------------------------
Each question is matched against every passage of the site (BM25, standard
library). A question no passage answers goes to the **gap report**, never to
the FAQ: that is the "do not invent facts" rule the suite's prompts carry,
and Google's policy against auto-generated low-value content.

The draft comes from the local model through ``best-engine-ai-helper`` when
it answers, and from the best passage's own sentences otherwise. Either way
one deterministic guard runs: **every number in an answer must appear in a
passage it was drawn from**, or the model's draft is thrown away.

Anatomy of an answer
--------------------
First sentence answers and names the product (it is what survives a
zero-click answer); one supporting fact; then the next step: the matching
CTA for a deciding question, a link to the source page for a learning one.
The CTA follows the answer, never replaces it.

Audit
-----
* ``FAQ001`` (warning) — an answer states a number no other page states.
* ``FAQ002`` (error) — a FAQ in JSON-LD only; the page shows none of it.
* ``FAQ003`` (error) — the JSON-LD and the visible FAQ disagree.
* ``FAQ004`` (warning) — one question marked up on several pages.
* ``FAQ005`` (warning) — an answer too long to be quoted whole (more than
  three sentences or 80 words), or whose first sentence does not name the
  organisation: engines quote that sentence alone.

``--fix`` writes only what is deterministic: on ``.html`` pages, the
``FAQPage`` block regenerated from the visible FAQ (``FAQ003``). Answers are
drafts for review and are never written by ``--fix``.

Exit code
---------
* 0 — no errors.
* 1 — an audit error (``FAQ002`` or ``FAQ003``) remains.
* 2 — nothing to read.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _click import run_command, sprezzature_command  # noqa: E402
from _content import FaqItem, PageContent, clean, read_site  # noqa: E402
from audit_site import ERROR, WARNING, Finding, render_json  # noqa: E402
from cta import (  # noqa: E402
    DECIDE,
    EVALUATE,
    LEARN,
    CtaPlan,
    CtaSpec,
    load_ctas,
    money_pages,
    render_findings,
)

# ── Words ──────────────────────────────────────────────────────────────────

_STOP = frozenset(
    "a an the and or of to in on for with by is are be it its this that what who how why "
    "when where which do does did can could i my me you your we our us they their at as "
    "from if not no so than then there about into after before up out will would should "
    "le la les un une des du de d l et ou à au aux en dans sur pour par avec est sont ce "
    "cette ces qui que quoi quel quelle quels quelles comment pourquoi quand où je mon ma "
    "mes vous votre vos nous notre nos il elle ils elles se sa son ses ne pas plus y a "
    "est-ce qu c s n j t m".split()
)
_WORD = re.compile(r"[\w'’-]+", re.U)
_NUMBER = re.compile(r"(?<![\w.])\d[\d\s.,]*\d(?![\w])|(?<![\w.])\d(?![\w])")


def fold(text: str) -> str:
    """Lower-case and strip accents, so ``prix`` matches ``Prix`` and ``é`` ``e``."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def terms(text: str) -> list[str]:
    """Content words of ``text``, folded, stop words removed."""
    out = []
    for raw in _WORD.findall(fold(text)):
        word = raw.strip("'’-")
        if len(word) > 1 and word not in _STOP and not word.isdigit():
            out.append(word)
    return out


#: Thousands groups: one to three digits, then groups of exactly three.
_THOUSANDS = re.compile(r"\d{1,3}(?:[\s.,]\d{3})+")
#: A number that names something rather than counts it: a standard
#: (``ISO 3166``, ``RFC 9110``). Not a fact anyone could find false.
_NAMED = re.compile(r"\b(?:ISO|IEC|RFC|EN|IEEE|ECMA)[\s/-]*$")
#: Code, in Markdown or HTML: ``min-h-11`` is a class name and ``--classes 12``
#: an invocation, literals a reader copies rather than facts a page sources.
_CODE = re.compile(r"`[^`\n]*`|<code\b[^>]*>.*?</code>", re.S | re.I)


def _canonical_number(raw: str) -> str:
    """One spelling per number: ``1 885`` = ``1,885`` = ``1885``; ``3,5`` = ``3.5``.

    Every separator used to be dropped, so the Python version ``3.10`` was
    read as three hundred and ten and reported as a figure no other page
    states. Separators are thousands only when the groups after them are
    three digits; otherwise the last one is a decimal point, and a string with
    several (``1.11.0``) is a version, kept whole.
    """
    raw = re.sub(r"\s+", " ", raw.strip())
    if _THOUSANDS.fullmatch(raw):
        return re.sub(r"[\s.,]", "", raw)
    seps = re.findall(r"[\s.,]", raw)
    if len(seps) == 1:
        return raw.replace(",", ".").replace(" ", "")
    return raw.replace(" ", "")


def numbers(text: str) -> set[str]:
    """Numbers in ``text``, one spelling each: ``1 885`` and ``1,885`` are one."""
    return {_canonical_number(m.group(0)) for m in _NUMBER.finditer(text)}


def claimed_numbers(text: str, literals: Iterable[str] = ()) -> set[str]:
    """The numbers in ``text`` that state a fact a reader could check.

    Leaves out a single digit (an exit code, a step, "one of three"), which
    every page states in passing, and a number that is part of a standard's
    name, or a number inside code. FAQ001 asks for a source; none has one to
    give.
    """
    text = _CODE.sub(lambda m: " " * len(m.group(0)), text)
    # Longest first, so ``min-h-11`` goes whole before any shorter literal
    # inside it; two characters or fewer would blank half the prose.
    for lit in sorted((x for x in literals if len(x) > 2), key=len, reverse=True):
        text = text.replace(lit, " " * len(lit))
    out = set()
    for m in _NUMBER.finditer(text):
        n = _canonical_number(m.group(0))
        if len(n) == 1 or _NAMED.search(text[: m.start()]):
            continue
        out.add(n)
    return out


def sentences(text: str) -> list[str]:
    """Split prose into sentences, keeping abbreviations like ``e.g.`` whole."""
    parts = re.split(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÖØ-Þ0-9«“\"(])", text.strip())
    return [p.strip() for p in parts if p.strip()]


# ── The corpus ─────────────────────────────────────────────────────────────


@dataclass
class Source:
    """One passage of the site, with where it comes from."""

    page: str
    heading: str
    text: str
    line: int = 0
    core: bool = False  # on the home page or a money page


class Index:
    """BM25 over the site's passages. Small, exact, standard library."""

    K1, B = 1.5, 0.75

    def __init__(self, sources: list[Source]) -> None:
        self.sources = sources
        self.docs = [Counter(terms(f"{s.heading} {s.text}")) for s in sources]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lengths) / len(self.lengths)) if self.lengths else 0.0
        df: Counter[str] = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: list[str], k: int = 4) -> list[tuple[float, Source]]:
        """The ``k`` best passages for ``query``, best first, score > 0 only."""
        scored: list[tuple[float, int]] = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            for t in set(query):
                f = doc.get(t, 0)
                if not f:
                    continue
                norm = self.K1 * (1 - self.B + self.B * self.lengths[i] / (self.avg or 1))
                score += self.idf.get(t, 0.0) * f * (self.K1 + 1) / (f + norm)
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [(s, self.sources[i]) for s, i in scored[:k]]


_LANGS: dict[int, str] = {}


def page_lang(page: PageContent) -> str:
    """The page's declared language, or the one its text is written in.

    A PHP page often has no ``lang`` attribute: the shell prints it. Then
    the text decides, once per page.
    """
    if page.lang:
        return page.lang.lower()[:2]
    key = id(page)
    if key not in _LANGS:
        from _lang import detect_text_language

        _LANGS[key] = detect_text_language(page.text[:1500], fallback="")
    return _LANGS[key]


_PLACEHOLDER = re.compile(r"\{\w*\}|%[sd]|\$\{")

#: Headings of reference lists. Their notes describe somebody else's work
#: ("How Vanna works, how to train it, data security. medium.com"), and on
#: the calibration site the extractive fallback quoted them as answers.
REFERENCE_HEADING = re.compile(
    r"^\s*(bibliograph\w*|r[ée]f[ée]rences?|sources?|notes?|further reading|works cited"
    r"|lectures?( compl[ée]mentaires?)?|pour aller plus loin)\b",
    re.I,
)


def is_home(path: str) -> bool:
    """The site's front page, in any of its languages."""
    return bool(re.fullmatch(r"([a-z]{2}(-[a-z]{2})?/)?(index\.(html?|php|md)|README\.md)", path))


def corpus(
    pages: list[PageContent], lang: str = "", core: frozenset[str] = frozenset()
) -> list[Source]:
    """Every passage a reader can see on a page, in the site's language.

    Left out: FAQ answers, because an answer that is only true because the
    FAQ says so is what the gap report exists to catch; data files, whose
    strings are rendered elsewhere and often half a sentence
    (``{0} lignes sur {1}``, from an i18n table, read as prose the first
    time); reference lists, whose notes describe other people's work; and
    pages in another language, so an English FAQ is not answered in French.
    """
    out: list[Source] = []
    for page in pages:
        if not page.is_page:
            continue
        if lang and page_lang(page) not in {lang, ""}:
            continue
        faq_answers = {fold(clean(f.answer)) for f in page.faq}
        is_core = page.path in core or is_home(page.path)
        for p in page.passages:
            text = clean(p.text)
            if (
                len(text) < 20
                or REFERENCE_HEADING.match(p.heading or "")
                or fold(text) in faq_answers
                or _PLACEHOLDER.search(text)
                or "<" in text  # a <video> fallback, markup shown as text
            ):
                continue
            out.append(Source(page.path, p.heading, text, p.line, is_core))
    return out


# ── Questions ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Objection:
    """One question every buyer asks, and the words an answer to it uses."""

    stage: str
    en: str
    fr: str
    vocabulary: tuple[str, ...]


#: The checklist at the point of decision. ``{p}`` is the product's name.
#: The vocabulary is what a passage must contain to count as an answer; it
#: is folded (no accents) and matched as word prefixes.
OBJECTIONS: tuple[Objection, ...] = (
    Objection(
        DECIDE,
        "Who is {p} for?",
        "À qui s'adresse {p} ?",
        ("for teams", "for people", "audience", "designed for", "built for", "pour les", "destine"),
    ),
    Objection(
        DECIDE,
        "How much does {p} cost?",
        "Combien coûte {p} ?",
        ("price", "pricing", "cost", "free", "licen", "pay", "prix", "tarif", "cout", "gratuit"),
    ),
    Objection(
        DECIDE,
        "How does {p} compare with the alternatives?",
        "Comment {p} se compare-t-il aux alternatives ?",
        ("compar", "alternative", "unlike", "instead of", "versus", "contrairement", "plutot"),
    ),
    Objection(
        DECIDE,
        "What happens after I {action}?",
        "Que se passe-t-il quand je {action} ?",
        ("after", "then", "next", "within", "call", "reply", "ensuite", "puis", "apres", "sous"),
    ),
    Objection(
        DECIDE,
        "What happens to my data with {p}?",
        "Que deviennent mes données avec {p} ?",
        ("data", "privacy", "offline", "local", "never sent", "donnees", "confidential", "hors"),
    ),
    Objection(
        EVALUATE,
        "How do I get started with {p}?",
        "Comment commencer avec {p} ?",
        ("install", "get started", "start", "setup", "pip", "npm", "commencer", "demarr"),
    ),
    Objection(
        EVALUATE,
        "What does {p} need to run?",
        "De quoi {p} a-t-il besoin pour fonctionner ?",
        (
            "requires",
            "require",
            "python",
            "macos",
            "linux",
            "windows",
            "gpu",
            "memory",
            "necessite",
        ),
    ),
    Objection(
        LEARN,
        "What is {p}?",
        "Qu'est-ce que {p} ?",
        ("is a", "is an", "est un", "est une", "lets", "turns", "permet"),
    ),
    Objection(
        LEARN,
        "How does {p} work?",
        "Comment fonctionne {p} ?",
        ("works", "reads", "runs", "uses", "step", "fonctionne", "lit", "utilise", "etape"),
    ),
)

#: Weight of where a question came from. A real question beats a guess.
EVIDENCE: dict[str, float] = {"hint": 3.0, "existing": 2.0, "objection": 1.0, "heading": 0.5}
STAGE_WEIGHT: dict[str, float] = {DECIDE: 3.0, EVALUATE: 2.0, LEARN: 1.0}


@dataclass
class Question:
    """A candidate question and the reasons it is on the list."""

    text: str
    stage: str
    origin: str  # hint / existing / objection / heading
    count: int = 0
    vocabulary: tuple[str, ...] = ()
    existing_answer: str = ""
    page: str = ""  # for a heading question: the page that asks it

    @property
    def weight(self) -> float:
        bonus = math.log2(1 + self.count) if self.count else 0.0
        return (EVIDENCE[self.origin] + bonus) * STAGE_WEIGHT[self.stage]


def stage_of(question: str) -> str:
    """Guess the funnel stage of a free-text question from its words."""
    words = " ".join(terms(question))
    if re.search(
        r"\b(price|pricing|cost|buy|book|contact|refund|contract|support|prix|tarif|cout|"
        r"acheter|reserver|contrat|rembours|devis|data|donnees|privacy)",
        words,
    ):
        return DECIDE
    if re.search(
        r"\b(install|start|setup|try|download|requir|need|run|free|trial|essai|install|"
        r"commencer|telecharg|besoin)",
        words,
    ):
        return EVALUATE
    return LEARN


def read_hints(path: Path) -> list[Question]:
    """One question per line, an optional ``,count`` after it.

    Source-agnostic on purpose: an analytics export, a site-search log, a
    support inbox and sales notes all reduce to this. Lines that are not
    questions (no ``?``, fewer than three words) are skipped.
    """
    out: list[Question] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip().strip('"')
        if not line or line.startswith("#"):
            continue
        count = 0
        m = re.match(r"^(.*?)[,;\t]\s*(\d+)\s*$", line)
        if m:
            line, count = m.group(1).strip().strip('"'), int(m.group(2))
        if len(line.split()) < 3:
            continue
        if not line.endswith("?"):
            line = line.rstrip(".") + ("?" if not re.search(r"\s\?$", line) else "")
        out.append(Question(line, stage_of(line), "hint", count))
    return out


def objection_questions(product: str, plan: CtaPlan | None, lang: str) -> list[Question]:
    """The checklist, worded for this product and its primary CTA."""
    primary = plan.primary if plan else None
    if primary is not None:
        label = primary.label.strip().rstrip("→ ").strip()
        action = f"click “{label}”" if lang != "fr" else f"clique sur « {label} »"
    else:
        action = "get in touch" if lang != "fr" else "prends contact"
    out = []
    for o in OBJECTIONS:
        if "{action}" in o.en and primary is None:
            continue  # "after I get in touch" asks about a CTA nobody declared
        template = o.fr if lang == "fr" else o.en
        text = template.format(p=product, action=action)
        out.append(Question(text, o.stage, "objection", 0, o.vocabulary))
    return out


def in_scope(path: str, core: frozenset[str] = frozenset()) -> bool:
    """A page of the site itself, not of a project it hosts.

    The root, a language folder (``fr/``), and the money pages. On the
    calibration site, ``ai-bunker/`` and ``saggio/`` each carry their own
    FAQ about their own product; a FAQ for the site is not made of theirs.
    """
    parts = path.split("/")
    return path in core or len(parts) == 1 or (len(parts) == 2 and bool(_LANG_DIR.match(parts[0])))


_LANG_DIR = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")


def existing_questions(
    pages: list[PageContent], lang: str = "", core: frozenset[str] = frozenset()
) -> list[Question]:
    """The questions the site's own FAQs already ask, visible or marked up."""
    seen: set[str] = set()
    out = []
    for page in pages:
        if lang and page_lang(page) not in {lang, ""}:
            continue
        if not in_scope(page.path, core):
            continue
        # A FAQ that only exists as markup is still the author's own
        # wording: it becomes the visible section, which is FAQ002's repair.
        for item in [*page.faq, *page.jsonld_faq]:
            key = fold(item.question)
            if key in seen or not item.question:
                continue
            seen.add(key)
            out.append(
                Question(item.question, stage_of(item.question), "existing", 0, (), item.answer)
            )
    return out


def heading_questions(
    pages: list[PageContent], lang: str = "", core: frozenset[str] = frozenset()
) -> list[Question]:
    """Headings that are already questions, outside any FAQ."""
    seen: set[str] = set()
    out = []
    for page in pages:
        if lang and page_lang(page) not in {lang, ""}:
            continue
        if not in_scope(page.path, core):
            continue
        in_faq = {fold(f.question) for f in page.faq}
        for p in page.passages:
            h = clean(p.heading)
            if h.endswith("?") and fold(h) not in in_faq and fold(h) not in seen:
                seen.add(fold(h))
                out.append(Question(h, stage_of(h), "heading", page=page.path))
    return out


def similar(a: str, b: str) -> bool:
    """Two questions asking the same thing: their words mostly shared.

    All the words, question words included. On content words alone, "Who is
    X for?" and "What is X?" are both just ``{x}``, and the checklist's
    guess swallowed the author's own question.
    """
    ta = {w for w in _WORD.findall(fold(a)) if len(w) > 1}
    tb = {w for w in _WORD.findall(fold(b)) if len(w) > 1}
    if not ta or not tb:
        return fold(a) == fold(b)
    return len(ta & tb) / len(ta | tb) >= 0.6


def dedupe(questions: list[Question]) -> list[Question]:
    """Keep one of each group of near-identical questions.

    A real question beats the checklist's wording of it whatever the stage
    weights say: the evidence decides which spelling survives, the weight
    decides the order afterwards.
    """
    out: list[Question] = []
    for q in sorted(questions, key=lambda q: (-EVIDENCE[q.origin], -q.weight)):
        if not any(similar(q.text, kept.text) for kept in out):
            out.append(q)
    return out


# ── Answers ────────────────────────────────────────────────────────────────


@dataclass
class Answer:
    """A grounded answer, or the reason there is none."""

    question: str
    stage: str
    origin: str
    answer: str = ""
    sources: list[Source] = field(default_factory=list)
    next_step: str = ""  # Markdown: a link, or an install command
    drafted_by: str = ""  # model / extract / existing
    notes: list[str] = field(default_factory=list)
    weight: float = 0.0

    @property
    def grounded(self) -> bool:
        return bool(self.answer)


def _has_vocabulary(text: str, vocabulary: tuple[str, ...]) -> bool:
    folded = " " + " ".join(_WORD.findall(fold(text))) + " "
    return any(f" {v}" in folded for v in vocabulary)


def ground(
    question: Question, index: Index, product: str, *, threshold: float = 0.0
) -> list[Source]:
    """The passages that answer ``question``, or none.

    A passage counts when it scores on the question's own words, the
    product's name excluded (every passage of a product site names it), and
    when, for a checklist question, it uses the vocabulary an answer needs:
    "How much does it cost?" is not answered by a passage that never speaks
    of price, licence or payment. A free-text question needs half its own
    words in the passage instead. BM25 scores alone are not comparable
    between a one-page site, where every word's weight is near zero, and a
    thousand-page one, so no score threshold applies by default.
    """
    product_terms = set(terms(product))
    query = [t for t in terms(question.text) if t not in product_terms]
    if question.vocabulary:
        query += [t for v in question.vocabulary for t in terms(v)]
    if not query:
        return []
    hits = []
    for score, source in index.search(query, k=8):
        if score < threshold:
            continue
        if not question.vocabulary:
            own = set(query)
            if len(own & set(terms(f"{source.heading} {source.text}"))) < len(own) / 2:
                continue
        if question.vocabulary:
            if not _has_vocabulary(source.text, question.vocabulary):
                continue
            # "price" in a chart gallery is a price axis. A deciding answer
            # comes from the front or a money page; the others may also come
            # from a passage that names the product.
            named = bool(set(terms(source.text)) & product_terms)
            if not (source.core or (named and question.stage != DECIDE)):
                continue
        hits.append(source)
    return hits[:3]


def extract_answer(question: Question, sources: list[Source], product: str) -> str:
    """The best two sentences of the sources, in their own words.

    Sentences are ranked by the question's words they share; the product's
    name and the checklist vocabulary each add one. Nothing is rephrased, so
    nothing can be invented.
    """
    wanted = set(terms(question.text)) | {t for v in question.vocabulary for t in terms(v)}

    # A checklist question is answered by a sentence that uses its words.
    def fits(sentence: str) -> bool:
        return not question.vocabulary or _has_vocabulary(sentence, question.vocabulary)

    product_terms = set(terms(product))
    ranked: list[tuple[float, int, str]] = []
    order = 0
    for source in sources:
        for sentence in sentences(source.text):
            words = set(terms(sentence))
            score = len(words & wanted) + (1.0 if words & product_terms else 0.0)
            if (
                6 <= len(sentence.split()) <= 60
                and re.search(r"[.!?…]$", sentence)
                and fits(sentence)
            ):
                ranked.append((score, order, sentence))
            order += 1
    ranked.sort(key=lambda r: (-r[0], r[1]))
    best = sorted(ranked[:2], key=lambda r: r[1])
    return " ".join(sentence for score, _, sentence in best if score > 0)


def numbers_are_sourced(answer: str, sources: list[Source]) -> set[str]:
    """Numbers of ``answer`` that none of ``sources`` states. Empty is good."""
    stated: set[str] = set()
    for s in sources:
        stated |= numbers(s.text)
    return numbers(answer) - stated


#: A model call, injectable: ``(prompt) -> raw text``. ``None`` = no model.
Drafter = Callable[[str], str]


def draft_with_model(
    question: Question,
    sources: list[Source],
    product: str,
    lang: str,
    chat: Drafter,
) -> tuple[str, list[Source], str]:
    """Ask the model, then keep its answer only if every number is sourced.

    Returns
    -------
    tuple
        ``(answer, sources used, note)``; an empty answer when the model
        declined, failed, or stated a number the passages do not.
    """
    from _ollama import LANG_INSTRUCTIONS
    from _prompts import render

    numbered = "\n".join(
        f"[{i}] ({s.page}{' — ' + s.heading if s.heading else ''}) {s.text[:900]}"
        for i, s in enumerate(sources, 1)
    )
    prompt = render(
        "faq_answer",
        lang_line=LANG_INSTRUCTIONS.get(lang, LANG_INSTRUCTIONS.get("en", "")),
        product=product,
        question=question.text,
        passages=numbered,
    )
    try:
        raw = chat(prompt)
    except Exception as exc:  # noqa: BLE001 - any model failure means "use the extract"
        return "", [], f"model unavailable ({type(exc).__name__})"
    match = re.search(r"\{.*\}", raw, re.S)
    try:
        data = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        return "", [], "model answer was not JSON"
    answer = clean(str(data.get("answer", "")))
    if not answer:
        return "", [], "model found no answer in the passages"
    picked = [
        sources[i - 1]
        for i in data.get("sources", [])
        if isinstance(i, int) and 1 <= i <= len(sources)
    ] or sources
    loose = numbers_are_sourced(answer, picked)
    if loose:
        return "", [], f"model stated {', '.join(sorted(loose))}, which no passage states"
    return answer, picked, ""


def cta_for(stage: str, plan: CtaPlan | None) -> CtaSpec | None:
    """The declared CTA a question of this stage ends on."""
    if not plan or not plan.ctas:
        return None
    if stage == DECIDE:
        return next((c for c in plan.ctas if c.stage == DECIDE), plan.primary)
    if stage == EVALUATE:
        return next((c for c in plan.ctas if c.stage == EVALUATE), plan.primary)
    return None


def next_step(stage: str, plan: CtaPlan | None, sources: list[Source], lang: str) -> str:
    """Markdown for what follows the answer: the CTA, or the deeper page."""
    spec = cta_for(stage, plan)
    if spec is not None:
        if spec.is_command:
            return f"`{spec.url}`"
        return f"[{spec.label}]({spec.url})"
    if sources:
        page = sources[0].page
        href = "/" + re.sub(r"\.(md|markdown)$", ".html", page)
        label = sources[0].heading or ("Read more" if lang != "fr" else "En savoir plus")
        return f"[{label}]({href})"
    return ""


# ── Building the section ───────────────────────────────────────────────────


@dataclass
class Placement:
    """Where the section goes on one page."""

    page: str
    line: int
    reason: str


@dataclass
class FaqBuild:
    """Everything the build produced, for the author to review."""

    product: str
    lang: str
    items: list[Answer]
    gaps: list[Answer]
    placements: list[Placement]
    existing: bool


def product_name(pages: list[PageContent], plan: CtaPlan | None) -> str:
    """The one name answers use: declared, else the home page's title."""
    if plan and plan.organization:
        return plan.organization
    home = next(
        (p for p in pages if p.path in {"index.html", "index.php", "index.md", "README.md"}),
        None,
    )
    for page in [home, *pages] if home else pages:
        if page is not None and page.title:
            return re.split(r"\s+[—–|·:-]\s+", page.title)[0].strip()
    return "this site"


def site_lang(pages: list[PageContent]) -> str:
    """The language most pages declare, ``en`` when none does."""
    langs = Counter(p.lang.lower()[:2] for p in pages if p.lang)
    return langs.most_common(1)[0][0] if langs else "en"


def build_faq(
    pages: list[PageContent],
    plan: CtaPlan | None = None,
    hints: list[Question] | None = None,
    *,
    top: int = 8,
    lang: str = "",
    chat: Drafter | None = None,
) -> FaqBuild:
    """Draft the FAQ section from the whole site.

    Parameters
    ----------
    pages : list of PageContent
        The site, from :func:`_content.read_site`.
    plan : CtaPlan, optional
        The declared CTAs. Without it, questions are ranked by evidence only
        and no answer ends on a CTA.
    hints : list of Question, optional
        Real questions (:func:`read_hints`); they rank first.
    top : int
        Items in the section; 6 to 10 is what a reader reads.
    lang : str
        ``en`` or ``fr``; detected from the pages when empty.
    chat : callable, optional
        ``(prompt) -> text``. ``None`` drafts by extraction only.

    Returns
    -------
    FaqBuild
        Grounded items, best first; the gap report; where to place it.
    """
    lang = lang or site_lang(pages)
    product = product_name(pages, plan)
    core = frozenset(money_pages(pages, plan)) if plan and plan.ctas else frozenset()
    index = Index(corpus(pages, lang, core))
    pool = dedupe(
        [
            *(hints or []),
            *existing_questions(pages, lang, core),
            *objection_questions(product, plan, lang),
            *heading_questions(pages, lang, core),
        ]
    )
    items: list[Answer] = []
    gaps: list[Answer] = []
    for q in pool:
        ans = Answer(q.text, q.stage, q.origin, weight=q.weight)
        if q.origin == "heading":
            # The page that asks the question answers it, under the heading.
            sources = [s for s in index.sources if s.page == q.page and s.heading == q.text][:3]
        else:
            sources = ground(q, index, product)
        if q.existing_answer:
            ans.answer, ans.drafted_by = clean(q.existing_answer), "existing"
            ans.sources = sources
            loose = numbers_are_sourced(ans.answer, sources) if sources else numbers(ans.answer)
            if loose:
                ans.notes.append(f"states {', '.join(sorted(loose))}, which no other page states")
            if not sources:
                ans.notes.append("no other page supports this answer")
        elif sources:
            if chat is not None:
                text, used, note = draft_with_model(q, sources, product, lang, chat)
                if text:
                    ans.answer, ans.sources, ans.drafted_by = text, used, "model"
                elif note:
                    ans.notes.append(note)
            if not ans.answer:
                text = extract_answer(q, sources, product)
                if text:
                    ans.answer, ans.sources, ans.drafted_by = text, sources, "extract"
        if not ans.answer:
            gaps.append(ans)
            continue
        if ans.drafted_by != "existing" and not set(terms(product)) & set(terms(ans.answer)):
            ans.notes.append(f"the first sentence does not name {product}")
        ans.next_step = next_step(q.stage, plan, ans.sources, lang)
        items.append(ans)
    items.sort(key=lambda a: -a.weight)
    return FaqBuild(
        product=product,
        lang=lang,
        items=items[:top],
        gaps=[g for g in gaps if g.origin != "heading"],
        placements=placements(pages, plan, lang),
        existing=any(p.faq for p in pages),
    )


def placements(pages: list[PageContent], plan: CtaPlan | None, lang: str = "") -> list[Placement]:
    """Where the section goes: money pages first, above the final CTA.

    A page with a FAQ heading keeps its place. Otherwise the section goes
    just before ``</main>``, which on a landing page is where the last CTA
    sits; the author moves it if the page ends otherwise.
    """
    chosen = money_pages(pages, plan) if plan and plan.ctas else []
    if not chosen:
        homes = [p for p in pages if p.is_page and is_home(p.path)]
        homes.sort(
            key=lambda p: (
                bool(lang) and page_lang(p) != lang,
                p.fmt == "md",  # a README is the repository's front page, not the site's
                p.path.count("/"),
            )
        )
        chosen = [p.path for p in homes[:1]]
    by_path = {p.path: p for p in pages}
    out = []
    for path in chosen:
        page = by_path.get(path)
        if page is None or not page.is_page:
            continue
        if page.faq_heading_line:
            out.append(Placement(path, page.faq_heading_line, "replace the existing FAQ"))
        elif page.main_end_line:
            out.append(Placement(path, page.main_end_line, "before </main>, above the last CTA"))
        else:
            out.append(Placement(path, 0, "at the end of the page, above the last CTA"))
    return out


# ── Rendering ──────────────────────────────────────────────────────────────

HEADING = {"en": "Frequently asked questions", "fr": "Questions fréquentes"}


def _full_answer(item: Answer) -> str:
    return f"{item.answer} {item.next_step}".strip() if item.next_step else item.answer


def _md_to_text(markdown: str) -> str:
    """``[label](url)`` → ``label``, `` `code` `` → ``code``, for the JSON-LD."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", markdown)
    return re.sub(r"`([^`]+)`", r"\1", text)


def faq_jsonld(items: list[Answer] | list[FaqItem]) -> dict[str, Any]:
    """The ``FAQPage`` node, built from the very text the reader sees."""
    entities = []
    for item in items:
        q = item.question
        a = _md_to_text(_full_answer(item)) if isinstance(item, Answer) else item.answer
        entities.append(
            {
                "@type": "Question",
                "name": q,
                "acceptedAnswer": {"@type": "Answer", "text": clean(a)},
            }
        )
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entities}


def _jsonld_script(node: dict[str, Any]) -> str:
    body = json.dumps(node, ensure_ascii=False, indent=2).replace("</", "<\\/")
    return f'<script type="application/ld+json">\n{body}\n</script>'


def render_faq_markdown(build: FaqBuild) -> str:
    """The section in Markdown, with its JSON-LD as a raw HTML block."""
    lines = [f"## {HEADING.get(build.lang, HEADING['en'])}", ""]
    for item in build.items:
        lines += [f"### {item.question}", "", _full_answer(item), ""]
    if build.items:
        lines += [_jsonld_script(faq_jsonld(build.items)), ""]
    return "\n".join(lines)


def _md_inline_to_html(markdown: str) -> str:
    out = html.escape(markdown, quote=False)
    out = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{html.escape(html.unescape(m.group(2)))}">{m.group(1)}</a>',
        out,
    )
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", out)


def render_faq_html(build: FaqBuild) -> str:
    """The section as an HTML fragment to paste where :class:`Placement` says."""
    lines = [
        '<section id="faq" aria-labelledby="faq-title">',
        f'  <h2 id="faq-title">{html.escape(HEADING.get(build.lang, HEADING["en"]))}</h2>',
    ]
    for item in build.items:
        lines.append(f"  <h3>{html.escape(item.question)}</h3>")
        lines.append(f"  <p>{_md_inline_to_html(_full_answer(item))}</p>")
    lines.append("</section>")
    if build.items:
        lines.append(_jsonld_script(faq_jsonld(build.items)))
    return "\n".join(lines)


def render_report(build: FaqBuild) -> str:
    """What the author reads after the section: drafts to check, gaps, places."""
    out = []
    review = [i for i in build.items if i.notes or i.drafted_by == "model"]
    if review:
        out.append("Check before publishing:")
        for i in review:
            why = "; ".join(i.notes) or "drafted by the model"
            out.append(f"  - {i.question} — {why}")
            for s in i.sources[:2]:
                out.append(f"      source: {s.page}{':' + str(s.line) if s.line else ''}")
    if build.gaps:
        out.append("\nQuestions the site cannot answer yet (write the page, then run again):")
        for g in build.gaps:
            extra = f" ({'; '.join(g.notes)})" if g.notes else ""
            out.append(f"  - [{g.stage}] {g.question}{extra}")
    if build.placements:
        out.append("\nWhere the section goes:")
        for p in build.placements:
            where = f"{p.page}:{p.line}" if p.line else p.page
            out.append(f"  - {where} — {p.reason}")
    return "\n".join(out)


# ── Audit ──────────────────────────────────────────────────────────────────


def _same(a: str, b: str) -> bool:
    """Whether two answers say the same words, markup aside on *both* sides.

    The JSON-LD side has its tags stripped when it is read; the visible side
    is text the parser already decoded, so an answer quoting an element --
    "a clickable ``&lt;div&gt;``" -- kept ``<div>`` there and lost it in the
    markup, and every such answer was reported as disagreeing with itself.
    """

    def words(s: str) -> str:
        return " ".join(terms(re.sub(r"<[^>]+>", " ", s)))

    return words(a) == words(b)


#: Past these, an answer engine quotes a fragment or nothing: the drafting
#: prompt allows three sentences, and the answers engines lift whole run to
#: roughly forty to eighty words.
MAX_SENTENCES, MAX_WORDS = 3, 80


def _org_core(organization: str) -> str:
    """ "Deraison.ai" is written "Deraison" in running text."""
    return fold(
        re.sub(r"\.(ai|io|com|org|net|fr|co|app|dev)$", "", organization.strip(), flags=re.I)
    )


def audit_faq(pages: list[PageContent], organization: str = "") -> list[Finding]:
    """Check every FAQ on the site, visible and marked up.

    The visible FAQ is the reference: engines read it, and the markup is
    only ever a copy of it.
    """
    findings: list[Finding] = []
    index_sources = corpus(pages)  # every language: a number is a number
    marked: dict[str, list[str]] = defaultdict(list)
    for page in pages:
        if page.jsonld_faq and not page.faq:
            findings.append(
                Finding(
                    page.path,
                    0,
                    "FAQ002",
                    ERROR,
                    f"FAQPage markup with {len(page.jsonld_faq)} question(s) and no visible "
                    "FAQ on the page; engines read the visible text, and Google requires "
                    "marked-up content to be visible.",
                    "sprezzature-publish-faq <site> --format html, then paste the section",
                )
            )
        elif page.jsonld_faq and page.faq:
            visible = {fold(f.question): f for f in page.faq}
            marks = {fold(f.question): f for f in page.jsonld_faq}
            missing = [marks[k].question for k in marks if k not in visible]
            unmarked = [visible[k].question for k in visible if k not in marks]
            differ = [
                marks[k].question
                for k in marks
                if k in visible and not _same(marks[k].answer, visible[k].answer)
            ]
            if missing or unmarked or differ:
                parts = []
                if missing:
                    parts.append(f"marked up but not shown: {missing[0]!r}")
                if unmarked:
                    parts.append(f"shown but not marked up: {unmarked[0]!r}")
                if differ:
                    parts.append(f"answer differs: {differ[0]!r}")
                findings.append(
                    Finding(
                        page.path,
                        page.faq_heading_line,
                        "FAQ003",
                        ERROR,
                        "The FAQPage markup and the visible FAQ disagree ("
                        + "; ".join(parts)
                        + ").",
                        "" if page.fmt == "html" else "rebuild the JSON-LD from the visible FAQ",
                    )
                )
        for f in page.jsonld_faq:
            marked[fold(f.question)].append(page.path)
        for item in page.faq:
            others = [s for s in index_sources if s.page != page.path]
            loose = claimed_numbers(item.answer, page.literals) - {
                n for s in others for n in numbers(s.text)
            }
            if loose and others:
                findings.append(
                    Finding(
                        page.path,
                        item.line,
                        "FAQ001",
                        WARNING,
                        f"The answer to {item.question!r} states {', '.join(sorted(loose))}, "
                        "which no other page of the site states.",
                        "cite where the number comes from, or remove it",
                    )
                )
    core = _org_core(organization) if organization else ""
    for page in pages:
        for item in page.faq:
            parts = sentences(item.answer)
            words = len(item.answer.split())
            problems = []
            if len(parts) > MAX_SENTENCES or words > MAX_WORDS:
                problems.append(f"{len(parts)} sentences, {words} words")
            if core and parts and core not in fold(parts[0]) and core not in fold(item.question):
                problems.append(f"the first sentence does not name {organization}")
            if problems:
                findings.append(
                    Finding(
                        page.path,
                        item.line,
                        "FAQ005",
                        WARNING,
                        f"The answer to {item.question!r} is hard to quote alone: "
                        + "; ".join(problems)
                        + ".",
                        "answer in the first sentence, naming the organisation; "
                        "then one supporting fact; three sentences at most",
                    )
                )
    for question, where in marked.items():
        if len(set(where)) > 1:
            first = sorted(set(where))
            findings.append(
                Finding(
                    first[0],
                    0,
                    "FAQ004",
                    WARNING,
                    f"The same question is marked up on {len(first)} pages "
                    f"({', '.join(first[:3])}{'…' if len(first) > 3 else ''}); mark it up "
                    "on one.",
                    "keep the FAQPage markup on the page that answers it best",
                )
            )
    return findings


_LD_BLOCK = re.compile(
    r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.S | re.I
)


def fix_faq(pages: list[PageContent], root: Path) -> list[str]:
    """Regenerate the FAQPage JSON-LD from the visible FAQ, ``.html`` only.

    Only a block whose top-level node *is* a ``FAQPage`` is replaced; a
    ``@graph`` mixing several types is reported and left alone, because
    rewriting it means rewriting markup this tool did not write.

    Returns
    -------
    list of str
        The paths written.
    """
    written = []
    for page in pages:
        if page.fmt != "html" or not page.faq or not page.jsonld_faq:
            continue
        if not any(f.rule == "FAQ003" for f in audit_faq([page])):
            continue
        source = page.source
        replaced = False

        def swap(m: re.Match[str]) -> str:
            nonlocal replaced
            try:
                node = json.loads(m.group(1))
            except json.JSONDecodeError:
                return m.group(0)
            if isinstance(node, dict) and node.get("@type") == "FAQPage" and not replaced:
                replaced = True
                return _jsonld_script(faq_jsonld(page.faq))
            return m.group(0)

        new = _LD_BLOCK.sub(swap, source)
        if replaced and new != source:
            (root / page.path).write_text(new, encoding="utf-8")
            written.append(page.path)
    return written


# ── The model, behind the suite's one door ─────────────────────────────────

CACHE_DIR: Path = (
    Path(os.environ.get("SPREZZATURE_CACHE_DIR") or Path.home() / ".cache" / "sprezzature-skill")
    / "faq"
)


def model_drafter(no_cache: bool = False) -> Drafter | None:
    """A memoised ``(prompt) -> text`` through best-engine-ai-helper, or ``None``."""
    try:
        from best_engine_ai_helper.llm import chat as _llm_chat
    except ImportError:  # pragma: no cover - a base dependency
        return None
    from _ollama import ollama_engine, pick_default_model
    from _wallet import memoized

    model = pick_default_model()

    def chat(prompt: str) -> str:
        digest = hashlib.sha256(f"{model}\x00{prompt}".encode()).hexdigest()[:32]
        return str(
            memoized(
                "faq",
                digest,
                lambda: str(_llm_chat(prompt, model=model, engine=ollama_engine(model))),
                cache_dir=CACHE_DIR,
                enabled=not (no_cache or os.environ.get("SPREZZATURE_NO_CACHE")),
            )
        )

    return chat


# ── CLI ────────────────────────────────────────────────────────────────────


@sprezzature_command(
    "sprezzature-publish-faq",
    help=(
        "Build the FAQ section a site is missing, from its own words: questions "
        "ranked by the declared CTAs, answers grounded in the site's pages, the "
        "questions it cannot answer yet, and where the section goes. With "
        "--audit, check existing FAQs and their FAQPage markup; --fix rewrites "
        "the markup from the visible FAQ."
    ),
    epilog=(
        "Examples:\n\n"
        "\b\n"
        "  sprezzature-publish-faq site/                      # draft, Markdown\n"
        "  sprezzature-publish-faq site/ --format html -o faq.html\n"
        "  sprezzature-publish-faq site/ --hints questions.csv --no-llm\n"
        "  sprezzature-publish-faq site/ --audit --fix\n"
    ),
)
@click.argument("target", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--ctas",
    "ctas_path",
    type=click.Path(path_type=Path),
    default=None,
    help="The declared CTAs. Default: ctas.yaml in the site folder, when present.",
)
@click.option(
    "--hints",
    "hints_path",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Real questions, one per line, optional ',count'. They rank first.",
)
@click.option("--top", default=8, show_default=True, help="Items in the section.")
@click.option("--lang", default="", help="en or fr. Default: the pages' own language.")
@click.option(
    "--llm/--no-llm",
    default=True,
    help="Draft answers with the local model; --no-llm extracts the site's own sentences.",
)
@click.option("--no-cache", is_flag=True, help="Ask the model again even for a stored draft.")
@click.option("--audit", is_flag=True, help="Check the site's existing FAQs instead of drafting.")
@click.option("--fix", is_flag=True, help="With --audit: rewrite FAQPage markup in .html pages.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["markdown", "html", "json"]),
    default="markdown",
    help="Output format. Default: markdown.",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the section here instead of standard output.",
)
def cli(
    target: Path,
    ctas_path: Path | None,
    hints_path: Path | None,
    top: int,
    lang: str,
    llm: bool,
    no_cache: bool,
    audit: bool,
    fix: bool,
    fmt: str,
    output: Path | None,
) -> int:
    """Draft, or audit, the site's FAQ."""
    pages = read_site(target)
    if not pages:
        click.echo(f"sprezzature-publish-faq: nothing to read under {target}", err=True)
        return 2
    site = target if target.is_dir() else target.parent

    if audit or fix:
        written = fix_faq(pages, site) if fix else []
        if written:
            pages = read_site(target)
            for path in written:
                click.echo(f"→ Rewrote the FAQPage markup of {path}", err=True)
        ctas_file = ctas_path or (site / "ctas.yaml")
        plan = load_ctas(ctas_file) if ctas_file.is_file() else None
        findings = audit_faq(pages, organization=plan.organization if plan else "")
        if fmt == "json":
            click.echo(render_json(findings))
        else:
            click.echo(render_findings(findings) if findings else "Every FAQ is consistent.")
        return 1 if any(f.severity == ERROR for f in findings) else 0

    ctas_file = ctas_path or (site / "ctas.yaml")
    plan = load_ctas(ctas_file) if ctas_file.is_file() else None
    if plan is None:
        click.echo(
            "No ctas.yaml: questions are ranked without the site's calls to action, and "
            "no answer ends on one. Run sprezzature-publish-cta first to declare them.",
            err=True,
        )
    hints = read_hints(hints_path) if hints_path else []
    chat = model_drafter(no_cache) if llm else None
    build = build_faq(pages, plan, hints, top=top, lang=lang, chat=chat)

    if fmt == "json":
        payload = asdict(build)
        payload["jsonld"] = faq_jsonld(build.items)
        text = json.dumps(payload, indent=2, ensure_ascii=False)
    elif fmt == "html":
        text = render_faq_html(build)
    else:
        text = render_faq_markdown(build)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
        click.echo(f"→ Wrote {output} — a draft: read every answer before publishing.", err=True)
    else:
        click.echo(text)
    if fmt != "json":
        report = render_report(build)
        if report:
            click.echo("\n" + report, err=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    return run_command(cli, argv)


if __name__ == "__main__":
    raise SystemExit(main())
