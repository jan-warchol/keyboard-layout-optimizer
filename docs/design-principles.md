# One-handed Model 100 layout: design principles

A living document. Add principles, decisions and open questions as we learn.
Each decision records *why*, so it can be revisited when the reason changes.

## Goal and constraints

- **Type everything with the right hand** on a Keyboardio Model 100.
  Using the left hand again is a stretch goal, not a design input.
- **Comfort first, speed second.** The motivation is health; a layout that
  is fast but straining is a failure.
- **Fully programmable keyboard** (Kaleidoscope / Chrysalis): any key can
  send anything, layers and dual-use keys are available.
- **Languages and content:** Polish, English, shell commands, code. Polish
  diacritics (ą ć ę ł ń ó ś ź ż) total ~2% of typed characters.

## Lessons from previous attempts

| Attempt | Idea | Why it failed |
|---|---|---|
| Layers 4/5 | Half the letters per layer, switched with the palm key | Pressing the palm key moves the whole hand and breaks the flow of typing |
| Layer 7 | All letters on the base layer (4 rows × 6 columns) | Jumps between keys too big (number row, outer pinky column) |

→ **Principle:** we're aiming between these two: more letters on the base layer than
layers 4/5, but avoiding layer 7's large jumps. *How many* letters belong on the
base layer is a question for measurement, not a guess.

## Layout structure

### Pinned keys (decisions, not measured costs)

Fixed by preference to shrink the search; the reason is recorded so the pin
can be lifted if it turns out wrong.

- **Inner index-stretch column (3 keys):** Enter, Backspace, Tab and similar
  non-letter keys.
