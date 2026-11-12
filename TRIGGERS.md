# Triggers

When to turn Markdown into a site, and what to call.

This file is written for an agent: a Claude Code or OpenCode skill, an MCP
(Model Context Protocol, the protocol through which AI agents call tools in English)
host, anything choosing a tool on someone's behalf. The skill itself ships
inside the package, at `sprezzature_publish/skill/`, and
`sprezzature-publish-skill --install` copies it into `~/.claude/skills`
(`--agent opencode` for `~/.opencode/skills`). Humans are welcome, but
the routing rules below are the point.

---

## The generalisation, stated once

> **You are holding Markdown that has to become something somebody else can
> find.** Nobody names this package. They say "put this online", "why does
> this look so bad when I share the link", "I need favicons", "make this
> readable for a wider audience", « mets ça en ligne », « il faut que Google
> le voie ». The shared shape is a document on one side and a reader who is
> not in the room on the other.

The second trigger is silent, and is the one to remember: **you just wrote
Markdown that will be published.** A README, a docs page, a release note.
Lint it before it renders, the same way you would lint source.

The third has no Markdown anywhere in it, and it is the commonest of the
three: **a site already exists and has to get better.** One somebody else
built, one built here years ago, a WordPress export, a landing page a
designer handed over. There is no source to go back to — only HTML. That is
`sprezzature-publish-audit`, which reads what is there and repairs what can
be derived. Never answer "I would need the Markdown" to this question: the
tool does not want any.

The fourth is the one every other request is secretly about: **somebody
wants a reader to do something.** Book a call, buy, install, sign up,
download, read on. SEO (search engine optimization) is getting a page onto the
first page of Google results; GEO (generative engine optimization) is being
the source ChatGPT quotes when somebody asks it; AEO (answer engine
optimization) is being the answer a search engine prints above the links.
Each ends on a CTA (call to action: the one button the site wants clicked,
such as "Book a demo"). They say "my site doesn't sell", "nobody contacts me",
"what should people do on this page", "SEO", "GEO", "AEO", "show up in
ChatGPT answers", "write me a FAQ", « mon site ne convertit pas », « il me
faut une FAQ ». Route on the closed vocabulary, not on the phrasing:

| The reader should… | Stage | Where it goes |
|---|---|---|
| book, buy, contact, request a quote | **decide** | `cta`, then `faq`, then `findable` |
| install, download, sign up, try, subscribe | **evaluate** | same |
| read, explore, understand | **learn** | same |

The order is fixed, and the first step is a **question to the user**: which
one action is this site for, and which secondary ones? Detection
(`sprezzature-publish-cta`) offers what the site already links to, so the
user picks instead of typing; it never decides for them. Everything after
reads the answer from `ctas.yaml`: which pages are money pages, which FAQ
questions rank first, what each deciding answer links to, which findings
are errors.

---

## Which tool, and which neighbour

Four different questions get asked about the same page. Send each to the
right place: they do not substitute for one another.

| The question | Package | Where to start |
|---|---|---|
| **Can it be found?** meta tags, feeds, sitemap, llms.txt | sprezzature-publish | `sprezzature-publish-lint`, then `-indexes` |
| **Can *this existing site* be found?** no Markdown behind it | sprezzature-publish | `sprezzature-publish-audit <dir\|url>`, then `--fix` |
| **Does it lead readers where it should?** SEO + GEO + AEO, CTA first | sprezzature-publish | `sprezzature-publish-cta`, `-faq`, `-findable` |
| **How many CTAs compete on one screen?** choice overload | sprezzature-ux-laws | Hick's law |
| **Is it accessible?** missing alt, unlabelled inputs, heading order | sprezzature-accessibility | `lint_html` |
| **Is it legible?** contrast, colour-blind safety | sprezzature-colors | `check_contrast` |
| **Is the speech already recorded?** sound in, timed text out | sprezzature-audio | `sprezzature-audio-captions` |

The last row is the one that gets mis-routed. This package turns text into
sound and binds it to a page. Turning sound into text is the other
direction, and it lives next door.

---

## The thirteen tools, and the plain-language request each answers

You do not need to name a tool to route: `make-site <tool>` and
`sprezzature-publish <tool>` both resolve against one table. This list is
for reading a request back as a tool.

