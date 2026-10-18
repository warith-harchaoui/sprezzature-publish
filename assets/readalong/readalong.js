/* readalong — follow the narration, sentence by sentence.
 *
 * The whole module is about forty lines of logic. That is the point: the
 * cues come from a WebVTT file the browser parses itself through `<track>`,
 * so there is no parser here, no timer polling `currentTime`, and no clock
 * of our own to drift away from the audio.
 *
 * Accessibility decisions, each deliberate
 * ----------------------------------------
 * - The highlight is visual only. No live region, no `aria-current`: this
 *   feature exists for readers who are *looking* at the page, and announcing
 *   every sentence would make the page hostile to anyone on a screen reader,
 *   who already has speech and does not need a second voice.
 * - Auto-scroll is instant under `prefers-reduced-motion`, not suppressed.
 *   Smooth scrolling is the vestibular trigger; a jump is not animation, and
 *   removing the scroll entirely would leave a reader hunting for the
 *   highlight they asked to follow.
 * - Scrolling happens only when the sentence is off screen, so a reader who
 *   has scrolled ahead is not dragged back on every cue.
 * - Sentences are focusable and activate on Enter or Space as well as click,
 *   so seeking by sentence is reachable without a mouse.
 * - The designed controls are a `<button>` and an `<input type="range">`,
 *   not divs with drag handlers. Arrow keys, Home/End, touch, and the
 *   screen-reader's own slider gestures then work because the browser
 *   implements them, not because this file remembered to.
 * - The bar is unhidden here and the native `<audio controls>` hidden in the
 *   same breath. Shipping it visible would mean a reader with no JavaScript
 *   sees a play button that does nothing; shipping the native element hidden
 *   would mean they see no player at all.
 * - Every word the controls speak is written into the markup by the
 *   generator, which has the language table. Nothing here builds a string a
 *   reader hears.
 */

