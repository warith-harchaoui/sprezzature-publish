# Examples

Every command line below is parsed by `tests/test_the_documented_commands_run.py`,
which hands it to the tool's own click parser without running the tool: an
unknown flag, a missing required option or an extra argument fails the
suite.

## Gate the Markdown before anything renders it

```bash
sprezzature-publish-lint docs/
sprezzature-publish-lint docs/ --format json
sprezzature-publish-lint docs/ --fix
```

The lint needs only click and the standard library, so this is the one
worth putting in a pre-commit hook: no image library, no model client,
milliseconds.

## Redraw a diagram the lint reports

A Mermaid block is reported as `MMD001`. Write the arrows as rows, draw them
with `sprezzature-figures`, embed the SVG (Scalable Vector Graphics, an
image made of shapes rather than pixels, so it stays sharp at any zoom), and
delete the block:

```bash
printf 'source,target\nDraft,Review\nReview,Publish\n' > flow.csv
sprezzature-figures render flowchart --data flow.csv --out docs/flow.svg
```

## Markdown to pages

```bash
sprezzature-publish-html README.md --out site/
sprezzature-publish-html docs/ --out site/ --site-name 'Acme' --lang en
sprezzature-publish-html docs/ --out site/ --katex-base ./vendor/katex
```

`--katex-base` pointed at a local path is what makes the build offline:
left alone it references the public CDN (content delivery network, servers
around the world that hand each reader a copy of a file from nearby).

## One logo to the whole icon set

```bash
sprezzature-publish-icons logo.svg --raster logo.png --out public/ --name 'Acme'
sprezzature-publish-icons logo.png --bg '#ffffff' --theme-dark '#000000'
```

The run also writes `site.webmanifest` and a paste-ready `head.html`, so
the references do not have to be typed by hand. An SVG source needs
`--raster`: Pillow cannot rasterise SVG, and without a PNG beside it the run
writes `favicon.svg` and nothing else. Write the set to the site root: the
links in `head.html` are root-relative (`/favicon.ico`), and `audit` looks for
`head.html` at the root.

## What crawlers and language models look for

```bash
sprezzature-publish-indexes --root site/ --base-url https://example.com
sprezzature-publish-indexes --root site/ --base-url https://example.com --humans --rss
sprezzature-publish-indexes --root site/ --base-url https://example.com --no-llms-full
```

`robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, a feed and
`humans.txt`. Only click and the standard library, like the lint.

## Audit a site that already exists

```bash
sprezzature-publish-audit public/ --base-url https://example.com
sprezzature-publish-audit public/ --base-url https://example.com --dry-run
sprezzature-publish-audit public/ --base-url https://example.com --fix --lang en
sprezzature-publish-audit https://example.com/about --format json
```

No Markdown is needed: it reads the emitted HTML, a single page or a live
address. `--fix` writes only what can be derived from what the page already
says, plus `--lang`, `--theme-color` and `--og-image` when they are given; a
live address is reported, never repaired.

## Lead readers to what the site is for

```bash
sprezzature-publish-cta site/ --write ctas.yaml
sprezzature-publish-cta site/ --ctas ctas.yaml
sprezzature-publish-faq site/ --format html -o faq.html
sprezzature-publish-faq site/ --hints questions.csv
sprezzature-publish-faq site/ --audit --fix
sprezzature-publish-findable site/ --ctas ctas.yaml --base-url https://example.org --fix
```

`cta` asks which action the site is for when the terminal is interactive,
and `--no-ask` drafts the plan without asking. `faq` drafts with the local
model unless `--no-llm`, which keeps the site's own sentences; `--hints`
takes real questions, one per line, and ranks them first. `findable`
puts the money pages first and tags each finding with the goals it serves.

## Meta tags, drafted by a local model

```bash
sprezzature-publish-meta site/index.html --site-name 'Acme' --lang en
sprezzature-publish-meta site/index.html --canonical https://example.com/ --no-cache
```

Strict JSON on stdout, so the caller decides what to do with it. The model
runs on the machine; nothing leaves it.

## Rewrite prose at a reading grade

```bash
cat draft.md | sprezzature-publish-plain --target-grade 8 --lang en
sprezzature-publish-plain --input copy.md --preserve 'Sprezzature,Tailwind'
```

`--preserve` is the flag that matters: brand names and identifiers survive
the rewrite verbatim.

## Changelogs become one feed

```bash
sprezzature-publish-changelog --repos-root .. --out ../web
sprezzature-publish-changelog --repos-root .. --out ../web --rss-only
```

Every `CHANGELOG.md` in the repositories beside each other under
`--repos-root` is read, and each dated release heading becomes one entry of
a combined `feed.atom` / `feed.xml`. An `## [Unreleased]` with no date is
left out.

## Read a post aloud, and follow it on the page

```bash
sprezzature-publish-narrate post.md --out-dir site/audio/
sprezzature-publish-narrate site/post.html --scope article --out-dir site/audio/
sprezzature-publish-readalong site/post.html --narration site/audio/ --out built/
```

`--scope` on an HTML input is the difference between reading the article
and reading the header, the nav and the footer along with it.

## The two repairs a narrated page needs

```bash
sprezzature-publish-readalong site/post.html --strip --out drafts/
sprezzature-publish-readalong site/post.html --narration site/audio/ --check
```

`--strip` takes the player back out, which is the first half of correcting
a sentence in a page that already has a voice: strip, edit the prose,
record again. `--check` is for the other failure, a page edited after it
shipped: the markers stay, their times stay, and every one of them now
points at the wrong sentence, which is worse than no highlight because it
is confidently wrong.

## One front door, two names

```bash
make-site lint docs/
make-site html README.md --out site/
sprezzature-publish lint docs/
sprezzature-publish tools
```

`make-site <tool>` and `sprezzature-publish <tool>` are one click command
under two names, resolving against one table. A tool cannot appear in one and
be missing from the other. `tools` lists the thirteen and says which import
cleanly here. `--help` after a tool name is answered by the front door with
the tool's one-line summary; its full options are on its own command,
`sprezzature-publish-lint --help`.

## The skill, for an agent

```bash
sprezzature-publish-skill
sprezzature-publish-skill --install
sprezzature-publish-skill --install --agent opencode
sprezzature-publish skill --path
```

The skill ships inside the package (`sprezzature_publish/skill/`, also
returned by `sprezzature_publish.skill_path()`). The first line reports
whether the copy in `~/.claude/skills` is in step; `--install` copies it
there, or into `~/.opencode/skills` with `--agent opencode`.

## Over HTTP

```bash
pip install "sprezzature-publish"
sprezzature-publish-mcp --port 8000     # the routes and /mcp, one process
curl -s localhost:8000/health
```

## In containers

```bash
docker compose up -d
docker compose --profile prose up -d
```

The model server is its own profile: only the tools that ask a local model
need it (`meta`, `plain` and `faq`, which drafts with the model unless
`--no-llm`; `lint --ai` and `narrate --ai-hints` when asked), and someone who only wants pages should not
be made to run one.
