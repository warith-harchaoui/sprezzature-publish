#!/usr/bin/env python3
"""
cta
===

Ask a site what it is for, and check that every page says so.

Search, generative and answer engine optimisation all end on the same
question: once a reader arrives, what should they do? This tool makes that
question the first input of the whole run. The **declared** calls to action
— one primary, a few secondary, each with a label, a destination and the
reader it is for — live in ``ctas.yaml``. Everything downstream reads them:
which pages are *money pages*, which FAQ questions rank first, what a
deciding answer links to.

Declared, not guessed
---------------------
Detection here only does two things. It **pre-fills the question**, so the
author picks from what the site already offers instead of typing URLs; and
it **audits afterwards** which pages lack the CTA that was declared. It never
decides on the author's behalf what the site is selling.

How a candidate is scored
-------------------------
Rules only: no model, no screenshot. Each actionable element read by
:mod:`_content` gets a score, and every signal that contributed is kept as
evidence, so a surprising rank can be read rather than trusted.

1. **Destination**, read on the ``href`` only — never on the text, where
   "PayPal" matched 108 times on the calibration site, all of it prose.
   Booking, contact and purchase are *decide*; sign-up, download, install
   and endorsement are *evaluate*; everything else is *learn*.
2. **Prominence, relative to the page.** The heaviest style on a page, and
   among the heavy ones the rarest, is its primary button. That works the
   same for Tailwind utilities, Framer's inline styles and Bootstrap's
   ``btn-primary``, with no per-framework vocabulary to keep current.
3. **Position**: the hero (``<main>`` before its first ``<h2>``), and the
   header when the destination is a conversion — a booking button in a nav
   is the site-wide CTA, not navigation.
4. **An imperative lead verb**, English or French.
5. **Repetition**: the same destination on many pages is a site-wide CTA.

``data-cta`` in the author's own markup wins outright.

Exit code
---------
* 0 — no errors.
* 1 — a declared CTA appears on no page (``CTA001``).
* 2 — nothing to read.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import json
import math
import posixpath
import re
import sys
import urllib.parse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import click

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _click import run_command, sprezzature_command  # noqa: E402
from _content import Actionable, PageContent, decode_href, read_site  # noqa: E402
from audit_site import ERROR, WARNING, Finding, render_json  # noqa: E402

# ── Stages, and the destinations that name them ────────────────────────────

DECIDE, EVALUATE, LEARN = "decide", "evaluate", "learn"
STAGES: tuple[str, ...] = (DECIDE, EVALUATE, LEARN)

#: ``(kind, stage, weight, services, paths)``, first match wins. Read on the
#: decoded destination only. ``services`` match anywhere (a booking or
#: payment host is a conversion whoever links to it); ``paths`` match only a
#: destination on the site itself, because ``/book`` on someone else's host
#: is a book (tobyord.com/book), and ``/pricing`` there is their offer, not
#: this site's. A path matches on its last segment only: ``/demo`` is a
#: demo, ``/demo/screenshots`` is a folder of pictures. The weights rank a booking above a download above a star;
#: they do not need to be finer than that, because prominence and
#: repetition do the rest.
DESTINATIONS: tuple[tuple[str, str, int, re.Pattern[str] | None, re.Pattern[str] | None], ...] = (
    tuple(
        (
            kind,
            stage,
            weight,
            re.compile(services, re.I) if services else None,
            re.compile(rf"/({paths})(\.[a-z]+)?/?(\?|$)", re.I) if paths else None,
        )
        for kind, stage, weight, services, paths in (
            (
                "book",
                DECIDE,
                5,
                r"calendly\.com|(^|[/.])cal\.com/|tidycal\.com|savvycal\.com|zcal\.co|youcanbook\.me|"
                r"hubspot\.com/meetings|meetings\.hubspot|acuityscheduling",
                r"book|booking|rendez-vous|rdv|meet|se-rencontrer|book-a-demo|request-a-demo",
            ),
            (
                "buy",
                DECIDE,
                5,
                r"buy\.stripe\.com|checkout\.stripe|paypal\.(me|com)/|gumroad\.com|"
                r"lemonsqueezy\.com|paddle\.com|payhip\.com|ko-fi\.com|patreon\.com",
                r"pricing|tarifs?|prix|buy|acheter|checkout|cart|panier|order|commander|shop|"
                r"boutique|plans?",
            ),
            ("contact", DECIDE, 4, r"^mailto:|^tel:", r"contact|nous-contacter|contactez"),
            (
                "signup",
                EVALUATE,
                4,
                "",
                r"sign-?up|register|inscription|join|trial|essai|get-started|start|onboarding",
            ),
            (
                "subscribe",
                EVALUATE,
                3,
                r"substack\.com|mailchi\.mp|list-manage\.com|buttondown|convertkit|kit\.com|"
                r"beehiiv",
                # ``/newsletter``, not ``62_newsletter.html``: a page of
                # documentation about newsletters is not a sign-up.
                r"newsletter|subscribe|abonnement",
            ),
            (
                "install",
                EVALUATE,
                3,
                r"pypi\.org/project|npmjs\.com/package|marketplace\.visualstudio|"
                r"chrome\.google\.com/webstore|chromewebstore|apps\.apple\.com|play\.google\.com",
                "",
            ),
            (
                "download",
                EVALUATE,
                3,
                r"\.(zip|dmg|pkg|exe|msi|deb|rpm|apk|tar\.gz|tgz|whl|appimage)$|releases/latest",
                r"download|telecharger|télécharger",
            ),
            ("star", EVALUATE, 2, r"^https?://github\.com/[^/]+/[^/#?]+/?(stargazers)?$", ""),
        )
    )
)


def is_internal(dest: str) -> bool:
    """True for a destination on the site itself, as :func:`normalize` spells it."""
    return dest.startswith("/") and not dest.startswith("//")


#: Lead verbs, EN and FR. Matched on the first word of the label.
VERBS: frozenset[str] = frozenset(
    "get start try book buy order download install subscribe sign join contact talk "
    "schedule request explore see read discover learn give star watch apply register "
    "réserver reserver télécharger telecharger essayer contacter explorer découvrir "
    "decouvrir voir lire commander acheter installer rejoindre parler prendre demander "
    "s'inscrire inscrivez commencer démarrer demarrer écrire ecrire discuter".split()
)

#: Text that says an element changes the page rather than leaves it.
_UTILITY_TEXT = re.compile(
    r"^(skip to|aller au|passer au|menu|close|fermer|toggle|search|rechercher|"
    r"previous|next|précédent|suivant|back to top|haut de page|copy|copier)\b",
    re.I,
)
_LANG_TEXT = re.compile(
    r"^([a-z]{2}(-[a-z]{2})?|[\U0001F1E6-\U0001F1FF]{2}|english|français)$", re.I
)


@dataclass
class Occurrence:
    """One scored actionable element on one page."""

    page: str
    line: int
    text: str
    dest: str
    kind: str
    stage: str
    score: float
    landmark: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    """One destination, aggregated over every page that offers it."""

    label: str
    url: str
    kind: str
    stage: str
    score: float
    pages: list[str]
    evidence: list[str]


@dataclass
class CtaSpec:
    """One declared call to action."""

    label: str
    url: str
    audience: str = ""
    stage: str = ""
    primary: bool = False

    @property
    def is_command(self) -> bool:
        """True for an install command, which has no URL to follow."""
        return not re.match(r"^([a-z][a-z0-9+.-]*:|/|\.\.?/|#)", self.url, re.I) and " " in self.url


@dataclass
class CtaPlan:
    """What ``ctas.yaml`` declares: the offer, the entity, the CTAs."""

    offer: str = ""
    organization: str = ""
    ctas: list[CtaSpec] = field(default_factory=list)

    @property
    def primary(self) -> CtaSpec | None:
        """The one primary CTA, or the first one when none is marked."""
        return next((c for c in self.ctas if c.primary), self.ctas[0] if self.ctas else None)


# ── Normalising a destination ──────────────────────────────────────────────

_TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|mc_|ref$|ref_src$)", re.I)


def normalize(href: str, page_path: str = "", hosts: frozenset[str] = frozenset()) -> str:
    """One spelling per destination, so repetition can be counted.

    Entities and percent-encoding decoded, tracking parameters and the
    fragment dropped, host lower-cased, trailing slash removed, and a
    relative link resolved against the page it sits on into a site path
    (``/figures.html``), so ``figures.html`` and ``../figures.html`` count
    as one destination. An absolute link to one of ``hosts`` (the site's
    own) is spelled as its path too, so ``https://example.org/book`` is
    internal like ``/book``.
    """
    value = decode_href(href)
    if not value:
        return ""
    if value.lower().startswith(("mailto:", "tel:")):
        scheme, _, rest = value.partition(":")
        return f"{scheme.lower()}:{rest.split('?')[0].strip().lower()}"
    parts = urllib.parse.urlsplit(value)
    query = urllib.parse.urlencode(
        [(k, v) for k, v in urllib.parse.parse_qsl(parts.query) if not _TRACKING.match(k)]
    )
    if parts.scheme in {"http", "https"}:
        path = parts.path.rstrip("/") or ""
        if _bare_host(parts.netloc) in hosts:
            return (path or "/") + (f"?{query}" if query else "")
        out = f"{parts.scheme}://{parts.netloc.lower()}{path}"
        return out + (f"?{query}" if query else "")
    if parts.scheme or value.startswith("//"):
        return value
    if not parts.path:  # a same-page fragment
        return "#" + parts.fragment if parts.fragment else ""
    base = posixpath.dirname("/" + page_path.lstrip("/"))
    joined = posixpath.normpath(posixpath.join(base, parts.path))
    for index in ("/index.html", "/index.php", "/index.htm"):
        if joined.endswith(index):
            joined = joined[: -len(index)] or "/"
    return (joined.rstrip("/") or "/") + (f"?{query}" if query else "")


def _bare_host(netloc: str) -> str:
    host = netloc.lower().rsplit("@", 1)[-1].split(":", 1)[0]
    return host[4:] if host.startswith("www.") else host


def site_hosts(pages: list[PageContent]) -> frozenset[str]:
    """The site's own hosts, read from the canonical links its pages declare."""
    return frozenset(
        host
        for host in (_bare_host(urllib.parse.urlsplit(p.canonical).netloc) for p in pages)
        if host
    )


