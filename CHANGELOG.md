# Changelog

All notable changes to `sprezzature-publish` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **The two repairs a narrated page needs.** `build` writes a voice into a
  page and refuses to write one onto prose that moved while the recording
  was running. That net covers one order of events; two others happen and
  neither was covered.
  - **`--strip` takes the player back out.** The timings live in the page,
    one `data-start` per sentence, so editing the prose moves every sentence
    after the edit out from under its timestamp. The repair is to take the
    player out, edit, and record again, which needs a way to take the player
    out. Every caller was writing that by hand; on one site it was written
    from scratch three times in three days, and each rewrite walked into the
    same two traps. A pattern that stops at the first `</div>` cuts the
    player in half, because the player holds seven nested `<div>` of its
    own; and unwrapping a `<span class="ra-s">` by deleting the tag *and*
    its content silently deletes the sentence. Both are tested.
  - **`--check` reads a page that shipped.** Nothing fires when a page is
    edited after it has a voice. The markers stay, their times stay, and
    every one of them now points at the wrong sentence, which is worse than
    no highlight because it is confidently wrong. `--tolerate` names a
    string the comparison is allowed to find changed.
  - `strip` and `check` are exported from `sprezzature_publish` beside
    `build`, so a caller that builds a site in a loop can do all three
    without shelling out.

## [1.2.0] — 2026-10-18

### Added

- **What the voice says, where it differs from what the page shows.** A page
  is read with the eyes and a narration with the ears, and some of what is
  on a page is written for the eye alone. The cue keeps the page's words —
  so a read-along still highlights exactly what a reader sees — and only the
  string handed to the engine changes, carried in a new `say` field.
  - **Footnote markers are not spoken.** A superscript "1" is a signpost to
    the bottom of the page; read aloud it lands glued to the word before it,
    and "the Ralph technique one, after Ralph Wiggum" is a sentence about a
    version number. Judged by content rather than by class name — a `<sup>`
    whose whole content is a number, bare or bracketed, which is the
    convention Markdown, Wikipedia and hand-written HTML all share.
  - **Mathematics is read, not spelled.** `\(R = T_{BA} \circ T_{AB}\)`
    was spoken as "backslash, open parenthesis, R equals T underscore". It is
    now "R equals T B A composed with T A B" — in the language the page is
    written in, detected with `langdetect` through the shared `_lang`
    helper, because a French page read with English operator names is worse
    than silence. A language with no vocabulary is refused, not served
    English.
  - **A formula too tangled to spell out is narrated instead.** Above a
    complexity threshold, and only with `--ai-hints`, the local model is
    asked for a one-sentence reading through the `latex_caption` prompt this
    package already ships for screen-reader captions. The deterministic
    reading is the baseline, not a degraded mode: a model that fails, or
    that answers with LaTeX, costs nothing.
- **`--no-follow`** builds the player without the sentence highlight. A
  supported shape, not a degraded one: some readers who listen *and* read
  want to read ahead of the voice rather than be led by it.

### Changed

- **The player is a bar across the foot of the window.** At the foot and not
  the top, and that is the one placement decision with a reason rather than
  a taste behind it: pages that carry a narration usually also carry a
  sticky masthead, and a second sticky bar under the first stacks two chrome
  strips over the text. The foot is also where a thumb already is on a
  phone. One behaviour at every width, not an inline card that becomes a bar
  on scroll — that is two components to keep agreeing.
- **It is thin.** 53 px: the scrubber rides the bar's top edge instead of
  taking a row of its own, because a progress line is a line. The title
  truncates below 34rem and the speed control leaves below 22rem; the
  controls never shrink below their touch target.
- **The page keeps its last paragraph out from under the bar.** The bar
  measures itself and publishes `--ra-bar`; the stylesheet spends it as
  `padding-bottom`. Measured rather than assumed, because the height depends
  on the host page's font, and a guess a few pixels short hides the end of
  the article — the one place a reader will not think to look for a bar.
- **It remembers where the reader got to**, in `localStorage`, keyed by path
  so a campaign link's query string does not turn the same article into a
  different recording. A finished recording forgets its position, because
  "continue" that lands on the closing word is worse than starting over.
- **The colours come from the page.** `page_palette` reads the colours a
  page actually paints with — from its markup and from whatever stylesheets
  resolve to files beside it — and the player wears them. Two properties,
  because an accent usually has only one of its two jobs: `--ra-accent`
  fills the button and the progress, `--ra-tint` washes the bar and the
  highlight. When a page's accent is too pale to carry a fill, the fill
  takes the page's ink and the accent stays where it works — which is the
  page's own arrangement, a pale chip with dark type on it.

  The rule that makes this work: a colour on the right of a **custom
  property definition** is skipped, a colour inside a real declaration is
  kept. A framework default sitting on every rich-text block of a page gets
  counted thirty-one times otherwise, and the player ends up wearing a
  colour that appears nowhere on the page.

### Fixed

- `reading_meta_html` is `listening_meta_html`, and a formula's join no
  longer glues a digit to the word before it ("plus1").

## [1.1.0] — 2026-10-18

### Changed

