# Examples

Every command line below is parsed by `tests/test_the_documented_commands_run.py`,
which asks each tool's parser whether it accepts the flags on the line. A
line here that does not run fails the suite.

## Gate the Markdown before anything renders it

```bash
sprezzature-publish-lint docs/
sprezzature-publish-lint docs/ --format json
sprezzature-publish-lint docs/ --fix
```

The lint is standard library only, so this is the one worth putting in a
pre-commit hook: no image library, no model client, milliseconds in a
minimal container.

## Render the Mermaid blocks while linting

```bash
sprezzature-publish-lint docs/ --render-mermaid --out-dir docs/diagrams/
sprezzature-publish-lint docs/ --render-mermaid --fix
```

With `--fix`, the PNG sibling reference is inserted next to the block. The
repair is idempotent and never invents content.

## Markdown to pages

```bash
sprezzature-publish-html README.md --out site/
sprezzature-publish-html docs/ --out site/ --site-name 'Acme' --lang en
sprezzature-publish-html docs/ --out site/ --katex-base ./vendor/katex
```

`--katex-base` pointed at a local path is what makes the build offline:
left alone it references the public CDN.

## One logo to the whole icon set

```bash
sprezzature-publish-icons logo.svg --out public/ --name 'Acme'
sprezzature-publish-icons logo.png --bg '#ffffff' --theme-dark '#000000'
```

The run also writes `site.webmanifest` and a paste-ready `head.html`, so
the references do not have to be typed by hand.

## What crawlers and language models look for

```bash
sprezzature-publish-indexes --root site/ --base-url https://example.com
sprezzature-publish-indexes --root site/ --base-url https://example.com --humans --rss
sprezzature-publish-indexes --root site/ --base-url https://example.com --no-llms-full
```

`robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, a feed and
`humans.txt`. Standard library only, like the lint.

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

## A CHANGELOG becomes dated posts and a feed

```bash
sprezzature-publish-changelog --repos-root .. --out ../web
sprezzature-publish-changelog --repos-root .. --out ../web --rss-only
```

## Read a post aloud, and follow it on the page

```bash
sprezzature-publish-narrate post.md --out-dir site/audio/
sprezzature-publish-narrate site/post.html --scope article --out-dir site/audio/
sprezzature-publish-readalong site/post.html --narration site/audio/ --out site/
```

`--scope` on an HTML input is the difference between reading the article
and reading the header, the nav and the footer along with it.

## The two repairs a narrated page needs

```bash
sprezzature-publish-readalong site/post.html --strip --out site/
sprezzature-publish-readalong site/post.html --check
```

`--strip` takes the player back out, which is the first half of correcting
a sentence in a page that already has a voice: strip, edit the prose,
record again. `--check` is for the other failure, a page edited after it
shipped: the markers stay, their times stay, and every one of them now
points at the wrong sentence, which is worse than no highlight because it
is confidently wrong.

## Either front door

```bash
make-site lint docs/
make-site html README.md --out site/
sprezzature-publish lint docs/
```

`make-site <tool>` reads its flags with argparse, `sprezzature-publish
<tool>` with click, and both resolve against one table. A tool cannot
appear in one and be missing from the other.

## Over HTTP

```bash
pip install "sprezzature-publish[api]"
uvicorn sprezzature_publish.api:app --port 8000
curl -s localhost:8000/health
```

## In containers

```bash
docker compose up -d
docker compose --profile prose up -d
```

The model server is its own profile: two tools of nine need it, and
someone who only wants pages should not be made to run one.