def classify(dest: str, act: Actionable | None = None) -> tuple[str, str, int]:
    """``(kind, stage, weight)`` for a normalised destination."""
    if act is not None:
        if act.kind == "install":
            return "install", EVALUATE, 3
        if act.kind == "form":
            return "subscribe", EVALUATE, 3
        if "download" in act.attrs:
            return "download", EVALUATE, 3
    internal = is_internal(dest)
    for kind, stage, weight, services, paths in DESTINATIONS:
        if (services and services.search(dest)) or (internal and paths and paths.search(dest)):
            return kind, stage, weight
    return "page", LEARN, 0


# ── Prominence, relative to the page ───────────────────────────────────────

_NEUTRAL_BG = re.compile(
    r"^bg-(white|transparent|inherit|current|none|(neutral|gray|slate|zinc|stone)-(50|100))$"
)


def style_weight(act: Actionable) -> tuple[int, str]:
    """How heavy an element looks, 0 to 3, and a signature of that look.

    3 = filled (a strong background), 2 = outlined button, 1 = padded and
    rounded chip, 0 = a text link. Only unprefixed utility classes count:
    ``hover:bg-neutral-100`` is what every nav link does on hover, not what
    a button looks like at rest.
    """
    tokens = [t for t in act.classes.split() if ":" not in t]
    style = act.style.lower().replace(" ", "")
    framer = act.attrs.get("data-framer-name", "").lower()
    filled = (
        any(t.startswith("bg-") and not _NEUTRAL_BG.match(t) for t in tokens)
        or any(re.fullmatch(r"(btn|button)-(primary|success|danger|dark|cta)", t) for t in tokens)
        or "cta" in tokens
        or "primary" in framer
        or bool(
            re.search(r"background(-color)?:(?!rgba\(0,0,0,0\)|transparent|none|inherit)", style)
        )
    )
    padded = any(re.fullmatch(r"p[xy]?-([2-9]|1\d)(\.5)?", t) for t in tokens) or "padding" in style
    outlined = (
        any(t == "border" or re.fullmatch(r"border-[0-9]", t) for t in tokens)
        or any(t in {"btn", "button"} or t.startswith("btn-outline") for t in tokens)
        # ``border:`` or ``border-width:``, not ``border-bottom-left-radius:``.
        or bool(re.search(r"border(-width|-style)?:(?!0|none)", style))
    )
    rounded = any(t.startswith("rounded") for t in tokens) or "radius" in style
    text_white = "text-white" in tokens
    if filled and (padded or rounded or text_white or framer):
        weight = 3
    elif outlined and (padded or rounded):
        weight = 2
    elif padded and rounded:
        weight = 1
    else:
        weight = 0
    signature = " ".join(
        sorted(t for t in tokens if re.match(r"(bg|border|rounded|p[xy]?|text-white|btn)", t))
    )
    return weight, signature or framer or style[:40]