| Tool | The request it answers |
|---|---|
| `cta` | "what should people do on my site", "nobody books a call", "which button matters", "ctas.yaml" |
| `faq` | "write me a FAQ", "answer engine optimisation", "AEO", "show up in ChatGPT / AI Overviews answers", "FAQPage schema" |
| `findable` | "SEO + GEO + AEO audit", "why don't AI answers cite us", "is my pricing page indexable", "nosnippet" |
| `audit` | "audit this existing site", "this live URL", "fix the head tags", no Markdown anywhere |
| `lint` | "check my Markdown", "is this doc clean", a pre-commit gate |
| `html` | "make pages out of this", "typeset the math" (a diagram is redrawn with `sprezzature-figures`; the lint flags each Mermaid block as `MMD001`) |
| `icons` | "I need favicons", "app icons", "PWA (progressive web app, a site you install on a phone's home screen like an app) icons", "I only have a logo" |
| `indexes` | "SEO", "sitemap", "robots.txt", "llms.txt", "RSS (Really Simple Syndication, a feed a reader app follows)", "why doesn't Google see it" |
| `meta` | "the link preview looks wrong", "OG (Open Graph, the tags that decide a shared link's preview card) card", "Twitter card", "Schema.org" |
| `plain` | "simplify this", "write it for a wider audience", "rewrite at grade 8" |
| `changelog` | "a feed from my CHANGELOG", "one feed for all my repositories' releases" |
| `narrate` | "read this post aloud", "podcast my blog", "text to speech" |
| `readalong` | "highlight the sentence being spoken", "follow along while it reads" |

---

## What to call, on every surface

| Job | Command line | MCP tool |
|---|---|---|
| Declare and check the CTAs | `sprezzature-publish-cta` | `find_calls_to_action` |
| Build or audit the FAQ | `sprezzature-publish-faq` | `build_faq` |
| Joint SEO + GEO + AEO report | `sprezzature-publish-findable` | `report_findability` |
| Audit an existing page | `sprezzature-publish-audit` | `audit_site` |
| Lint the Markdown | `sprezzature-publish-lint` | `lint_markdown` |
| Render pages | `sprezzature-publish-html` | `render_markdown` |
| Plain-language rewrite | `sprezzature-publish-plain` | `rewrite_plainly` |
| Icon set | `sprezzature-publish-icons` | none, see below |
| Crawler and model indexes | `sprezzature-publish-indexes` | none, see below |
| Meta tags | `sprezzature-publish-meta` | none, see below |
| Narrate a post | `sprezzature-publish-narrate` | none, see below |
| Bind the narration | `sprezzature-publish-readalong` | none, see below |
| Changelogs as one feed | `sprezzature-publish-changelog` | none, see below |
| Install or refresh this skill | `sprezzature-publish-skill --install` | none: it writes under your home directory |

Seven of the thirteen cross a network boundary cleanly, because they are
text in and text out, and those seven are the MCP tools, with `health`
beside them: the site's pages go in as `[{path, content}]`, the CTAs as a
parameter. The other six stay commands. Five write files keyed by filename:
an icon set, a sitemap beside the pages it indexes, a feed, an audio track
and its cues, and offering those over MCP would mean inventing a download
protocol. The sixth, `meta`, prints JSON (JavaScript Object Notation, a text format in which programs store data as named fields) for one page from a local model.
Call them with Bash.

Over MCP the CTAs are a parameter, and their absence comes back as a
`note` that says to ask. Ask: never fill `ctas` from the candidates on your
own. The FAQ is a draft for the author to read (`draft: true`), and a
question the pages cannot answer comes back under `gaps`, not answered.

Start with the lint either way. It needs only click and the standard
library, so it runs where nothing else will, and a document that fails it will not render well
anyway.

---

## What this cannot see, and say so when you report

It reads documents, and it writes files. It cannot open a browser, so it
says nothing about how a page behaves once loaded: no runtime DOM (Document Object Model, the live tree of elements a browser builds from the page), no
contrast measured on rendered pixels, no keyboard trace. Those belong to
the neighbours in the table above.

It also does not rank anything. `FAQPage` markup earns no rich result on
Google since 2026-05-07, and nothing here says it does: the FAQ is built for
its visible text, the one thing answer engines read. Emitting `sitemap.xml` and `llms.txt` makes
a site legible to crawlers and to language models; whether anybody arrives
is not something this package knows or should claim.

Report output as output, never as a verdict. "The lint found nothing" means
exactly that, not "this documentation is good".

---

## File patterns

`*.md` routes here when publication is the concern, and, per the
generalisation above, when such a file was just written. `ctas.yaml` always
routes here. `*.html`, `*.php` and a site's `*.json` / `*.yaml` data route
here for `audit`, `cta`, `faq`, `findable`, `meta`, `narrate` and
`readalong`; for anything about how the
markup behaves, route to sprezzature-accessibility or sprezzature-ux-laws.
