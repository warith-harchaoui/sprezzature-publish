# Triggers

When to turn Markdown into a site, and what to call.

This file is written for an agent: a Claude Code or OpenCode skill, an MCP
host, anything choosing a tool on someone's behalf. Humans are welcome, but
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

---

## Which tool, and which neighbour

Four different questions get asked about the same page. Send each to the
right place: they do not substitute for one another.

| The question | Package | Where to start |
|---|---|---|
| **Can it be found?** meta tags, feeds, sitemap, llms.txt | sprezzature-publish | `sprezzature-publish-lint`, then `-indexes` |
| **Can *this existing site* be found?** no Markdown behind it | sprezzature-publish | `sprezzature-publish-audit <dir\|url>`, then `--fix` |
| **Is it accessible?** missing alt, unlabelled inputs, heading order | sprezzature-accessibility | `lint_html` |
| **Is it legible?** contrast, colour-blind safety | sprezzature-colors | `check_contrast` |
| **Is the speech already recorded?** sound in, timed text out | sprezzature-audio | `sprezzature-audio-captions` |

The last row is the one that gets mis-routed. This package turns text into
sound and binds it to a page. Turning sound into text is the other
direction, and it lives next door.

---

## The nine tools, and the plain-language request each answers

You do not need to name a tool to route: `make-site <tool>` and
`sprezzature-publish <tool>` both resolve against one table. This list is
for reading a request back as a tool.

| Tool | The request it answers |
|---|---|
| `lint` | "check my Markdown", "is this doc clean", a pre-commit gate |
| `html` | "make pages out of this", "render the diagrams" |
| `icons` | "I need favicons", "app icons", "PWA icons", "I only have a logo" |
| `indexes` | "SEO", "sitemap", "robots.txt", "llms.txt", "RSS", "why doesn't Google see it" |
| `meta` | "the link preview looks wrong", "OG card", "Twitter card", "Schema.org" |
| `plain` | "simplify this", "write it for a wider audience", "rewrite at grade 8" |
| `changelog` | "turn my releases into posts", "a feed from my CHANGELOG" |
| `narrate` | "read this post aloud", "podcast my blog", "text to speech" |
| `readalong` | "highlight the sentence being spoken", "follow along while it reads" |

---

## What to call, on every surface

| Job | CLI | MCP tool |
|---|---|---|
| Lint the Markdown | `sprezzature-publish-lint` | `lint_markdown` |
| Render pages | `sprezzature-publish-html` | `render_markdown` |
| Plain-language rewrite | `sprezzature-publish-plain` | `rewrite_plainly` |
| Icon set | `sprezzature-publish-icons` | none, see below |
| Crawler and model indexes | `sprezzature-publish-indexes` | none, see below |
| Meta tags | `sprezzature-publish-meta` | none, see below |
| Narrate a post | `sprezzature-publish-narrate` | none, see below |
| Bind the narration | `sprezzature-publish-readalong` | none, see below |
| A CHANGELOG as posts | `sprezzature-publish-changelog` | none, see below |

Three of the nine cross a network boundary cleanly, because they are text
in and text out, and those three are the MCP tools. The other six write a
folder of files, keyed by filename: an icon set, a sitemap beside the pages
it indexes, an audio track and its cues. Offering those over MCP would mean
inventing a download protocol, so they stay commands. Call them with Bash.

Start with the lint either way. It has no dependencies at all, so it runs
where nothing else will, and a document that fails it will not render well
anyway.

---

## What this cannot see, and say so when you report

It reads documents, and it writes files. It cannot open a browser, so it
says nothing about how a page behaves once loaded: no runtime DOM, no
contrast measured on rendered pixels, no keyboard trace. Those belong to
the neighbours in the table above.

It also does not rank anything. Emitting `sitemap.xml` and `llms.txt` makes
a site legible to crawlers and to language models; whether anybody arrives
is not something this package knows or should claim.

Report output as output, never as a verdict. "The lint found nothing" means
exactly that, not "this documentation is good".

---

## File patterns

`*.md` routes here when publication is the concern, and, per the
generalisation above, when such a file was just written. `*.html` routes
here only for `meta`, `narrate` and `readalong`; for anything about how the
markup behaves, route to sprezzature-accessibility or sprezzature-ux-laws.