def is_utility(act: Actionable, dest: str) -> bool:
    """Skip links, language and theme switchers, toggles, same-page jumps."""
    text = act.text.strip()
    attrs = act.attrs
    if dest.lower().startswith("javascript:"):
        return True
    if _UTILITY_TEXT.match(text) or "hreflang" in attrs:
        return True
    if _LANG_TEXT.match(text) and act.landmark in {"nav", "header", ""}:
        return True
    label = " ".join(
        (attrs.get("aria-label", ""), attrs.get("id", ""), attrs.get("title", ""))
    ).lower()
    if any(word in label for word in ("theme", "dark", "mode", "langue", "language", "menu")):
        return True
    if act.kind == "button" and not dest and not act.attrs.get("type") == "submit":
        # A button that goes nowhere toggles something on the page.
        return "data-cta" not in attrs
    return False


def score_page(page: PageContent, hosts: frozenset[str] = frozenset()) -> list[Occurrence]:
    """Score every actionable element of one page.

    Parameters
    ----------
    page : PageContent
        One file read by :mod:`_content`.
    hosts : frozenset of str
        The site's own hosts (:func:`site_hosts`).

    Returns
    -------
    list of Occurrence
        One per element that is not a page utility, with its evidence.
    """
    rows: list[tuple[Actionable, str, int, str]] = []
    for act in page.actionables:
        dest = act.text if act.kind == "install" else normalize(act.href, page.path, hosts)
        if act.kind != "install" and is_utility(act, dest):
            continue
        weight, signature = style_weight(act)
        rows.append((act, dest, weight, signature))

    # The rarest of the heaviest looks on this page is its primary button.
    heaviest = max((w for _, _, w, _ in rows), default=0)
    looks = Counter(sig for _, _, w, sig in rows if w == heaviest and heaviest >= 2)
    rarest = min(looks.values()) if looks else 0

    out: list[Occurrence] = []
    for act, dest, weight, signature in rows:
        kind, stage, dest_weight = classify(dest, act)
        evidence: list[str] = []
        score = 2.0 * dest_weight
        if dest_weight:
            evidence.append(f"destination: {kind} ({stage})")
        if dest.startswith("#"):
            # A jump within the page: a CTA only when styled as one.
            score -= 2
            evidence.append("same-page anchor")
        score += weight
        if weight:
            evidence.append(f"style weight {weight}/3")
        if weight == heaviest >= 2 and looks.get(signature) == rarest:
            score += 2
            evidence.append("rarest heavy style on the page")
        if act.hero:
            score += 2
            evidence.append("in the hero")
        elif act.landmark in {"header", "nav"} and (dest_weight >= 4 or weight == 3):
            score += 1
            evidence.append(f"in the {act.landmark}, styled or converting")
        first = re.split(r"[\s→⭐️]+", act.text.lower().strip(), maxsplit=1)[0] if act.text else ""
        if first in VERBS:
            score += 1
            evidence.append(f"imperative verb '{first}'")
        if "data-cta" in act.attrs:
            score += 20
            evidence.append("data-cta in the markup")
        if act.kind == "data":
            score -= 1
            evidence.append(f"from data ({page.fmt})")
        out.append(
            Occurrence(
                page=page.path,
                line=act.line,
                text=act.text,
                dest=dest,
                kind=kind,
                stage=stage,
                score=score,
                landmark=act.landmark,
                evidence=evidence,
            )
        )
    return out