- **Outer pinky column, bottom key:** `/` and `\`. Close to the normal
  position, and it has worked well in practice. Too awkward for letters in
  fast typing.
- **Outer pinky column, middle two keys:** comfortable, letter candidates.
- **Number row:** the index-finger keys (6 and 7 positions) and the
  ring-finger key are hard to reach. The middle-finger key is reasonable;
  the pinky-column key is easy to reach *with the ring finger* (how reliably
  is still open).
- Resulting base-layer letter slots: 15 (columns 6-0, rows 1-3) + 2 (outer
  pinky middle) + 2 (number row middle, pinky-column) ≈ 19, or 18 if Space
  goes into the grid. So the base layer holds roughly 13-20 letters; the
  rest go to the second letter layer.

### Thumb keys and modifiers

- **Space is not required to be on a thumb key.** Thumb keys are scarce
  and needed for held modifiers: Ctrl (most shortcuts), Shift, the
  second-letter-layer key (AltGr-like), plus Super and Alt somewhere. Space
  is the only usual thumb key that is never held together with others, so
  it is the natural candidate to move into the grid. Layouts with Space in
  the grid felt odd in earlier experiments, but are not ruled out; the
  optimizer compares both (phase 1 measures the Space thumb, so costs are
  comparable).
- **Adjacency on the thumb arc matters.** Two adjacent thumb keys can be
  pressed together by the thumb without trouble, so modifier pairs that are
  used together (Ctrl+Shift, Ctrl+layer) must be adjacent. A third key can
  be added by pressing the rightmost thumb key with the index finger, but
  only when the letter being combined isn't pressed by the index finger.

### Second letter layer

- **Polish letters sit under their Latin letters** (ą under a, ł under l,
  …, ź under x as in Polish programmer layout). Intuitive, and a starting
  point rather than a final decision. The other layer-2 positions hold the
  letters that don't fit the base layer, plus other characters.
- **Not a hard constraint.** Rearrangements of this kind have worked in
  the past, so the optimizer may move a Polish letter elsewhere on layer 2,
  e.g. when its Latin letter ends up on layer 2 itself. Keeping the mapping
  is a preference (a bonus or penalty in the score), not a rule.
- **z on the base layer is a hard constraint** (common in Polish and in
  shortcuts: Ctrl+Z; ~90% sure it belongs there anyway).
- **x:** a base-layer candidate because of Ctrl+X (cut), not because of ź.
- Model: cost(ą) = layer cost + cost of a's position (when the mapping is
  kept).

### Palm key: a modal layer for navigation and numbers

- The palm key fails for letters (layers 4/5) because pressing it for one
  key, releasing and pressing again moves the whole hand. It works well
  when **held for a stretch of related actions**; it served well for arrows
  and other non-printing keys in the default layout.
- So the palm layer is for *modes* that aren't interleaved with letters:
  **cursor movement/editing** and **numbers** (digits plus `.` and `,`, which
  is what number entry usually needs). Numbers won't fit on the base layer,
  and on the second letter layer they'd end up scattered in unrelated
  positions.

## Scoring model

1. **Measure, don't guess.** Costs come from timed trials on the actual
   keyboard plus a subjective discomfort rating, not from generic heuristics
   designed for two-handed typing.
2. **Bigrams first, trigrams later.** Score =
   Σ frequency(a→b) × cost(pos_a → pos_b). With one hand every bigram is same-hand,
   so two-hand metrics (alternation, hand balance) don't apply.
   Trigram terms are added for selected 3-key patterns once the bigram model
   exists, where measured trigram time differs from the sum of its bigrams.
3. **Cost combines speed and discomfort.** Speed is a good proxy for
   comfort but misses strain (e.g. fast pinky stretches). The exact combination
   is still open (see below).
4. **Positions, not fingers.** The cost is attached to physical positions;
   which finger presses a key is whatever is natural, and is captured by the
   measurement implicitly.
5. **Fit a model, don't just look up the table.** Measured costs are smoothed by a model
   (finger relationship, row/column distance, direction) so that noisy or
   unmeasured pairs get sensible estimates.

## Measurement methodology

- **Measurement layer** (layer 1, entered with palm + outer home key, left
  top-inner key exits): each of the 32 right-half keys sends a unique key.
  It mirrors layer 4 (the layer currently used for typing) so key positions
  are familiar, except: dual-use keys become plain taps (they emit on
  release, which would distort timing), number-row arrows become digits 1-5
  (also used for ratings), unused thumb key and palm get `x` / `z`.
  Generated by `measure/make_measurement_layer.py`.
  - Since 2026-11-19 layer 4 itself has no dual-use keys and sends the
    same keys (only the number row, t1 and palm differ), so measuring
    directly on layer 4 is equivalent and avoids switching layers. Palm and
    r0c1 send nothing there, so they can't be measured on layer 4.
  - Caveat: sequences that are frequent in current layer-4/5 typing may
    come out a bit faster due to practice. That layout has been in use for
    about 2 months; watch for practice effects when fitting the model.
- **Trial:** 1-4 highlighted keys typed cyclically (1 2 1 2 … or
  1 2 3 1 2 3 …): 30 presses for single-key repeats, 20 cycles for pairs,
  13 for triples, 10 for 4-key sequences. Warm-up is at least 8 presses
  (8 / 5 / 3 / 3 cycles). Instruction: *type it as if it were part of a
  word*: separate presses, not a back-and-forth oscillation and not a sprint.
  Self-paced: no metronome, since the natural pace differs per combination.
- **Main measure is the cycle time** (one pass through the pattern). The
  inward/outward split within a cycle is kept: it matches the felt
  difference (inward presses can be timed precisely; outward ones need a
  bigger gap to avoid a simultaneous press). Whether the cyclic context
  exaggerates it is checked with triples, where each transition appears
  in more than one context.
- **Timing** from kernel input events (`/dev/input`), press-to-press.
  Releases are logged too (hold time, overlap/rollover).
- **Errors:** a wrong key invalidates the transition into it; error counts
  are kept as an additional cost signal.
- **Discomfort rating** after every trial, on the top row `. u i o b`
  (same keys on both layers):
  1 effortless · 2 fine · 3 some effort · 4 uncomfortable · 5 strain.
  The selected rating is shown and must be confirmed with Space or Enter.
- **Control trials** (`n r` and the inward roll `h l r n`) at the start
  and end of every session track drift and fatigue.
- **Repeatability:** every pattern is measured in 3 different sessions
  (at most once per session), so day-to-day spread can be compared with
  the differences between patterns.
- **Rollover is not a sign of a wrong typing mode.** Comfortable pairs
  overlap in normal typing too (the old keylogs show it). Release times are
  logged; the *length* of the overlap may still distinguish a deliberate
  roll from an oscillation, which is to be analysed.
- Break reminder every 13 minutes.

### Phases: fingers first, positions later

Two-key cycles away from the home row turned out unrepresentative
(protocol 1, the first 44 trials, kept as exploratory data only):

- With two off-home keys typed alternately, the hand shifts to a position
  that suits that pair, which it wouldn't do in text where the next key can
  be anywhere. E.g. the cost of `.`→`r` is the index reaching while the
  middle finger stays anchored; a 2-key loop lets the hand avoid that.
- Within a trial the typist can switch from separate presses to a fast
  oscillation (faster, more errors, not like typing). Unfamiliar pairs sped
  up by 50-90 ms between the first and second half of a trial.

So measurement proceeds from the simplest movements:

1. **Finger baseline** (`measure.py run --plan phase1`): home-row index,
   middle, ring, pinky (`n r l h`) and the Space thumb. Same-key repeats (5),
   finger pairs (10), finger triples in both cyclic orders (20), inward and
   outward 4-finger rolls (2): 37 patterns × 3 sessions.
2. **Same finger, different keys.**
   a. *Unanchored* (`--plan phase2a`): two keys of one finger typed
      alternately, the hand free to settle into a comfortable position.
      Vertical (top-home, home-bottom, top-bottom) for index..pinky,
      horizontal (inner/outer column, each row) for index and pinky:
      18 patterns. Measures the finger's own movement; not a typing cost
      by itself.
   b. *Anchored* by a home-row key on another finger (e.g. `n u r`) so the
      hand can't shift. The difference from 2a is the stretch penalty of
      moving one finger while the others stay.
3. **Off-home positions as differences:** replace one key of a home-row
   cycle with an off-home key on the same finger (`n r l r` → `. r l r`);
   the change in time and rating is the cost of that position in context.
   Sequences of 4+ keys for anything off the home row.

The model then combines finger-pair costs (phase 1) with per-position
extra costs (phases 2-3).

### Why not use timings from everyday typing

Analysis of the 2025 two-handed logs (`analysis/legacy_right_hand_timings.*`,
right-hand-only bigrams on the layer-0 layout) showed:

- Times *into* Backspace are ~400 ms regardless of position: that is
  error-noticing time, not motor cost. Everyday typing mixes in thinking and
  reaction time.
- Within the same movement category times range from 60 to 230 ms; frequent
  bigrams (`in`, `on`, `ni` ~62 ms) are fast because they're practised. Practice
  effects outweigh the movement itself.
- Still, the rough pattern is useful as a sanity check: different fingers
  ~125-160 ms, same finger different key ~165-195 ms, inward rolls
  (towards the index) faster than outward ones.

## Corpus and weighting

- **What is typed by hand is what counts.** Most code is written by agents
  and longer prose is dictated; hand typing is short corrections, a few
  words where dictation doesn't integrate, shell commands, and editing /
  cursor movement (the hardest to cover by dictation).
- **Weights come from the keylogs, not from guesses about content types.**
  Keystats logs record focus changes (`# focus {"app": ...}`), so typing
  can be split by context (terminal, editor, browser). Dictated text,
  agent-written code and pasted text never reach the keylog, so the log
  already reflects the real mix.
  - The current logs are on the layer-4/5 layout, in use for ~2 months.
    They are small so far (~8k presses over 3 days, much of it measurement
    trials). The 2025 logs are bigger but from two-handed typing with
    little dictation, so their mix is different.
