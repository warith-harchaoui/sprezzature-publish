# sprezzature-publish

[🇫🇷](https://github.com/warith-harchaoui/sprezzature-publish/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/sprezzature-publish/blob/main/README.md)

A folder of Markdown becomes a site somebody can find.

Point it at a `README.md` and a `docs/` folder and it emits pages, the meta
tags that make them shareable, a favicon and app-icon set from one logo, the
indexes crawlers and language models look for — `robots.txt`, `sitemap.xml`,
`llms.txt`, an Atom feed, `humans.txt` — and, when asked, a narrated audio
track with a read-along that highlights the sentence being spoken.

It is sized for a site you can hold in your head: a README, some docs, a
blog. For a hundred versioned pages, reach for MkDocs Material, Hugo or
Astro instead; this does not compete with them and says so.

---

## How it works

![Flow diagram. At the top, a README, a docs folder, a changelog and one logo feed two lanes. The left lane makes: it renders the pages, turns the logo into a full icon set, writes the indexes crawlers and language models look for, and narrates the text with a local voice bound to the page. The right lane audits: it lints the Markdown before anything renders it, reads the built site or a live URL back, and cites a specification for every rule. Both meet in one outcome, a site a search engine, a language model and a reader can each find their way through.](https://raw.githubusercontent.com/warith-harchaoui/sprezzature-publish/main/assets/how-it-works.svg)

## What's here

| | |
|---|---|
| `sprezzature-publish-lint` | **audit** — read the Markdown before anything renders it. Only click and the standard library, milliseconds, pre-commit shaped. `--fix` repairs what has one safe repair. |
| `sprezzature-publish-audit` | **audit** — read the site *after* it exists: head meta, Open Graph, icon links, `robots.txt`, `sitemap.xml`, `llms.txt`. Takes a directory, a page or a live URL — no Markdown source required. `--fix` writes back what can be derived rather than invented. |
| `sprezzature-publish-cta` | **first** — find the calls to action a site already offers, ask which ones it is for, write `ctas.yaml`, and check every page against them. Reads HTML, PHP, Markdown, JSON and YAML. |
| `sprezzature-publish-faq` | **make** — build the FAQ a site is missing from its own pages: questions ranked by the declared CTA, answers grounded in the site's words, the questions it cannot answer yet. **audit** — the `FAQPage` markup against the visible FAQ, `--fix` rewrites it. |
| `sprezzature-publish-findable` | **audit** — one SEO + GEO + AEO report, money pages first, each finding tagged with every goal it serves. `--fix` applies the deterministic repairs. |
| `sprezzature-publish-html` | Markdown → standalone HTML pages, math typeset by KaTeX. |
| `sprezzature-publish-icons` | one logo → favicon, app icons, PWA icons, and the `<head>` snippet that references them. |
| `sprezzature-publish-indexes` | `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, Atom, `humans.txt`. |
| `sprezzature-publish-meta` | Open Graph, Twitter Card and Schema.org JSON-LD, drafted by a local model. |
| `sprezzature-publish-plain` | rewrite prose at a target reading grade, keeping the terms you name. |
| `sprezzature-publish-changelog` | the `CHANGELOG.md` of every sibling repository under `--repos-root` becomes one Atom and RSS feed, a dated release per entry. |
| `sprezzature-publish-narrate` | narrate a post with a local voice, and write the timed track beside the audio. |
| `sprezzature-publish-readalong` | bind that narration to the page, so the sentence being spoken is highlighted. |

### Where the rules come from

Every audit rule cites a specification or the search engine's own
documentation — WHATWG HTML, [RFC 6596](https://datatracker.ietf.org/doc/html/rfc6596)
(canonical), [RFC 9309](https://datatracker.ietf.org/doc/html/rfc9309) (robots.txt),
[sitemaps.org 0.9](https://www.sitemaps.org/protocol.html), [ogp.me](https://ogp.me/),
[X Cards](https://developer.x.com/en/docs/twitter-for-websites/cards/overview/markup),
[JSON-LD 1.1](https://www.w3.org/TR/json-ld11/),
[W3C Web App Manifest](https://www.w3.org/TR/appmanifest/),
[Apple's web-app configuration guide](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/SafariWebContent/ConfiguringWebApplications/ConfiguringWebApplications.html),
[RFC 4287](https://datatracker.ietf.org/doc/html/rfc4287) / [RSS 2.0](https://www.rssboard.org/rss-specification),
[llmstxt.org](https://llmstxt.org/). Where no such document exists, the rule
says so instead of pretending: see `references/audit-site.md`, which carries
the table rule by rule and is the thing to cite when a finding is disputed.

One front door over all thirteen, in click, under two names: `make-site <tool>`
and `sprezzature-publish <tool>` resolve to the same callable, so they cannot
drift. The argparse twin was removed on 2026-10-25, and on 2026-11-04 the
per-tool commands and the MCP server followed: every command here is click.

## Install

```sh
pip install sprezzature-publish
```

One line, and it is everything: the lint, the renderer, the icon set, the
local-model tools, the narration, the HTTP surface and the MCP server.

Until 2026-11-01 this block was six lines and you had to pick — the base was a
single dependency, so `pip install sprezzature-publish` gave you a lint and
nothing else, and knowing which extra you wanted was a prerequisite for the
package being useful. The extras are gone; `[dev]` is the test toolchain and
is not one of them.

Requires **Python 3.10–3.13**: `sprezzature-audio`, now a base dependency,
declares `<3.14` at the version named in the manifest.

The lint needing **only click and the standard library** is deliberate, and
it is the reason this package is worth putting in a pre-commit hook: it runs
in milliseconds, with no image library and no model client behind it. The
rest of the package is installed beside it, since there are no extras any
more, and the lint does not depend on it: `best-engine-ai-helper`, which only
`--ai` uses, is imported when `--ai` asks for it, and every rule runs without it.

## Use

### Gate the Markdown first

```sh
sprezzature-publish-lint docs/            # exit 1 on any error; warnings do not fail
sprezzature-publish-lint docs/ --fix      # repair what has one safe repair
```

### Then build

```sh
sprezzature-publish-html README.md --out site/
sprezzature-publish-html docs/ --out site/docs/
sprezzature-publish-icons logo.png --out site/
sprezzature-publish-indexes --root site/ --base-url https://example.com

# Improve a site that already exists — yours, or somebody else's
sprezzature-publish-audit public/ --base-url https://example.com            # report
sprezzature-publish-audit public/ --base-url https://example.com --dry-run  # preview the repairs
sprezzature-publish-audit public/ --base-url https://example.com --fix --lang en
sprezzature-publish-audit https://example.com/about                         # a live page
sprezzature-publish-meta site/index.html     # asks a local model
```

### Lead readers to what the site is for

Search, generative and answer engines (SEO, GEO, AEO) all end on one
question: once a reader arrives, what should they do? So that is the first
input, asked rather than guessed.

```sh
sprezzature-publish-cta site/                    # what the site links to, then: which one is it for?
sprezzature-publish-faq site/ > faq.md           # the FAQ the site is missing, as a draft
sprezzature-publish-faq site/ --audit --fix      # FAQPage markup rebuilt from the visible FAQ
sprezzature-publish-findable site/ --base-url https://example.com
sprezzature-publish-indexes --root site/ --base-url https://example.com \
  --offer "Local captions for teams." --cta "Book a demo=https://cal.com/acme/demo"
```

The declared CTAs (`ctas.yaml`) decide the *money pages*: the pages that
carry one in their body, and the page it lands on. A `noindex` there is an
error; on a blog post it is a choice. Every FAQ answer comes from a passage
of the site, and every number in it from that passage, or it is not
written: a question the site cannot answer goes to a gap report instead.
`FAQPage` markup is built from the visible text, once per page, and never
claimed to rank: Google stopped showing FAQ rich results on 2026-05-07, and
answer engines read what a reader reads.

### And, if the page should be read aloud

```sh
sprezzature-publish-narrate post.md --out-dir site/audio/
sprezzature-publish-readalong site/post.html --narration site/audio/ --out built/
```

The voice itself lives in [`sprezzature-audio`](https://github.com/warith-harchaoui/sprezzature-audio),
whose engines run on `speaker-helper`: this package owns the **document** and
the **page**, not the engines. Somebody who only wants rendered Markdown never
loads a text-to-speech stack to get it.

### From Python

```python
from sprezzature_publish import lint_file, convert_one
```

A site is built by a script somebody wrote, in a loop, on a schedule. That
caller should import rather than shell out and parse stdout.

### Over HTTP

```sh
pip install "sprezzature-publish"
sprezzature-publish-mcp --port 8000     # the routes and /mcp, one process
curl -s localhost:8000/health
```

`uvicorn sprezzature_publish.api:app` serves the routes alone: the MCP
endpoint is mounted when `sprezzature_publish.mcp` is imported, which is what
`sprezzature-publish-mcp` does before it binds.

Seven routes — lint, audit, render, plain-language, CTAs, FAQ and the joint
findability report — plus `GET /health`, because those are the ones that
cross a network boundary cleanly: text in, text out. The MCP endpoint
publishes the same eight as tools, named by their `operation_id`
(`lint_markdown`, `audit_site`, `render_markdown`, `rewrite_plainly`,
`find_calls_to_action`, `build_faq`, `report_findability`, `health`). The
site-level three take the pages as `[{path, content}]` and the declared CTAs
as a parameter, and say so in the response when the CTAs are missing. The
favicon set is a folder of binaries keyed by filename and stays a command
rather than being offered here with an invented download protocol.

### In containers

```sh
docker compose up -d
curl -s localhost:8000/health
docker compose --profile prose up -d       # adds the local model server
```

The container runs `sprezzature-publish-mcp`, so one port serves the HTTP
routes and the MCP endpoint: point an MCP client at
`http://localhost:8000/mcp`.

The model server is a separate profile: only the tools that ask a local model need it, and
someone who only wants pages should not be made to run one.

## What it does not own

**The voices.** Narration synthesis lives in
[sprezzature-audio](https://github.com/warith-harchaoui/sprezzature-audio) —
captions turn sound into timed text and narration turns text into timed
sound, so one package owns that modality in both directions. This one owns
the document and the page, and invokes those as subprocesses so their heavy
imports never enter its graph. It is a base dependency, so the voices arrive
with `pip install sprezzature-publish`; only the model files are fetched apart.

```sh
sprezzature-audio-install-voice --engine chatterbox    # model files, once
sprezzature-publish-narrate post.md --out-dir site/audio/
```

No engine is named on the second line and none needs to be: speaker-helper's
router picks it from the language and the offline condition, and today it
answers Chatterbox in English and in French, which is why that is the one to
install. `--engine kokoro` takes the light one on purpose: it reads the text,
works out what language it is in, and picks the voice that speaks it. That is
not a convenience — the detected language is what its phonemiser works from,
so a French page read as English is not French in an American accent, it is
an American spelling the words out.

## See also

- **[sprezzature-accessibility](https://github.com/warith-harchaoui/sprezzature-accessibility)** — lint the HTML this emits, and draft the alt text it tells you is missing.
- **[sprezzature-audio](https://github.com/warith-harchaoui/sprezzature-audio)** — the voices, and the captions audit.
- **[sprezzature](https://github.com/warith-harchaoui/sprezzature)** — the suite, and the skills that drive it from Claude.

## License

BSD-3-Clause. See `LICENSE`.

## Author

[Warith HARCHAOUI, Ph.D.](https://www.linkedin.com/in/warith-harchaoui/)
