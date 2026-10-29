# Landscape

`sprezzature-publish` is the publication brick of the [sprezzature](https://sprezzature.ai/)
suite: a folder of Markdown goes in, a site somebody can find comes out.
Pages, the meta tags that decide what a shared link looks like, a favicon and
app-icon set from one logo, the indexes crawlers and language models look for,
and a narration bound to the page sentence by sentence.

It is sized for a site you can hold in your head: a README, some docs, a blog.
That constraint is the first thing to say about it, because everything below
follows from it.

## How it fits in the ecosystem

```
sprezzature suite
├── sprezzature-publish        ← this package (10 tools, document → site)
├── sprezzature-accessibility  (lint the HTML this emits, draft the missing alt)
├── sprezzature-audio          (the voices, and the captions audit)
├── sprezzature-colors         (contrast and colour-vision deficiency)
├── sprezzature-figures        (167 chart types, hand-authored SVG)
├── sprezzature-maps           (real coastlines on a real projection)
├── sprezzature-ui             (the screen, and the translation catalogue)
├── sprezzature-ux-laws        (30 laws, 8 decidable from the markup)
├── sprezzature-video          (what a film claims, against the code)
└── best-engine-ai-helper      (which local model fits this machine)
```

**Before it:** whoever wrote the Markdown. A README, a `docs/` folder, a
`CHANGELOG.md`, one logo file. Nothing else is required, and the lint runs on
the Markdown before anything renders it.

**After it:** [`sprezzature-accessibility`](https://github.com/warith-harchaoui/sprezzature-accessibility),
which reads the HTML this one emits and says whether it is usable, then drafts
the alt text it found missing. The two deliberately do not overlap: this
package checks `og:image:alt`, which is a social-preview surface, and leaves
every image inside the page to the other one.

**The sibling doing the neighbouring work:**
[`sprezzature-audio`](https://github.com/warith-harchaoui/sprezzature-audio),
which owns the sound modality in both directions. Captions turn recorded
speech into timed text; narration turns written text into timed sound. This
package does not synthesise a single sample. It invokes that one as a
subprocess, so a reader who only wants rendered Markdown never installs a
text-to-speech stack.

## When to choose it

- **You have a README and a `docs/` folder and you want them online this
  afternoon**, with the meta tags, the icon set and the sitemap already
  correct rather than filed as follow-up work.
- **A site already exists and nobody can regenerate it.** A page a designer
  exported, a landing page live for three years, a WordPress export. There is
  no Markdown to go back to, and `sprezzature-publish-audit` wants none: it
  takes a directory, a single file or a live URL, reports what a crawler will
  fail to find, and with `--fix` writes back only what can be derived from
  what the page already says. It is the tenth tool and the newest: it is in
  the repository and not yet in the published wheel, which is `1.3.0`.
- **The Markdown has to be gated before it renders.** The lint has no
  dependencies at all, not even an image library, which is what lets it sit in
  a pre-commit hook and run in milliseconds in a minimal container.
- **A post should be listenable, and the listener should be able to follow
  along on the page.** The narration runs on your machine, and the read-along
  it binds is verified cue by cue against the rendered page rather than
  assumed.

## When to pick something else

- **A hundred versioned pages, a plugin ecosystem, a team.**
  [MkDocs Material](https://squidfunk.github.io/mkdocs-material/),
  [Docusaurus](https://docusaurus.io/) and
  [Starlight](https://starlight.astro.build/) are better at that in every
  direction that matters: versioned navigation, search, a theme somebody else
  maintains, contributors who already know the conventions. This package says
  so in its own README and does not try to compete.
- **Build speed over everything, or a single binary with no runtime.**
  [Hugo](https://gohugo.io/) and [Zola](https://www.getzola.org/). Hugo also
  ships multilingual routing, `sitemap.xml` and RSS without a plugin, which is
  three of this package's columns answered by the tool you were going to use
  anyway.
- **A design you control line by line, with islands of interactivity.**
  [Astro](https://astro.build/) or [Eleventy](https://www.11ty.dev/). This
  package emits one template and offers no theme layer at all.
- **Documentation hosted for you, with `llms.txt` generated and nothing to
  install.** [Mintlify](https://www.mintlify.com/) and
  [GitBook](https://gitbook.com/) do that, and Mintlify has been emitting
  `llms.txt`, `llms-full.txt` and a Markdown twin of every page since November
  2024. If an account and a hosted build are acceptable, that is less work
  than any local toolchain.
- **A voice for anything, in any language, reading anything.**
  [ElevenReader](https://elevenlabs.io/text-reader) and
  [Speechify](https://speechify.com/) read a PDF, an email or a page nobody
  asked a build system about, in more languages than this package carries
  player wording for, with word-level highlighting rather than
  sentence-level. They are products; this is a build step.
- **Prose style enforced across a whole documentation set.**
  [Vale](https://vale.sh/) is a single offline binary with a rule language,
  readability metrics and a large set of published style guides. The
  plain-language tool here rewrites; Vale measures and enforces, which is a
  different job and the one a docs team usually wants first.

## Ideas worth stealing

Studying a competitor and bringing nothing home is wasted reading. Eight
things these tools do, ordered by what they return for what they cost. Two
are refusals, and the reason is the entry.

**[Mintlify](https://www.mintlify.com/) and the `llms.txt` v2 proposal: the
Markdown twin, advertised.** Mintlify publishes a `.md` copy of every page
beside the HTML and points `llms.txt` at the copy, so an agent gets clean
prose with no navigation and no scripts; v2 of the proposal (August 2026)
names the mechanism, `rel="alternate" type="text/markdown"`. Here:
`md_to_html.py` writes `page.md` beside `page.html` and adds that link to the
head, `site_indexes.py` links the `.md` from `llms.txt` instead of the
rendered page, and `audit_site.py` gains a `SITE107` that checks the twin
exists and the link declares it. Cost: half a day on the Markdown path, where
the source is already in hand. Honest limit: a page audited with no Markdown
behind it can have no twin, so the rule has to be a note there and not an
error, which is the same shape as `SITE014` already.

**[Vale](https://vale.sh/): reading grade as a measurement, not a prompt
hint.** Vale ships readability as rules (Flesch-Kincaid, Gunning fog, SMOG,
LIX, Coleman-Liau, ARI), computed deterministically with no model anywhere
near them. Here: `plain_language.py` takes `--target-grade 8` and passes it
into a prompt, then checks only that the output is not longer than the input.
A `--report` flag printing the measured grade before and after would make the
flag mean something. This is the best ratio on the list precisely because the
brick already has the flag and nothing behind it. Cost: an afternoon, standard
library, no new dependency. The honest caveat is that syllable counting is
approximate in English and more so in French, so the number is a reported
estimate and has to say it is.

**[Material for MkDocs](https://squidfunk.github.io/mkdocs-material/plugins/social/)'s
social plugin: a preview card per page, rendered locally.** It draws a
1200×630 PNG from the page's own title and ships it as `og:image`, cached in
the site directory so nothing depends on an external service. Here,
`SITE008` reports a missing `og:image` and refuses to invent one, which is
correct and also the commonest finding on a new site. `favicons.py` already
has Pillow, the logo, the background and both theme colours: a `--cards` run
writing `og/<page>.png` would turn that refusal into a derived repair, which
is the dividing line `audit_site.py` already draws. Cost: an afternoon inside
an extra people installing icons already have. What makes it not free: a card
needs a bundled font, and a font is a licence question.

**[Hugo](https://gohugo.io/methods/page/alternativeoutputformats/): the
multilingual sitemap.** Hugo writes `xhtml:link rel="alternate" hreflang=…`
entries so a crawler is told which page is the other language of which, rather
than left to infer it from a path. Here: `site_indexes.py` writes a bare
`<url><loc>` list, and the suite's own site ships English and French. A
`--hreflang` flag pairing `/fr/x.html` with `/x.html` by path convention, plus
a per-site rule that reports an unpaired translation, closes a gap that is
more bug report than idea. Cost: an afternoon, no dependency, and the format
is documented by Google rather than by sitemaps.org, which the rule table has
to say.

**[Yoast SEO](https://yoast.com/): one `@graph`, not several blocks.** Yoast
emits a single JSON-LD block whose nodes (`WebSite`, `WebPage`,
`Organization`, `Person`, `BreadcrumbList`) reference each other by `@id`
instead of sitting in separate unconnected scripts. Here:
`meta_from_ollama.py` asks a local model for one object. Giving it a fixed
`@graph` skeleton to fill makes the model's job smaller rather than larger,
and lets `SITE011` check something real, that every `@id` referenced inside
the document resolves inside it. Cost: half a day, a prompt change and a
schema. It also narrows what the model can get wrong, which is the direction
this package already goes everywhere else.

**[RealFaviconGenerator](https://realfavicongenerator.net/)'s checker: open
the icon, do not just find it.** It reads a published site and reports, per
platform, which declaration is missing and which points at a file that is not
what it claims. Here: `SITE110` and `SITE111` check the files exist and
`SITE112` checks the `head.html` snippet was actually pasted, but nothing
opens an icon to confirm it decodes and is the size the `<link>` declares,
which is exactly how a hand-copied set fails. Cost: a real objection, not a
small one. The audit is one of the two tools that run with nothing installed,
and reading a PNG means Pillow. The shape that survives is an opt-in
`--check-icons` that names what it needs and skips without it.

**[starlight-llms-txt](https://delucis.github.io/starlight-llms-txt/)'s
`llms-small.txt`: refused.** The plugin writes a third, trimmed variant for
small context windows, beside `llms.txt` and `llms-full.txt`. Not taken.
`llms.txt` is a proposal rather than a standard and `llms-full.txt` is already
a convention the proposal itself does not mention; a third invented filename
would be this package writing a file nobody looks for by name. The useful half
of the idea already exists as `--no-llms-full`, which lets a caller decide how
much to ship.

**[Speechify](https://speechify.com/) and
[ElevenReader](https://elevenlabs.io/text-reader): word-level highlighting,
refused here.** Both highlight the word being spoken, not the sentence, and it
reads better. Not taken, for a reason that is the whole design of the module:
sentence cues come out of the narration run itself, so the page and the audio
can be compared one by one and the build raises on the first divergence. Word
timings would need per-token timestamps from the engine or a forced aligner,
neither of which can be checked the same way, and the single guarantee this
feature makes is that the highlight is never off by one. If it is ever taken,
it belongs in `sprezzature-audio`, which owns timing in both directions.

## How the field divides

**Generators against components against products.** A static-site generator
(Hugo, Astro, Eleventy, Jekyll, Zola, Pelican, Quarto, mdBook) owns the whole
pipeline from a content folder to a directory of HTML, and treats metadata as
something you configure inside its template layer. A search-engine
optimisation (SEO) component
(next-seo, astro-seo, jekyll-seo-tag, Yoast SEO) owns only the `<head>` and
assumes a site already exists around it. A hosted product (Mintlify, GitBook)
owns the build, the hosting and the search, and asks for an account. This
package sits across the first two: it generates pages, and it will also walk
into a site it did not build and repair the head.

**Local against hosted, and it is not a licence question.** Every generator
in the table runs on your machine; so do Vale and pwa-asset-generator. The
split that matters is narrower: where does the *judgement* happen. Meta
descriptions, plain-language rewrites and alt text are the parts people
outsource to a service, and that is the one place this package insists on a
local model, resolved through
[`best-engine-ai-helper`](https://github.com/warith-harchaoui/best-engine-ai-helper)
so no script here names a model tag. Mintlify, GitBook, ElevenReader,
Speechify and NotebookLM all send the text somewhere. For a public README
that is nobody's problem; for an internal document it decides the question.

**Text in against sound out.** The narration half of this table has almost no
overlap with the generator half. ElevenReader, Speechify, NotebookLM and
[Podcastfy](https://github.com/souzatharsis/podcastfy) read a document aloud
and none of them build a site; no static-site generator in the table reads
anything aloud. The read-along column is where the two halves touch, and it
is nearly empty: the consumer readers do it inside their own app, over a page
they fetched, and this package does it by writing markup into a page you then
host yourself. Nobody else emits a `<track kind="metadata">` beside your own
HTML and leaves it there.

**The new column is `llms.txt`, and it is contested.** Proposed by Jeremy
HOWARD in September 2024 and revised to v2 in August 2026, it is a
convention, not a standard. Independent measurements in 2026 put adoption
between 5.6 % and 13.3 % of sampled domains depending on the sample, and
Google's own generative-search guidance of 15 May 2026 lists it among the
tactics it considers unnecessary. Mintlify and GitBook emit it automatically,
Starlight has a well-used plugin, Nextra has none. This package writes it, and
the rule that checks it says in `references/audit-site.md` that it is a
proposal rather than a standards-body document, because that is the honest
level of claim.

## The table

Twenty-six tools, fifteen criteria. A star is a **judgement**, not a
measurement: 5 means this is a strength of that tool as of October 2026, 1
means it does not really do this. Every column is oriented so that more stars
is better, which is why the cost axis reads as openness and the weight axis
reads as lightness. The numbers are written down so somebody can disagree with
a specific cell rather than with a feeling.

`sprezzature-publish` is the first row because `standpoint` orients the whole
map around the first row and places it top right. That is a drawing
convention, not a claim about quality, and the row loses outright on four
columns: it does not scale past a hundred pages, it has no theme layer, its
player speaks two languages and refuses the rest, and it is one author's
package a few months old.

| Tool | Per-page meta tags out of the box | Icon set from one logo | Indexes crawlers look for | Indexes language models look for | Syndication feed | Audio narration | Sentence-synchronised read-along | Plain-language rewriting | Applies to HTML already published | Local and offline, no account | Light to install | Scales past a hundred pages | Themes and customisation | Bilingual output and parity | Maturity and ecosystem |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| sprezzature-publish | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ |
| MkDocs Material | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Hugo | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Astro | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Starlight | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Docusaurus | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Eleventy | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Jekyll | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Zola | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| VitePress | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Nextra | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| Quarto | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Pelican | ⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| mdBook | ⭐⭐ | ⭐ | ⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| Mintlify | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| GitBook | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| next-seo | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Yoast SEO | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| RealFaviconGenerator | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| pwa-asset-generator | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ |
| Vale | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| Hemingway Editor | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ |
| ElevenReader | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Speechify | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| NotebookLM | ⭐ | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Podcastfy | ⭐ | ⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐ |

## The map

![Positioning map of 26 publishing, metadata, prose and narration tools. sprezzature-publish sits alone in the top-right quadrant, far to the right of everything else at its height. Level with it but on the centre line are the reading products Speechify and ElevenReader, with NotebookLM and Podcastfy just below and to their left. The left edge, near the horizontal axis, holds the single-purpose tools Hemingway Editor, RealFaviconGenerator, pwa-asset-generator and Vale. The whole lower half is the static-site generator family: Hugo, Docusaurus, Astro, Starlight, MkDocs Material, Jekyll, Quarto and Zola toward the right, Eleventy, Nextra, Pelican, mdBook and next-seo toward the left, with the hosted products Mintlify and GitBook and the plugin Yoast SEO on the right edge below the axis. mdBook, the weakest overall, is diagonally opposite the reference. The horizontal axis opposes autonomy on the left to reach on the right, reach meaning the files that make a document findable. The vertical axis opposes an adaptable build system at the bottom to a tool that acts on a document a reader already has at the top.](assets/landscape.svg)

The source is [`assets/landscape.csv`](assets/landscape.csv), the star table
above and nothing added, and the map is regenerated with:

```sh
python scripts/landscape_to_csv.py ~/sprezzature-publish/LANDSCAPE.md   # from the hub
standpoint assets/landscape.csv --outdir assets --stem landscape --check
```

The geometry is ordinary correlation principal component analysis (PCA)
and it is **deterministic**: the same
table gives the same map every run, whatever model named the poles. The four
words at the edges come from a local model; the loadings are the control, and
they are vaguer than the numbers behind them, so here is what the two axes are
actually made of.

**Horizontal, "Autonomy ↔ Reach", 37.4 % of the variance.** Indexes language
models look for (+0.49), indexes crawlers look for (+0.42), per-page meta tags
(+0.38) and bilingual parity (+0.37) pull right; local and offline (−0.16)
pulls left, and that is the strongest thing pulling left at all. So the axis
is not really autonomy against reach: it is **does this tool write the files
that make a document findable, or not**. The left pole is mostly the absence
of that work, which is why Hemingway Editor (−3.01) and pwa-asset-generator
(−2.35) are out there. Mintlify sits at exactly the same horizontal
coordinate as this package, 3.01, which is the map agreeing that a hosted docs
product and this one answer the same question by different means.

**Vertical, "Adaptable ↔ Engaging", 17.8 % of the variance.** Applies to HTML
already published (+0.41), audio narration (+0.40), read-along (+0.37) and
plain-language rewriting (+0.25) load at the top; scales past a hundred pages
(−0.34), themes and customisation (−0.33) and local and offline (−0.25) load
at the bottom. The real opposition is **a build system you configure** against
**a tool that acts on a document somebody is already holding**. Every static
site generator in the table lies in a band between −3.7 and −1.7; Speechify
and ElevenReader are at +3.68 and +3.63. This package is at +3.68, which puts
it with the readers rather than with the generators, and that is the correct
reading of what it is.

One detail worth saying because it is the opposite of flattering: **local and
offline loads negative on both axes**, so it pulls toward the bottom-left.
This package scores 5 on it and sits top-right anyway. Being local is not what
puts it there; writing the indexes and binding the narration is.

**Two axes carry 55.2 % of the table.** Nearly half of what those fifteen
criteria say is not on this page, which is expected with fifteen criteria over
twenty-six tools and is the reason the table stays above the map rather than
below it. `--check` reports `leader_top_right: True` and
`axis_labels_visible: True`, and `readable: False`: five pairs of point labels
risk overlapping (Hugo and Docusaurus, Jekyll and Quarto, Zola and VitePress,
Nextra and Pelican, ElevenReader and Speechify). That is a crowding artefact
of thirteen generators sharing one band, not a geometry fault, and the
coordinates behind every label are in
[`assets/landscape.yaml`](assets/landscape.yaml).

`standpoint` also writes a prose interpretation beside the figure. It is not
reproduced here, because a model reading back ratings somebody wrote is not a
finding, and this file is more useful if the judgements stay visibly mine.

## Sources

- [llms.txt, the proposal](https://llmstxt.org/) by Jeremy HOWARD, v2, August 2026.
- [State of llms.txt 2026: adoption, standards, and practice](https://presenc.ai/research/state-of-llms-txt-2026).
- [Docs platforms that generate llms.txt automatically (2026)](https://context7.com/llms-txt-documentation-platforms).
- [Mastering generative engine optimization in 2026](https://searchengineland.com/mastering-generative-engine-optimization-in-2026-full-guide-469142), Search Engine Land.
- [Static site generators 2026 head-to-head](https://www.youngju.dev/blog/culture/2026-05-14-static-site-generators-2026-hugo-eleventy-astro-mkdocs-docusaurus-mintlify-starlight-comparison-deep-dive.en).
- [Material for MkDocs, the built-in social plugin](https://squidfunk.github.io/mkdocs-material/plugins/social/).
- [`starlight-llms-txt`](https://delucis.github.io/starlight-llms-txt/).
- [W3C Web Application Manifest, icon masks](https://www.w3.org/TR/appmanifest/#icon-masks).
- [pwa-icons: a faster progressive-web-app icon generator](https://github.com/SivaramPg/pwa-icons).
- [Podcastfy, an open-source alternative to NotebookLM's podcast feature](https://github.com/souzatharsis/podcastfy).
