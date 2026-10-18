# Changelog

All notable changes to `sprezzature-publish` are documented here.
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