- **Corpora fill in the bigram statistics**; the keylogs set proportions.
  Rare bigrams barely affect the base layer (the score is dominated by the
  few hundred most frequent bigrams), so the point of corpora isn't the rare
  tail; it's stable estimates of the common bigrams, which a few thousand
  logged presses don't give.
- Sources: keystats logs, shell history, text and code samples to be
  provided. Final weighting is still checked by running the optimizer with
  different weightings and comparing the resulting layouts.

### Shortcuts are a separate frequency table

- Letter frequency in text underrates letters used in shortcuts (V is
  rare in text but Ctrl+V is very frequent; same for Z, C, S, W…).
  Count *letter pressed with Ctrl/Alt/Super held* from the keylogs as a
  second table, scored alongside the text bigrams.
- A shortcut on a layer-2 letter needs Ctrl + layer key + letter: possible
  with adjacent thumb keys, but less obvious and more effortful.
  Frequent shortcut letters should earn base-layer places.
- One-shot modifiers would remove the need to stack held keys, but it's
  unknown how well they suit the user (who is used to chording). To be tried.

### Shell history: notes for processing

Years of history exist; location to be confirmed (`~/.bash_history` here
has only 14 lines). Raw history overstates what is actually typed, so filter:

- **Autocompletion:** for tokens that are paths, filenames, git branches or
  long command names, keep only the first 2-3 characters of each path
  component, followed by Tab.
