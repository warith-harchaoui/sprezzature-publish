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

## What's here

| | |
|---|---|
| `sprezzature-publish-lint` | **audit** — read the Markdown before anything renders it. Standard library only, milliseconds, pre-commit shaped. `--fix` repairs what has one safe repair. |
| `sprezzature-publish-html` | Markdown → standalone HTML pages, Mermaid diagrams rendered. |
| `sprezzature-publish-icons` | one logo → favicon, app icons, PWA icons, and the `<head>` snippet that references them. |
| `sprezzature-publish-indexes` | `robots.txt`, `sitemap.xml`, `llms.txt`, `llms-full.txt`, Atom, `humans.txt`. |
| `sprezzature-publish-meta` | Open Graph, Twitter Card and Schema.org JSON-LD, drafted by a local model. |
| `sprezzature-publish-plain` | rewrite prose at a target reading grade, keeping the terms you name. |
| `sprezzature-publish-changelog` | a `CHANGELOG.md` becomes dated posts and a feed. |
| `sprezzature-publish-narrate` | narrate a post with a local voice, and write the timed track beside the audio. |
| `sprezzature-publish-readalong` | bind that narration to the page, so the sentence being spoken is highlighted. |

Two front doors over all nine: `make-site <tool>` (argparse) and
`sprezzature-publish <tool>` (click). Both read one table, so a tool cannot
appear in one and be missing from the other.

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
sprezzature-publish-html README.md docs/ --out-dir site/
sprezzature-publish-icons logo.png --out-dir site/icons/
sprezzature-publish-indexes site/ --base-url https://example.com
```

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
sprezzature-audio-install-voice --engine openvoice
sprezzature-publish-narrate post.md --out-dir site/audio/
```

## See also

- **[sprezzature-accessibility](https://github.com/warith-harchaoui/sprezzature-accessibility)** — lint the HTML this emits, and draft the alt text it tells you is missing.
- **[sprezzature-audio](https://github.com/warith-harchaoui/sprezzature-audio)** — the voices, and the captions audit.
- **[sprezzature](https://github.com/warith-harchaoui/sprezzature)** — the suite, and the skills that drive it from Claude.

## License

BSD-3-Clause. See `LICENSE`.

## Author

[Warith HARCHAOUI, Ph.D.](https://www.linkedin.com/in/warith-harchaoui/)