const CLOCK = (seconds) => {
  const total = Math.max(0, Math.floor(seconds || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n) => String(n).padStart(2, '0');
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${m}:${pad(s)}`;
};

/* The controls. Returns without enhancing if the markup is not there, so an
 * older page that still has the plain player keeps working. */
function wireControls(root, audio) {
  const ui = root.querySelector('[data-ra-ui]');
  const play = root.querySelector('[data-ra-play]');
  const scrub = root.querySelector('[data-ra-scrub]');
  const elapsed = root.querySelector('[data-ra-elapsed]');
  const totalOut = root.querySelector('[data-ra-total]');
  if (!ui || !play || !scrub || !elapsed) return;

  // Declared duration first: `preload="none"` means the browser knows
  // nothing about the file until play, and `0:00` beside a sixty-four-minute
  // recording is wrong exactly when a reader is deciding to commit to it.
  let duration = Number.parseFloat(root.dataset.raDuration) || 0;
  const skip = Number.parseFloat(root.dataset.raSkip) || 15;
  const rates = (root.dataset.raRates || '1')
    .split(',')
    .map(Number.parseFloat)
    .filter((r) => r > 0);

  ui.hidden = false;
  root.setAttribute('data-ra-enhanced', '');

  let scrubbing = false;

  function paint() {
    const at = audio.currentTime || 0;
    const span = duration || audio.duration || 0;
    elapsed.textContent = CLOCK(at);
    if (totalOut && span) totalOut.textContent = CLOCK(span);
    if (scrubbing || !span) return;
    const ratio = Math.min(1, at / span);
    scrub.value = String(Math.round(ratio * 1000));
    root.style.setProperty('--ra-progress', String(ratio));
    // The slider's value is a thousandth of a recording, which is not a
    // thing anyone can picture. What a screen-reader user needs announced is
    // the time, so that is what is announced.
    scrub.setAttribute('aria-valuetext', CLOCK(at));
  }

  // The measured duration wins once the file says what it is: the declared
  // one comes from the cues, and a recording trimmed after the fact would
  // leave the two disagreeing.
  audio.addEventListener('loadedmetadata', () => {
    if (Number.isFinite(audio.duration) && audio.duration > 0) {
      duration = audio.duration;
    }
    paint();
  });
  audio.addEventListener('timeupdate', paint);

  play.addEventListener('click', () => {
    if (audio.paused) audio.play();
    else audio.pause();
  });

  const showState = () => {
    const playing = !audio.paused && !audio.ended;
    if (playing) play.setAttribute('data-ra-playing', '');
    else play.removeAttribute('data-ra-playing');
    // The label and the glyph move together. A button that looks like pause
    // and announces "Play" is worse than either alone.
    const label = playing ? play.dataset.raLabelPause : play.dataset.raLabelPlay;
    if (label) play.setAttribute('aria-label', label);
  };
  ['play', 'pause', 'ended'].forEach((event) =>
    audio.addEventListener(event, showState),
  );
  showState();

  const seekTo = (seconds) => {
    const span = duration || audio.duration || 0;
    audio.currentTime = Math.max(0, Math.min(span || seconds, seconds));
    paint();
  };

  // `input` and not `change`: the fill and the clock follow the thumb while
  // it is dragged, which is the feedback that makes a sixty-minute scrubber
  // usable at all.
  scrub.addEventListener('input', () => {
    scrubbing = true;
    const span = duration || audio.duration || 0;
    const at = (Number.parseFloat(scrub.value) / 1000) * span;
    root.style.setProperty('--ra-progress', String(Number(scrub.value) / 1000));
    elapsed.textContent = CLOCK(at);
    scrub.setAttribute('aria-valuetext', CLOCK(at));
  });
  scrub.addEventListener('change', () => {
    const span = duration || audio.duration || 0;
    scrubbing = false;
    seekTo((Number.parseFloat(scrub.value) / 1000) * span);
  });

  const back = root.querySelector('[data-ra-back]');
  const forward = root.querySelector('[data-ra-forward]');
  if (back) back.addEventListener('click', () => seekTo(audio.currentTime - skip));
  if (forward) {
    forward.addEventListener('click', () => seekTo(audio.currentTime + skip));
  }

  const rate = root.querySelector('[data-ra-rate]');
  if (rate && rates.length) {
    let index = 0;
    rate.addEventListener('click', () => {
      index = (index + 1) % rates.length;
      audio.playbackRate = rates[index];
      // `×` as the multiplication sign, not the letter x: a screen reader
      // reads the letter aloud. The button's accessible name is the
      // generator's "Playback speed" either way, so this text is for eyes.
      rate.textContent = `${rates[index]}\u00d7`;
    });
  }

  paint();
}

const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)');

function isOffScreen(element) {
  const box = element.getBoundingClientRect();
  return box.top < 0 || box.bottom > window.innerHeight;
}

function reveal(element) {
  if (!isOffScreen(element)) return;
  element.scrollIntoView({
    block: 'center',
    behavior: REDUCED_MOTION.matches ? 'auto' : 'smooth',
  });
}

function wire(root) {
  const audio = root.querySelector('[data-ra-audio]');
  const track = audio && audio.textTracks && audio.textTracks[0];
  if (!audio || !track) return;

  // `hidden` rather than `showing`: the cues drive a highlight, they are not
  // a caption overlay. A `metadata` track shown over an audio element would
  // be noise, but it still has to be non-`disabled` for `cuechange` to fire.
  track.mode = 'hidden';

  wireControls(root, audio);

  const sentences = document.querySelectorAll('.ra-s');
  let current = [];

  // The highlight is only ever *moved*, never cleared on the way past. Two
  // reasons, both of them things the narration does on purpose:
  //
  // - Between cues there is silence, because the timeline puts a pause after
  //   a heading and between list items. Clearing on `!cue` made the
  //   highlight blink off in every one of those gaps.
  // - Some cues have no sentence of their own. "End quote." is spoken and
  //   never written, so there is no `ra-N` to find; the reader is still
  //   inside the quotation, which is exactly where the highlight belongs.
  track.addEventListener('cuechange', () => {
    const cue = track.activeCues && track.activeCues[0];
    if (!cue || !/^\d+$/.test(cue.id)) return;
    // The sentence is found by id, as it always was. Almost every sentence is
    // one span and stops there.
    const head = document.getElementById(`ra-${cue.id}`);
    if (!head || head === current[0]) return;
    // The exception: markup the page already had can close between two of a
    // sentence's words -- a citation that ends mid sentence and hands over to
    // a note -- and no element can close a tag it did not open. Such a
    // sentence is several spans, marked with the cue they share, and they
    // light up together so they read as the one sentence they are.
    const next = head.dataset.raCue
      ? Array.from(document.querySelectorAll(`[data-ra-cue="${cue.id}"]`))
      : [head];
    current.forEach((part) => part.classList.remove('is-reading'));
    next.forEach((part) => part.classList.add('is-reading'));
    reveal(next[0]);
    current = Array.from(next);
  });

  // Click or keyboard on a sentence seeks the audio to it. `data-start` is
  // written by the generator from the same timeline that laid out the audio,
  // so this needs no lookup and cannot drift from the cue.
  const seek = (element) => {
    const start = Number.parseFloat(element.dataset.start);
    if (Number.isNaN(start)) return;
    audio.currentTime = start;
    if (audio.paused) audio.play();
  };

  sentences.forEach((sentence) => {
    // One tab stop per sentence, not per run: the later runs of a split
    // sentence seek to the same place, so making each its own stop would pad
    // the tab order with duplicates. They stay clickable.
    sentence.tabIndex = sentence.id ? 0 : -1;
    sentence.addEventListener('click', () => seek(sentence));
    sentence.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' && event.key !== ' ') return;
      event.preventDefault();  // Space would scroll the page
      seek(sentence);
    });
  });

  // Leaving the highlight behind when playback stops would say the reader is
  // still at a sentence they are not.
  audio.addEventListener('ended', () => {
    current.forEach((part) => part.classList.remove('is-reading'));
    current = [];
  });
}

document.querySelectorAll('[data-readalong]').forEach(wire);
