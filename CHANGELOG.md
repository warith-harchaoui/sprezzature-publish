# Changelog

All notable changes to `sprezzature-publish` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