- **The read-along player is a designed bar** rather than a native
  `<audio controls>` in a box: a round play button, the title beside it, a
  hairline scrubber, ±15 s, and a speed control. Progressive enhancement
  over the native element, which still ships visible and is hidden by the
  same attribute that reveals the bar — so there is no state in which a
  reader sees two players or none. Every control is a real `<button>` and
  the scrubber an `<input type="range">`, so the keyboard, touch and a
  screen reader's slider gestures all work because the browser implements
  them.
- **The caption under the player is one number, not two.** It read
  "45 min read · 64 min listen", which set an estimate beside a measurement
  and invited a comparison that can only come out one way — speech is
  slower than reading. The reading figure was also the weaker of the two: a
  word count times an assumed speed, against the narration's own length
  down to the sample. `reading_meta_html` is now `listening_meta_html` and
  takes no word count.
- **The right-hand clock counts down.** With the caption saying the length,
  a clock showing the total put the same number twice in a card the width
  of a paragraph. What changes while a recording plays is what is left.
- The total duration is written into the markup server-side, from the cues.
  With `preload="none"` the browser knows nothing about the file until the
  reader presses play, and `0:00` beside a sixty-four-minute recording is
  wrong at exactly the moment someone is deciding whether to commit to it.

- **The player has a colour.** `--ra-accent` is the one colour a host page
  is invited to set; everything else is still derived from the page's own
  text colour, which is the only thing a component injected into an unknown
  page can know. Its default is a teal, and the choice is a contrast
  calculation rather than a preference: the accent has to clear 3:1 — the
  threshold for a non-text interface element — against a light page *and* a
  dark one, and the obvious alternatives fail one side. It tints the play
  button, the progress fill, the card, and the read-along highlight itself,
  which is the surface a reader looks at for an hour.
- **The ±15 s buttons are legible.** Two earlier versions were not, and
  neither was visible in the markup — only at the size they are actually
  drawn. The first laid "15" over a filled disc and the two collided; the
  second opened the ring but drew it tight enough that the digits touched
  it, with the arrowhead sitting on the ring's own end.

### Fixed

- **`narrate_post` and `readalong` did not connect.** The first writes
  `narration.wav`; the second looked only for `<page-stem>.<ext>`, so for
  any page not called "narration" the audio was never found. A missing
  recording is deliberately not an error here — most pages are not narrated
  — so both commands exited 0 and the page simply came out without a
  player. They are documented one after the other in `readalong.py`'s own
  epilog.
- **The sibling-checkout fallback counted one directory too deep.** It was
  right while these scripts lived in the monorepo and wrong from the moment
  the package was extracted, resolving to a path outside the home
  directory. A fallback that cannot fire looks exactly like one that was
  never needed.
- **`sprezzature-publish-narrate` died on `--help`** without the `[prose]`
  extra, because the LLM client was imported at module load while
  `--ai-hints` is off by default. The one install shape the feature is
  named after — `[narrate]` — was the one that could not run it.

### Note

`kokoro` is now the default narration engine (see `sprezzature-audio`
1.3.0), and `--voice` left empty means the language of the text is detected
and the voice that speaks it is chosen.

## [1.0.0] — 2026-10-18

First release as a standalone package. The tools are not new — they have
built this suite's own site since the monorepo days — but until now they
could only be reached by someone who had cloned that repository.

### Added

- **Five surfaces over nine tools.** A library (`sprezzature_publish`), two
  front doors over the same table (`make-site` with argparse,
  `sprezzature-publish` with click) plus one command per tool, an HTTP API,
  an MCP server, and the `SKILL.md` that stays in the monorepo.
- **`Dockerfile` and `docker-compose.yml`**, always together. The compose
  file declares the port, the volume, the environment and the command; the
  local model server is a separate profile, because two tools of nine need
  it and someone who only wants pages should not be made to run one.

### Changed

- **The voices left.** Narration synthesis — the OpenVoice and Chatterbox
  wrappers, the voice chooser and the model installer — now ships with
  `sprezzature-audio`. Captions turn sound into timed text, narration turns
  text into timed sound: one package owns that modality in both directions.
  This one keeps the orchestrator, the read-along and the document parsing,
  and invokes the voices as subprocesses so their heavy imports never enter
  its graph.
- **The lint keeps zero dependencies.** That is the reason it is worth
  putting in a pre-commit hook, so everything heavier became an extra named
  after the tool that needs it: `[html]`, `[icons]`, `[lint]`, `[prose]`.
  `import sprezzature_publish` resolves its exports lazily for the same
  reason — a caller who only lints never imports Pillow.

### Fixed

- **Four exported names did not exist.** The first draft of the library
  surface advertised `lint_text`, `build_icons`, `narrate` and a `fix_file`
  that no module defined. Caught before the package was built, by checking
  every export against the source rather than trusting the list.
- **The render route would have returned 500 every time.** It read
  `conversion.out_path`; the renderer returns a `Conversion` carrying `dst`
  and `ok`. Caught by calling the route rather than by reading it.

[1.0.0]: https://github.com/warith-harchaoui/sprezzature-publish/releases/tag/v1.0.0