#: An occurrence at or above this score is called a CTA. Calibrated on the
#: hand-labelled fixtures in ``tests/fixtures/cta``.
THRESHOLD: float = 5.0


def detect_ctas(pages: list[PageContent], *, threshold: float = THRESHOLD) -> list[Candidate]:
    """Rank the site's calls to action, one candidate per destination.

    Parameters
    ----------
    pages : list of PageContent
        The site, as :func:`_content.read_site` returns it.
    threshold : float
        Occurrence score at which an element counts as a CTA.

    Returns
    -------
    list of Candidate
        Highest score first. A candidate's score is its best occurrence plus
        a repetition bonus that grows with the log of the pages offering it.
    """
    by_dest: dict[str, list[Occurrence]] = defaultdict(list)
    hosts = site_hosts(pages)
    for page in pages:
        for occ in score_page(page, hosts):
            if occ.score >= threshold and occ.dest:
                by_dest[occ.dest].append(occ)

    out: list[Candidate] = []
    for dest, occs in by_dest.items():
        best = max(occs, key=lambda o: o.score)
        pages_with = sorted({o.page for o in occs})
        labels = Counter(o.text for o in occs if o.text)
        label = labels.most_common(1)[0][0] if labels else _label_from_dest(dest)
        bonus = math.log2(1 + len(pages_with))
        evidence = list(best.evidence)
        if len(pages_with) > 1:
            evidence.append(f"on {len(pages_with)} pages")
        out.append(
            Candidate(
                label=label,
                url=dest,
                kind=best.kind,
                stage=best.stage,
                score=round(best.score + bonus, 2),
                pages=pages_with,
                evidence=evidence,
            )
        )
    out.sort(key=lambda c: (-c.score, c.url))
    return out


