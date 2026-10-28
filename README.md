# sprezzature-publish

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
| `sprezzature-publish-lint` | **audit** — read the Markdown before anything renders it. Standard library only, milliseconds, pre-commit shaped. `--fix` repairs what has one safe repair. |
| `sprezzature-publish-audit` | **audit** — read the site *after* it exists: head meta, Open Graph, icon links, `robots.txt`, `sitemap.xml`, `llms.txt`. Takes a directory, a page or a live URL — no Markdown source required. `--fix` writes back what can be derived rather than invented. |
| `sprezzature-publish-html` | Markdown → standalone HTML pages, Mermaid diagrams rendered. |
| `sprezzature-publish-icons` | one logo → favicon, app icons, PWA icons, and the `<head>` snippet that references them. |
| `sprezzature-publish-indexes` | `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, Atom, `humans.txt`. |
| `sprezzature-publish-meta` | Open Graph, Twitter Card and Schema.org JSON-LD, drafted by a local model. |
| `sprezzature-publish-plain` | rewrite prose at a target reading grade, keeping the terms you name. |
| `sprezzature-publish-changelog` | a `CHANGELOG.md` becomes dated posts and a feed. |
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

One front door over all nine, in click, under two names: `make-site <tool>`
and `sprezzature-publish <tool>` resolve to the same callable, so they cannot
drift. The argparse twin was removed on 2026-10-25.

## Install

```sh
pip install sprezzature-publish              # the lint: zero dependencies
pip install "sprezzature-publish[html]"      # + the renderer
pip install "sprezzature-publish[icons]"     # + Pillow, for the icon set
pip install "sprezzature-publish[prose]"     # + the local-model tools
pip install "sprezzature-publish[all]"       # everything above
pip install "sprezzature-publish[api,mcp]"   # + the HTTP and agent surfaces
```

The lint having **no dependencies at all** is deliberate, and it is the
reason this package is worth putting in a pre-commit hook: it runs in
milliseconds in a minimal container, with no image library and no model
client behind it. Everything heavier is an extra, named after the tool that
needs it, so an install says what it is for.

## Use

### Gate the Markdown first

```sh
sprezzature-publish-lint docs/            # exit 1 on any finding
sprezzature-publish-lint docs/ --fix      # repair what has one safe repair
```

### Then build

```sh
sprezzature-publish-html README.md docs/ --out site/
sprezzature-publish-icons logo.png --out site/icons/
sprezzature-publish-indexes site/ --base-url https://example.com

# Improve a site that already exists — yours, or somebody else's
sprezzature-publish-audit public/ --base-url https://example.com            # report
sprezzature-publish-audit public/ --base-url https://example.com --dry-run  # preview the repairs
sprezzature-publish-audit public/ --base-url https://example.com --fix --lang en
sprezzature-publish-audit https://example.com/about                         # a live page
sprezzature-publish-meta site/index.html     # asks a local model
```

### And, if the page should be read aloud

```sh
sprezzature-publish-narrate post.md --out-dir site/audio/
sprezzature-publish-readalong site/post.html --narration site/audio/
```

The voice itself lives in [`speaker-helper`](https://github.com/warith-harchaoui/speaker-helper):
this package owns the **document** and the **page**, not the engines. Somebody
who only wants rendered Markdown should not have to install a text-to-speech
stack to get it.

### From Python

```python
from sprezzature_publish import lint_file, convert_one
```

A site is built by a script somebody wrote, in a loop, on a schedule. That
caller should import rather than shell out and parse stdout.

### Over HTTP

```sh
pip install "sprezzature-publish[api]"
uvicorn sprezzature_publish.api:app --port 8000
curl -s localhost:8000/health
```

Three routes — lint, render, plain-language — because those are the ones
that cross a network boundary cleanly: text in, text out. The favicon set is
a folder of binaries keyed by filename and stays a command rather than being
offered here with an invented download protocol.

### In containers

```sh
docker compose up -d
curl -s localhost:8000/health
docker compose --profile prose up -d       # adds the local model server
```

The model server is a separate profile: two tools of nine need it, and
someone who only wants pages should not be made to run one.

## What it does not own

**The voices.** Narration synthesis lives in
[sprezzature-audio](https://github.com/warith-harchaoui/sprezzature-audio) —
captions turn sound into timed text and narration turns text into timed
sound, so one package owns that modality in both directions. This one owns
the document and the page, and invokes those as subprocesses so their heavy
imports never enter its graph.

```sh
pip install "sprezzature-audio[narrate]"
sprezzature-audio-install-voice --engine kokoro
sprezzature-publish-narrate post.md --out-dir site/audio/
```

No voice is named above and none needs to be: the default engine reads the
text, works out what language it is in, and picks the voice that speaks it.
That is not a convenience — the detected language is what the phonemiser
works from, so a French page read as English is not French in an American
accent, it is an American spelling the words out.

## See also

- **[sprezzature-accessibility](https://github.com/warith-harchaoui/sprezzature-accessibility)** — lint the HTML this emits, and draft the alt text it tells you is missing.
- **[sprezzature-audio](https://github.com/warith-harchaoui/sprezzature-audio)** — the voices, and the captions audit.
- **[sprezzature](https://github.com/warith-harchaoui/sprezzature)** — the suite, and the skills that drive it from Claude.

## License

BSD-3-Clause. See `LICENSE`.

## Author

[Warith HARCHAOUI, Ph.D.](https://www.linkedin.com/in/warith-harchaoui/)
