# Measurement plan

How transition costs are measured: the plan, the trial protocol, and what
the data has shown so far. The *why* of the layout and the scoring model is
in [design-principles.md](design-principles.md). Claims marked *(guess)* have
no measurement behind them yet.

## Plan

Costs are attached to **transitions**, not positions: what a key costs
depends on where the hand comes from and goes next (e.g. index inner column
→ pinky outer column may be easy, while either reach is costly with a
neighbouring finger pressing). Measuring each key relative to the home row
would also be unrepresentative: in one-handed typing the fingers rarely
return to it. With ~20 positions there are ~400-500 directed transitions,
too many to measure one by one, so a model describes each transition by a
few features and is fitted to many varied sequences.

| Phase | What | Status |
|---|---|---|
| 1 finger baseline | home-row fingers + Space thumb: repeats, pairs, triples, rolls (37 patterns) | done, 3 sessions |
| 2a same finger, unanchored | two keys of one finger alternately (18 patterns) | done, 3 sessions |
| 3 word pilot | warm-up and cycle count for 4-6 key words | **next** |
| 4 word trials | transitions in varied contexts, fitted by a feature model | to do |
| 5 layer switch | cost of a layer-2 key inside a word | to do, design open |
| validation | type real text on 2-3 emulated candidate layouts, compare with prediction | to do |

Word trials replace the earlier phases 2b (same finger, anchored), 3
(off-home positions as differences against home-row cycles) and 4 (both keys
off home): those all measured relative to the home row.

### Phase 3: word pilot

`python3 measure/measure.py run --plan pilot-words`, then
`python3 analysis/measurements.py warmup`.

- 18 words, 6 each of 4, 5 and 6 keys, lengths interleaved, then the first
  word of each length again. Keys from rows 1-3, columns 1-6, plus Space;
  distinct keys, at least 3 fingers, at most one same-finger transition.
  Fixed seed, so the words are reproducible.
- 20 cycles per word (2-3× the usual), nothing discarded as warm-up, so the
  analysis can see when the cycle time settles. Keys are numbered on screen
  in typing order.
- Answers: how many warm-up cycles each length needs, how many measured
  cycles give a stable median, whether 6-key words are too hard to remember
  (errors, slow settling), and how well the same word agrees later in the
  session. Agreement across sessions is checked by repeated anchor words in
  phase 4.

### Phase 4: word trials

- **Words** of 5-6 keys (final length after the pilot), typed cyclically.
  Each word gives one cycle time (the sum of its transitions, wrap-around
  included) and one rating.
- **Related words.** A rating mostly reflects the word's worst transition,
  so words come in families sharing most keys: a base word and variants
  that change one key. Comparing family members localises both time and
  discomfort.
- **Sampling** covers all kinds of transitions, with extra words for the
  suspected strain sources below. A few anchor words repeat every session
  (session speed, repeatability).
- **Model:** cycle time = session factor × Σ transition costs; the cost of
  a transition is a function of its features. Ratings are fitted separately
  (probably driven by the worst transition). Cycle times can't separate a
  per-key offset from the transitions into and out of the key, but such an
  offset cancels in any long text, so it doesn't affect scores.
- **Size:** with 20-40 model parameters, ~200-300 words *(guess: ~10
  measurements per parameter)*, i.e. 8-13 sessions of ~10 min.
- **Check:** predict held-out words; look at residuals for skip-gram
  effects (the hand position after key *i* affecting key *i+2*).

### Transition features

Known from data:

- Finger pair: same finger, neighbours, distance between fingers.
- Direction: inward (towards the index) is much faster than outward.
- Same finger, different key: for index and middle distance barely
  matters; for the pinky it matters a lot.
- Thumb: Space after a finger is nearly simultaneous; a finger after Space
  costs ~120-140 ms.

Main strain sources (user's experience, to be targeted by sampling):

1. **Adjacent fingers moving to different rows.** Ring up and pinky down
   is bad; **ring down and pinky up is the worst**: the long ring finger
   curls while the short pinky reaches, and the pinky's top row needs a
   small hand shift, which in turn makes the bottom row harder for the
   other fingers.
2. **Reaching sideways to an outer column while a neighbouring finger is
   pressing:** index to the inner column (column 1) together with the
   middle finger; pinky to the outer column (column 6) together with the
   ring or middle finger. Index to the inner column together with the ring
   finger is no problem.
3. **Hand shifts.** Everything in the three core rows is reachable without
   moving the hand, except the pinky top row (slight shift) and the index
   inner column top row (`.`, slight). The number-row middle-finger key and
   the number-row pinky-column key reached with the ring finger need almost
   no shift, but combine very poorly with keys in the lower rows.

Candidate features from these: opposite row movement of adjacent fingers
(asymmetric: which finger goes up), a sideways reach while a neighbour
presses, and a "hand shifted" state for keys that need a shift, costly when
the neighbouring keys are in lower rows.

## Findings so far

From 169 protocol-2 trials, 6 sessions over 2 days (2026-11-19/20).
Recompute with `python3 analysis/measurements.py report`.

- **The protocol works.** No speed-up within a trial (second half vs first
  half: ~1 ms). Spread across sessions: median 5-8% for repeats, pairs and
  triples; ~15% for 4-key rolls, which were still being learned
  (`n r l h`: 851 → 582 → 562 ms).
- **Session speed varies.** In phase 2a whole sessions ran 8% slower and
  9% faster than average; controls track it (`n r` 225 vs 179 ms).
  Correcting for it halves the phase-2a spread (8.7% → 4.3%); phase-1
  sessions hardly differed, so there it changes nothing. The fit needs a
  per-session factor.
- **Two-key cycles of different fingers are trills, not typing.** A
  triple takes on median 1.36× the sum of its pairs' half-cycles (1.0×
  for inward orders, up to 1.7× for outward ones); pairs roll over in
  60-99% of transitions. Different-finger transitions need cycles of 3+
  keys.