def _label_from_dest(dest: str) -> str:
    """Words for an element that has none: the host, or the path's last part."""
    parts = urllib.parse.urlsplit(dest)
    return parts.netloc or posixpath.basename(parts.path) or dest


# ── ctas.yaml ──────────────────────────────────────────────────────────────


def load_ctas(path: Path) -> CtaPlan:
    """Read ``ctas.yaml`` (or the same structure in JSON).

    Parameters
    ----------
    path : Path
        The file. Its shape::

            offer: One sentence saying what is offered.
            organization: The one name used everywhere.
            primary: {label: ..., url: ..., audience: ..., stage: decide}
            secondary:
              - {label: ..., url: ..., audience: ..., stage: evaluate}

    Returns
    -------
    CtaPlan
        The declared plan. Stage is filled from the destination when the
        file leaves it out.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        import yaml

        data = yaml.safe_load(text) or {}
    return plan_from_dict(data)


def plan_from_dict(data: dict[str, Any]) -> CtaPlan:
    """Build a :class:`CtaPlan` from the parsed file or an API payload."""

    def spec(raw: Any, primary: bool) -> CtaSpec | None:
        if not isinstance(raw, dict) or not raw.get("url"):
            return None
        url = str(raw["url"]).strip()
        stage = str(raw.get("stage", "")).strip().lower()
        if stage not in STAGES:
            stage = classify(url if " " in url else normalize(url))[1]
            if " " in url:  # an install command
                stage = EVALUATE
        return CtaSpec(
            label=str(raw.get("label", "")).strip() or _label_from_dest(url),
            url=url,
            audience=str(raw.get("audience", "")).strip(),
            stage=stage,
            primary=primary,
        )

    ctas = [s for s in [spec(data.get("primary"), True)] if s]
    for raw in data.get("secondary") or []:
        s = spec(raw, False)
        if s:
            ctas.append(s)
    return CtaPlan(
        offer=str(data.get("offer", "") or "").strip(),
        organization=str(data.get("organization", "") or "").strip(),
        ctas=ctas,
    )


def _q(value: str) -> str:
    """A YAML scalar that survives any text: JSON strings are valid YAML."""
    return json.dumps(value, ensure_ascii=False)


def render_ctas_yaml(plan: CtaPlan, candidates: list[Candidate] | None = None) -> str:
    """Write a plan as ``ctas.yaml``, with the detected evidence as comments.

    Hand-emitted rather than ``yaml.dump``-ed so the comments survive: the
    author edits this file, and the evidence is what tells them why each
    line is there.
    """
    evidence = {c.url: c for c in candidates or []}

    def block(spec: CtaSpec, indent: str, dash: str) -> list[str]:
        lines = []
        found = evidence.get(spec.url) or evidence.get(normalize(spec.url))
        if found:
            lines.append(f"{indent}# detected: score {found.score}, {', '.join(found.evidence)}")
        lines += [
            f"{indent}{dash}label: {_q(spec.label)}",
            f"{indent}  url: {_q(spec.url)}" if dash else f"{indent}url: {_q(spec.url)}",
            f"{indent}  audience: {_q(spec.audience)}"
            if dash
            else f"{indent}audience: {_q(spec.audience)}",
            f"{indent}  stage: {spec.stage}" if dash else f"{indent}stage: {spec.stage}",
        ]
        return lines

    out = [
        "# ctas.yaml — what this site asks its readers to do.",
        "# Read by sprezzature-publish cta, faq and findable. Edit freely: this",
        "# file wins over anything detected. Stages: decide / evaluate / learn.",
        "",
        f"offer: {_q(plan.offer)}",
        f"organization: {_q(plan.organization)}",
    ]
    primary = plan.primary
    if primary:
        out += ["", "primary:", *block(primary, "  ", "")]
    rest = [c for c in plan.ctas if c is not primary]
    if rest:
        out += ["", "secondary:"]
        for spec in rest:
            out += block(spec, "  ", "- ")
    return "\n".join(out) + "\n"


def draft_plan(candidates: list[Candidate], *, secondary: int = 2) -> CtaPlan:
    """A plan pre-filled from detection: the top candidate is primary.

    Only a draft. Detection cannot know whether the site is there to sell a
    call, a licence or a download, which is why the CLI asks.
    """
    ranked = [c for c in candidates if not c.url.startswith("#")] or candidates
    ctas = [
        CtaSpec(c.label, c.url, "", c.stage, primary=(i == 0))
        for i, c in enumerate(ranked[: 1 + secondary])
    ]
    return CtaPlan(ctas=ctas)


# ── Which pages carry which CTA ────────────────────────────────────────────

#: Folders whose files are pieces of a page rather than pages.
PARTIAL_DIRS: frozenset[str] = frozenset(
    {
        "layouts",
        "layout",
        "partials",
        "_partials",
        "includes",
        "_includes",
        "templates",
        "components",
        "inc",
        "views/partials",
    }
)


def partials(pages: list[PageContent]) -> set[str]:
    """Files that are included into other pages, or live in a partials folder."""
    names = {Path(i).name for p in pages for i in p.includes}
    return {
        p.path
        for p in pages
        if Path(p.path).name in names
        or any(part in PARTIAL_DIRS for part in Path(p.path).parts[:-1])
    }


def offers(page: PageContent, spec: CtaSpec) -> bool:
    """True when this file itself offers the declared CTA."""
    if spec.is_command:
        wanted = " ".join(spec.url.split()).lower()
        return (
            any(
                a.kind == "install" and " ".join(a.text.split()).lower().startswith(wanted)
                for a in page.actionables
            )
            or wanted in page.source.lower()
        )
    target = normalize(spec.url)
    return any(normalize(a.href, page.path) == target for a in page.actionables if a.href)


def carriers(pages: list[PageContent], plan: CtaPlan) -> dict[str, set[str]]:
    """Map each page path to the labels of the declared CTAs it carries.

    A CTA in a shared partial (a layout, a nav include) is carried by every
    page the shell renders: PHP and Markdown pages. A static ``.html`` file
    is self-contained, so it carries only what it holds.
    """
    shell = partials(pages)
    shared: set[str] = set()
    out: dict[str, set[str]] = {}
    for page in pages:
        held = {spec.label for spec in plan.ctas if offers(page, spec)}
        out[page.path] = held
        if page.path in shell:
            shared |= held
    for page in pages:
        if page.path not in shell and page.fmt in {"php", "md"}:
            out[page.path] |= shared
    return out


def money_pages(pages: list[PageContent], plan: CtaPlan) -> list[str]:
    """Pages that carry a declared CTA, plus the CTA's own landing page.

    Shell partials are excluded: they are pieces of every page, not a page
    a reader lands on.
    """
    shell = partials(pages)
    held = carriers(pages, plan)
    # A page carrying only what the shell gives it is every page; it is a
    # money page only when it holds a CTA itself.
    own = {p.path for p in pages if any(offers(p, s) for s in plan.ctas)}
    landing: set[str] = set()
    for spec in plan.ctas:
        dest = normalize(spec.url)
        if dest.startswith("/"):
            for page in pages:
                url = normalize(page.path)
                if (
                    url in {dest, dest + ".html", dest + ".php"}
                    or normalize("/" + page.path) == dest
                ):
                    landing.add(page.path)
    out = {p for p in own | landing if p not in shell and held.get(p) is not None}
    return sorted(out, key=lambda p: (p not in landing, p))


def audit_ctas(pages: list[PageContent], plan: CtaPlan) -> list[Finding]:
    """Check the site against its declared CTAs.

    ``CTA001`` (error): a declared CTA appears nowhere. ``CTA002`` (warning):
    a page a reader lands on offers none of the declared CTAs — on the
    calibration site, every blog post a reader reaches from an answer engine
    offered only an e-mail address, never the booking link.
    """
    findings: list[Finding] = []
    if not plan.ctas:
        return [
            Finding(
                "ctas.yaml",
                0,
                "CTA000",
                ERROR,
                "No call to action is declared, so nothing can be audited against one.",
                "sprezzature-publish-cta <site> --write ctas.yaml",
            )
        ]
    held = carriers(pages, plan)
    shell = partials(pages)
    for spec in plan.ctas:
        if not any(spec.label in labels for labels in held.values()):
            findings.append(
                Finding(
                    "ctas.yaml",
                    0,
                    "CTA001",
                    ERROR,
                    f"Declared CTA '{spec.label}' ({spec.url}) appears on no page.",
                    "add it to the pages it is for, or correct its url in ctas.yaml",
                )
            )
    primary = plan.primary
    for page in pages:
        if not page.is_page or page.path in shell or held.get(page.path):
            continue
        if not page.passages:  # a redirect stub, an empty shell
            continue
        findings.append(
            Finding(
                page.path,
                0,
                "CTA002",
                WARNING,
                "This page offers none of the declared calls to action"
                + (f"; the primary is '{primary.label}'." if primary else "."),
                f"link {primary.url} from this page" if primary else "",
            )
        )
    return findings


# ── Asking the author ──────────────────────────────────────────────────────


def ask_plan(candidates: list[Candidate], *, top: int = 8) -> CtaPlan:
    """Ask for the primary and secondary CTAs, offering what was detected.

    The author picks numbers, or types a URL (or an install command) when
    the site does not offer the CTA yet — which is a finding in itself.
    """
    shown = candidates[:top]
    click.echo("Calls to action found on the site, best first:\n")
    for i, c in enumerate(shown, 1):
        click.echo(f"  {i}. {c.label}  →  {c.url}  [{c.stage}, {len(c.pages)} page(s)]")
    click.echo("")

    def pick(prompt: str, default: str) -> CtaSpec | None:
        answer = click.prompt(prompt, default=default, show_default=bool(default)).strip()
        if not answer or answer == "-":
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(shown):
            c = shown[int(answer) - 1]
            label = click.prompt("  label", default=c.label)
            return CtaSpec(label, c.url, "", c.stage)
        label = click.prompt("  label")
        return CtaSpec(label, answer, "", classify(normalize(answer))[1])

    primary = pick("Primary CTA (number, or a URL / install command)", "1" if shown else "")
    if primary is None:
        return CtaPlan()
    primary.primary = True
    primary.audience = click.prompt("  who is it for", default="").strip()
    ctas = [primary]
    raw = click.prompt(
        "Secondary CTAs (numbers separated by commas, '-' for none)",
        default="-",
    ).strip()
    for token in re.split(r"[,\s]+", raw):
        if token.isdigit() and 1 <= int(token) <= len(shown):
            c = shown[int(token) - 1]
            if c.url != primary.url:
                ctas.append(CtaSpec(c.label, c.url, "", c.stage))
    offer = click.prompt("In one sentence, what is offered", default="").strip()
    organization = click.prompt("The one name of the organisation or product", default="").strip()
    return CtaPlan(offer=offer, organization=organization, ctas=ctas)


# ── Reporting ──────────────────────────────────────────────────────────────


def families(candidates: list[Candidate], *, at_least: int = 3) -> list[Candidate]:
    """Fold files of one kind in one folder into one line, for display.

    A gallery that offers one ``.zip`` per page would otherwise fill the
    whole inventory with its kits. ``/kits/a.zip``, ``/kits/b.zip`` and
    ``/kits/c.zip`` become ``/kits/*.zip`` with their best score; fewer than
    ``at_least`` siblings stay as they are. The ranking itself is untouched.
    """
    groups: dict[tuple[str, str], list[Candidate]] = defaultdict(list)
    for c in candidates:
        folder, name = posixpath.split(c.url)
        ext = posixpath.splitext(name)[1]
        key = (c.kind, f"{folder}/*{ext}") if is_internal(c.url) and ext else (c.kind, c.url)
        groups[key].append(c)
    out: list[Candidate] = []
    for (_, pattern), members in groups.items():
        if len(members) < at_least:
            out.extend(members)
            continue
        best = max(members, key=lambda m: m.score)
        out.append(
            Candidate(
                label=best.label,
                url=pattern,
                kind=best.kind,
                stage=best.stage,
                score=best.score,
                pages=sorted({p for m in members for p in m.pages}),
                evidence=[*best.evidence, f"{len(members)} files like it"],
            )
        )
    out.sort(key=lambda c: (-c.score, c.url))
    return out


def render_candidates(candidates: list[Candidate], top: int) -> str:
    """The ranked inventory, one candidate per block with its evidence."""
    lines = []
    for i, c in enumerate(families(candidates)[:top], 1):
        lines.append(f"{i:>2}. {c.score:>5}  {c.label}  →  {c.url}")
        lines.append(f"       {c.kind}, {c.stage}; {'; '.join(c.evidence)}")
    return "\n".join(lines) if lines else "No call to action detected."


def render_findings(findings: list[Finding], per_rule: int = 8) -> str:
    """Findings as text, at most ``per_rule`` lines per rule.

    A site of a thousand pages raises the same warning on hundreds of them;
    the full list is what ``--format json`` is for.
    """
    lines: list[str] = []
    shown: Counter[str] = Counter()
    total = Counter(f.rule for f in findings)
    for f in findings:
        shown[f.rule] += 1
        if shown[f.rule] > per_rule:
            continue
        where = f"{f.path}:{f.line}" if f.line else f.path
        lines.append(f"{where}: {f.severity}: {f.rule}: {f.message}")
        if f.remedy:
            lines.append(f"    → {f.remedy}")
        if shown[f.rule] == per_rule and total[f.rule] > per_rule:
            lines.append(f"    … and {total[f.rule] - per_rule} more {f.rule} (--format json)")
    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────


@sprezzature_command(
    "sprezzature-publish-cta",
    help=(
        "Find the site's calls to action, ask which ones it exists for, and "
        "write them to ctas.yaml; then check every page against them. Reads "
        "HTML, PHP, Markdown, JSON and YAML. Rules only, no model."
    ),
    epilog=(
        "Examples:\n"
        "  sprezzature-publish-cta site/                    # detect, then ask\n"
        "  sprezzature-publish-cta site/ --write ctas.yaml --no-ask\n"
        "  sprezzature-publish-cta site/ --ctas ctas.yaml   # audit the pages\n"
        "  sprezzature-publish-cta site/ --format json\n"
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
    "--write",
    "write_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Write the plan (asked, or drafted with --no-ask) to this file.",
)
@click.option(
    "--ask/--no-ask",
    default=None,
    help="Ask for the CTAs when none are declared. Default: ask when the terminal is interactive.",
)
@click.option("--top", default=8, show_default=True, help="Candidates to list.")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format. Default: text.",
)
def cli(
    target: Path,
    ctas_path: Path | None,
    write_path: Path | None,
    ask: bool | None,
    top: int,
    fmt: str,
) -> int:
    """Detect, ask, and audit the site's calls to action."""
    pages = read_site(target)
    if not pages:
        click.echo(f"sprezzature-publish-cta: nothing to read under {target}", err=True)
        return 2
    candidates = detect_ctas(pages)

    site = target if target.is_dir() else target.parent
    path = ctas_path or (site / "ctas.yaml")
    plan: CtaPlan | None = load_ctas(path) if path.is_file() else None
    if plan is None:
        interactive = sys.stdin.isatty() and fmt == "text"
        if ask if ask is not None else interactive:
            plan = ask_plan(candidates, top=top)
        elif write_path:
            plan = draft_plan(candidates)
        if plan is not None and write_path:
            write_path.write_text(render_ctas_yaml(plan, candidates), encoding="utf-8")
            click.echo(f"→ Wrote {write_path} — review it: the file wins over detection.", err=True)

    findings = audit_ctas(pages, plan) if plan and plan.ctas else []
    if fmt == "json":
        click.echo(
            json.dumps(
                {
                    "candidates": [asdict(c) for c in candidates[:top]],
                    "declared": [asdict(c) for c in plan.ctas] if plan else [],
                    "money_pages": money_pages(pages, plan) if plan else [],
                    "findings": json.loads(render_json(findings)),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        click.echo(render_candidates(candidates, top))
        if plan is None:
            click.echo(
                "\nNo ctas.yaml yet. Run again in a terminal to be asked, or pass "
                "--write ctas.yaml --no-ask for a draft to edit."
            )
        elif findings:
            click.echo("\n" + render_findings(findings))
        else:
            click.echo("\nEvery page offers a declared call to action.")
    return 1 if any(f.severity == ERROR for f in findings) else 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point; returns a process exit code."""
    return run_command(cli, argv)


if __name__ == "__main__":
    raise SystemExit(main())