- **Pasted text:** drop tokens that look pasted: URLs, hashes, UUIDs,
  very long tokens.
- **Recalled commands:** collapse consecutive duplicates and cap how often
  one command counts; repeats are mostly recalled with Up / Ctrl-R, not
  retyped.
- **Check the filters:** compare character and bigram frequencies of the
  filtered history against keystats logs captured while the terminal was
  focused.

## Open questions

- How to combine time, rating and error rate into a single cost.
- Does cyclic `ABAB` timing represent `A→B` inside real text well enough?
  (Check with trigram trials and with typing tests on candidate layouts.)
- Space on a thumb key vs in the grid; which modifiers get the thumb keys,
  in which order on the arc; where Super and Alt go.
- **Layer-switch cost needs its own experiment.** Proposal: word-like
  cycles with one layer-2 key inside (`n [L+r] l`) vs the same cycle on the
  base layer (`n r l`); the difference is the switch cost in context. Run
  with a held layer key and a one-shot layer key, and add Ctrl + layer +
  letter for shortcuts.
- One-shot vs chorded modifiers (see shortcuts).
- How reliable is reaching the pinky-column number key with the ring finger?
- Does x earn a base-layer slot through Ctrl+X (cut)? The shortcut table
  will tell.
- Editing and navigation volume (arrows, Home/End, word jumps,
  Ctrl+Backspace): measure from keylogs to size the palm layer.

## Decision log

- 2026-11-18 — Score from measured bigram costs (time + rating), trigrams
  added selectively later. Include number row and outer pinky column in
  measurements. Corpus weighting decided after experiments.
- 2026-11-18 — First 36 trials collected (core block). Data collection
  paused: review whether the measurement method is reliable before
  collecting more (some results look odd, to be articulated).
- 2026-11-19 — Protocol 2: 2-key cycles off the home row are unreliable
  (hand re-positions, typing mode switches). Start with a finger baseline
  on the home row + Space thumb, measured in 3 sessions; off-home positions
  later, in longer sequences and as differences against home-row cycles.
  Inward/outward asymmetry treated as real. No pacing guide.
- 2026-11-19 — Layout structure: inner index column for Enter/Backspace/Tab,
  bottom outer pinky key for `/` `\`; Space may go into the grid (thumb keys
  are needed for modifiers); Polish letters under their Latin letters on the
  second letter layer (a preference, not a rule), z pinned to the base
  layer; palm key = held modal
  layer for navigation and numbers. Weighting from keylogs (by focused app),
  shortcuts counted as a separate table.