- **Use whole-cycle times, not the per-transition splits.** The time of a
  transition within a cycle depends strongly on the rest of the cycle
  (median range 75 ms across triples, vs 30 ms within-trial noise), e.g.
  `h→r` is 268 ms after the outward roll `r l h` and ~90 ms elsewhere.
- **Inward ≫ outward.** `n l r` 335 ms vs `n r l` 447; inward 4-finger
  roll ~380 vs outward ~570. A bigram model fitted on the triples predicts
  the inward roll too slow (467), so rolls carry a trigram bonus.
- **Fingers:** same-key repeats: index 131, middle 139, ring 149, Space
  150, pinky 172 ms. The ring-pinky pair `l h` is the worst home-row pair:
  about as fast as a same-finger index move but rated 4 (matches the felt
  strain).
- **Same finger, different key (2a), per move:** index and middle 150-185
  ms, rated 1-2, distance barely matters; ring 170-225 ms, rated 2-3;
  pinky adjacent keys 195-255 ms, rated 3-4; pinky top↔bottom and outer
  column 265-290 ms, rated 4.
- **Ratings correlate with time (r = 0.65 on pairs) but not fully:** they
  separate the pinky more sharply, so they add information.

## Protocol

- **Measured on layer 4**, the layer currently used for typing, so key
  positions are familiar. Since 2026-11-19 it has no dual-use keys (they
  emit on release, which would distort timing). Palm and r0c1 send nothing
  there, so they can't be measured.
  - Caveat: sequences frequent in current layer-4/5 typing may come out
    faster due to practice (layout in use for ~2 months).
- **Trial:** highlighted keys typed cyclically, as if part of a word:
  separate presses, not an oscillation and not a sprint.

  | Keys | 1 | 2 | 3 | 4 | 5-6 |
  |---|---|---|---|---|---|
  | cycles | 30 | 20 | 13 | 10 | after the pilot |
  | warm-up cycles | 8 | 5 | 3 | 3 | after the pilot |

- **Main measure is the cycle time** (one pass through the pattern).
- **Timing** from kernel input events (`/dev/input`), press-to-press.
  Releases are logged too (hold time, rollover). Rollover is normal in
  comfortable sequences (the old keylogs show it too).
- **Errors:** a wrong key invalidates the transition into it; error counts
  are kept as an additional cost signal.
- **Discomfort rating** after every trial, on the top row `. u i o b`:
  1 effortless · 2 fine · 3 some effort · 4 uncomfortable · 5 strain.
- **Control trials** (`n r` and the inward roll `h l r n`) at the start and
  end of every session track drift, fatigue and session speed.
- **Repeatability:** phases 1-2a measured every pattern in 3 sessions (at
  most once per session); word trials use anchor words instead.
- **Stretches and breaks:** 3-minute stretches (pauses not counted), then a
  30 s break with a countdown; continue or finish with the end controls;
  at most 5 stretches.
- **Measuring only while the terminal is focused.** Switching away pauses
  the trial; key presses elsewhere are ignored.
- **Keylogs:** pause keystats during sessions; as a safeguard, keylog
  events inside session time windows are dropped from typing statistics.
- Protocol 1 (the first 44 trials, 2-key cycles over all positions) is
  exploratory only: off-home 2-key loops let the hand reposition and slide
  into oscillation (50-90 ms speed-ups within a trial).

## Why not use timings from everyday typing

Analysis of the 2025 two-handed logs (`analysis/legacy_right_hand_timings.*`,
right-hand-only bigrams on the layer-0 layout) showed:

- Times *into* Backspace are ~400 ms regardless of position: that is
  error-noticing time, not motor cost. Everyday typing mixes in thinking and
  reaction time.
- Within the same movement category times range from 60 to 230 ms; frequent
  bigrams (`in`, `on`, `ni` ~62 ms) are fast, probably because they're
  practised (or easy movements are the frequent ones).
- Still, the rough pattern is a useful sanity check: different fingers
  ~125-160 ms, same finger different key ~165-195 ms, inward rolls faster
  than outward ones.
