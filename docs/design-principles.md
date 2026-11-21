# One-handed Model 100 layout: design principles

A living document. Add principles, decisions and open questions as we learn.
Each decision records *why*, so it can be revisited when the reason changes.

Claims marked *(guess)* have no measurement or analysis behind them yet:
treat them as hypotheses to check, not as facts to build on. Claims based
on the user's long-term experience with a layout say so.

## Goal and constraints

- **Type everything with the right hand** on a Keyboardio Model 100.
  Using the left hand again is a stretch goal, not a design input.
- **Comfort first, speed second.** The motivation is health; a layout that
  is fast but straining is a failure.
- **Fully programmable keyboard** (Kaleidoscope / Chrysalis): any key can
  send anything, layers and dual-use keys are available.
- **Languages and content:** Polish, English, shell commands, code.

## Lessons from previous attempts

| Attempt | Idea | Why it failed |
|---|---|---|
| Layers 4/5 | Letters from the left hand added as another layer, switched with the palm key | Too much layer switching, and pressing the palm key moves the whole hand and breaks the flow of typing |
| Layer 7 | All letters on the base layer (4 rows × 6 columns) | Jumps between keys too big (number row, outer pinky column), key placement not optimized |

→ **Principle:** we're aiming between these two: more letters on the base layer than
layers 4/5 (and more frequent ones), but avoiding layer 7's large jumps. *How many*
letters belong on the base layer is a question for measurement, not a guess.

## Layout structure

Three layers, each with a different role:

- **Base layer:** the most frequent letters and symbols.
- **Second letter layer** (a held thumb key, AltGr-like): the remaining
  letters, Polish letters, less frequent symbols.
- **Palm layer** (held for a stretch of related actions): navigation,
  editing and numbers.

Pins below are fixed by preference to shrink the search; the reason is
recorded so a pin can be lifted if it turns out wrong. Judgements about
which keys are comfortable or hard to reach are by feel; word trials measure
them.

### Base layer

- **Letter slots:** 15 (columns 6-0, rows 1-3) + 2 (outer pinky column,
  middle keys: comfortable) + 2 (number row: the middle-finger key, and
  the pinky-column key reached *with the ring finger*, how reliably is
  still open) = 19, or 18 if Space goes into the grid. Letters share them
  with the most frequent symbols, so the base layer holds roughly 15-19
  letters.
- **Pinned: inner index-stretch column (3 keys)** holds Enter, Backspace,
  Tab and similar non-letter keys.
- **Pinned: outer pinky column, bottom key** holds `/` and `\`. Close to
  the normal position, and it has worked well in practice (experience).
- **Hard-to-reach keys are not wasted.** The number-row keys under the
  index finger (6 and 7 positions) and the ring finger are too awkward for
  letters in fast typing, but a single awkward press can still beat a
  layer switch for a moderately frequent symbol. They are candidates for
  punctuation, as the bottom outer pinky key already is for `/` `\`.
- **z is pinned to the base layer** (common in Polish and in shortcuts:
  Ctrl+Z; ~90% sure it belongs there). **x** is a candidate because of
  Ctrl+X (cut), not because of ź.

### Symbols

- **Placed together with letters**, not filled in afterwards. Shell and
  code use `- _ . , ' " | ~ $ = ( ) :` a lot; some of them are more
  frequent than some letters *(guess; the keylog frequencies will tell)*,
  so they compete for the same base-layer slots. The frequency statistics
  already include all characters.
- **Shifted symbols may get their own keys.** With digits on the palm
  layer, `! @ # $ % ^ & * ( )` lose their usual home (Shift + digit), and
  some are quite frequent. The same applies to any symbol pair whose
  unshifted symbol ends up on layer 2: if `[` is there, `{` would need
  Shift + layer key + key, which may be too much. So shifted symbols are
  placed individually, not automatically paired with their unshifted
  counterpart.
- **Symbols in shortcuts** (e.g. Ctrl+/, Ctrl+-, Ctrl+=): stacking a layer key
  on top of a modifier is undesirable but probably hard to avoid in most cases.
- Shifted characters (capitals, shifted symbols) cost a held Shift on the
  thumb, sometimes together with the layer key; the score has to account
  for it (not implemented yet).

### Second letter layer

- **Polish letters sit under their Latin letters** (ą under a, ł under l,
  …, ź under x as in Polish programmer layout). Intuitive, and a starting
  point rather than a final decision. The other layer-2 positions hold the
  letters that don't fit the base layer, plus symbols.
- **Not a hard constraint.** Rearrangements of this kind have worked in
  the past (experience), so the optimizer may move a Polish letter
  elsewhere on layer 2, e.g. when its Latin letter ends up on layer 2
  itself. Keeping the mapping is a preference (a bonus or penalty in the
  score), not a rule.

### Palm layer: navigation and numbers

- The palm key fails for letters (layers 4/5) because pressing it for one
  key, releasing and pressing again moves the whole hand. It works well
  when **held for a stretch of related actions**; it has served well for
  arrows and other non-printing keys for years (experience).
- So the palm layer is for *modes* that aren't interleaved with letters:
  **cursor movement/editing** and **numbers** (digits plus `.` and `,`,
  which is what number entry usually needs *(guess)*). Numbers won't fit on
  the base layer, and on the second letter layer they'd end up scattered
  in unrelated positions.

### Thumb keys and modifiers

- **Space is not required to be on a thumb key.** Thumb keys are scarce
  and needed for held modifiers: Ctrl (most shortcuts), Shift, the
  second-letter-layer key, plus Super and Alt somewhere. Space is the only
  usual thumb key that is never held together with others, so it is the
  natural candidate to move into the grid. Layouts with Space in the grid
  felt odd in earlier experiments, but are not ruled out; the optimizer
  compares both. Phase 1 measured the Space thumb with home-row keys only;
  word trials include Space with all positions.
- **Adjacency on the thumb arc matters.** Two adjacent thumb keys can be
  pressed together by the thumb without trouble, so modifier pairs that are
  used together (Ctrl+Shift, Ctrl+layer) must be adjacent. A third key can
  be added by pressing the rightmost thumb key with the index finger, but
  only when the letter being combined isn't pressed by the index finger.

## Scoring model

1. **Measure, don't guess.** Costs come from timed trials on the actual
   keyboard plus a subjective discomfort rating, not from generic heuristics
   designed for two-handed typing.
2. **Bigrams first, trigrams later.** Score =
   Σ frequency(a→b) × cost(pos_a → pos_b). With one hand every bigram is same-hand,
   so two-hand metrics (alternation, hand balance) don't apply.
   Trigram terms are added for selected 3-key patterns once the bigram model
   exists, where measured trigram time differs from the sum of its bigrams.
3. **Cost combines speed and discomfort.** Speed is assumed to be a good
   proxy for comfort that misses some strain (e.g. fast pinky stretches);
   validation checks this assumption. The exact combination
   is still open (see below).
4. **Positions, not fingers.** Keys are identified by physical position;
   which finger presses a key is whatever is natural, and is captured by the
   measurement implicitly.
5. **Transitions, not positions; fit a model.** What a key costs depends on
   the keys before and after it. There are too many transitions to measure
   one by one, so a model with transition features (finger relationship,
   rows, direction, sideways reach, hand shifts) is fitted to measured
   sequences and estimates every transition.

## Measurement

Costs come from timed trials on the keyboard plus discomfort ratings; the
plan, protocol and findings so far are in
[measurement-plan.md](measurement-plan.md). The corpus, the cost model and
which parameters matter are in [optimizer.md](optimizer.md). Summary: costs belong to
transitions, which depend on the keys before and after, not to key
positions; they are measured in short cyclic "words" in varied contexts
rather than relative to the home row, and fitted by a feature model.

## Corpus and weighting

- **What is typed by hand is what counts.** Most code is written by agents
  and longer prose is dictated; hand typing is short corrections, a few
  words where dictation doesn't integrate, shell commands, and editing /
  cursor movement (the hardest to cover by dictation).
- **Weights come from the keylogs, not from guesses about content types.**
  Keystats logs record focus changes (`# focus {"app": ...}`), so typing
  can be split by context (terminal, editor, browser). Dictated text,
  agent-written code and pasted text never reach the keylog, so the log
  already reflects the real mix, as typed on the current layout (which may
  itself make some sequences rarer).
  - The current logs are on the layer-4/5 layout, in use for ~2 months.
    They are small so far (~8k presses over 3 days, much of it measurement
    trials). Measurement trials must not count as typing: pause keystats
    during measurement, and as a safeguard drop keylog events inside the
    session time windows recorded in `trials.jsonl`. The 2025 logs are bigger but from two-handed typing with
    little dictation, so their mix is different.
- **Corpora fill in the bigram statistics**; the keylogs set proportions.
  Rare bigrams barely affect the base layer (the score is dominated by the
  few hundred most frequent bigrams *(guess; check by scoring with a
  truncated bigram table)*), so the point of corpora isn't the rare
  tail; it's stable estimates of the common bigrams, which a few thousand
  logged presses don't give.
- Sources: keystats logs, shell history, text and code samples to be
  provided. Final weighting is still checked by running the optimizer with
  different weightings and comparing the resulting layouts.

### Shortcuts are a separate frequency table

- Letter frequency in text underrates letters used in shortcuts (V is
  rare in text but Ctrl+V is probably very frequent; same for Z, C, S, W…
  *(guess until the shortcut table exists)*).
  Count *letter pressed with Ctrl/Alt/Super held* from the keylogs as a
  second table, scored alongside the text bigrams.
- A shortcut on a layer-2 letter needs Ctrl + layer key + letter. With
  adjacent thumb keys the difference from Ctrl + letter is minimal
  (experience), so shortcut frequency only adds a small weight towards the
  base layer.
- One-shot modifiers would remove the need to stack held keys, but it's
  unknown how well they suit the user (who is used to chording). To be tried.

### Shell history: notes for processing

Years of history exist; location to be confirmed (`~/.bash_history` here
has only 14 lines). Raw history overstates what is actually typed, so filter:

- **Autocompletion:** for tokens that are paths, filenames, git branches or
  long command names, keep only the first 2-3 characters of each path
  component, followed by Tab *(the 2-3 is a guess)*.
- **Pasted text:** drop tokens that look pasted: URLs, hashes, UUIDs,
  very long tokens.
- **Recalled commands:** collapse consecutive duplicates and cap how often
  one command counts; repeats are mostly recalled with Up / Ctrl-R, not
  retyped *(guess)*.
- **Check the filters:** compare character and bigram frequencies of the
  filtered history against keystats logs captured while the terminal was
  focused.

## Open questions

- How to combine time, rating and error rate into a single cost (rating
  scale decided 2026-11-21, see the decision log; the weight of time vs
  discomfort: fatigue test, design open).
- Do cyclic words represent transitions inside real text well enough?
  (2-key cycles of different fingers don't: they're trills. Check words
  with held-out predictions and typing tests on candidate layouts.)
- Space on a thumb key vs in the grid; which modifiers get the thumb keys,
  in which order on the arc; where Super and Alt go.
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
  are needed for modifiers; the optimizer compares Space on a thumb key vs
  in the grid); Polish letters under their Latin letters on the
  second letter layer (a preference, not a rule), z pinned to the base
  layer; palm key = held modal
  layer for navigation and numbers. Weighting from keylogs (by focused app),
  shortcuts counted as a separate table.
- 2026-11-20 — After a review: symbols are placed together with letters;
  measurement plan extended with both-keys-off-home trials (phase 4, tests
  the additive model) and the layer-switch experiment (phase 5, moved from
  open questions because layer-2 scoring depends on it); validation by
  typing real text on candidate layouts before committing; measurement
  sessions excluded from keylogs.
- 2026-11-20 — Phases 1-2a analysed (see measurement-plan.md). Off-home
  costs are measured as transitions in short cyclic words in varied
  contexts, fitted by a feature model, instead of as per-position extras
  relative to the home row. Word length and warm-up decided by a pilot.
  Measurement plan moved into its own document.
- 2026-11-21 — Before measuring more, find which cost parameters change
  the layout (sensitivity sweep, see [optimizer.md](optimizer.md)). Own
  annealing optimizer in Python (numba for speed), not the dariogoetz one.
  Corpus corrected for current one-handed use: git as `g`, no commits
  (agents commit), git and Vim downweighted, dictated and pasted notes out
  (details in optimizer.md). Scissor cost per finger pair and direction,
  full scissor more than twice a one-row one (user's experience). First
  sweeps: what decides the layout is index-middle scissors (both
  directions, if as bad as the user suspects), the index same-finger cost,
  the layer switch and the different-finger base, each by ~1-2% of the
  score; other scissors and strain features are in the noise. Measure
  those few next (see what-next.md).
- 2026-11-21 (later): optimizer compiled with numba (one language). The
  lateral stretch (index stretch column next to a middle-finger press;
  QWERTY G-D strained the user's left hand) decides as much as the
  index-up scissor if it is 4-6× the guess, so it joins the focus
  measurements (scissors index-middle, lateral, index same-finger, layer
  switch). Middle-ring and ring-pinky scissors, also straining for the
  user, come in a later round: layouts avoid them anyway.
- 2026-11-21 (evening): combining time and rating. Ratings become a
  penalty per cycle on the scale 0 1 3 6 12 (effortless … strain; "fine"
  is noticeably worse than effortless). The user would always pick the
  less effortful of two patterns even if slower, so discomfort dominates
  and time is mostly a tie-breaker; no exchange rate from preference
  questions. Proposed instead: a fatigue test, i.e. how fast the hand
  tires on a pattern typed at a fixed, similar pace (design open).
  User: tiredness grows slowly and has no clear moment; better measure
  the slowdown over a long trial and when it starts, though a slowdown
  marks strain rather than tiredness.
- 2026-11-21 (night): the held layer key next to Space costs +250-600 ms
  per word-like cycle, mostly from timing the release (user). Options:
  let the optimizer keep word-boundary letters on the base layer (model
  cost after `focus-5`), a **one-shot layer key** (measured by `focus-7`;
  the user finds it promising), or Space in the grid (removes the thumb
  conflict but not the release timing, and costs a prime finger slot).
- 2026-11-21 (night), layout review:
  - **Symbol pairs:** sharing a key with its Shift partner is intuitive
    and cheap *on the base layer* (`/?`, `-_`). On layer 2, layer + Shift
    for the partner may be too much, depending on the symbol: to consider
    in future layouts (now every pair fills a whole key on either layer).
    Unrelated symbols on one key (`*` with `@`) surprised the user.
  - **Number row:** index keys (c1, c2) cost more than a layer switch;
    the outer key (c6) is a little less bad but breaks the flow, no
    letters there; ring and pinky keys (c4, c5) "not horrible".
  - **Polish letters via a one-shot key in the grid** (tap it, then the
    Latin letter): frees the 9 layer-2 cells and puts every Polish letter
    exactly on its Latin letter, for one extra finger tap per Polish
    letter (1.7% of characters). The user wants to try it.
  - Keymap reorganized for trying layouts (`Keyboardio-Model-100_layout_
    2026-11-21_reorganized.json`): 0 base, 1 rAlt, 2 fun, 3-5 free,
    6-7 the current two-layer layout (former 4-5); the measurement layer,
    the number pad and the all-letters experiment are gone. measure.py
    identifies keys by key code, so it works on layer 6 as it did on 4.
- **2026-11-21, first typing test** on the one-shot layout: flows much
  better than the earlier attempts, few straining moves. Issues for the
  next iteration:
  - Scissors with a finger skipped strain: `n o` (ring top, index bottom)
    about 4 of 5, middle-pinky too. Model: `sc_far` *(guess, 100 per
    row)*; measured by `focus-8`.
  - The pinky top key needs the hand to move up, about as far as c6 top:
    `e_pinky_top` 25 → 35 *(guess)*; `focus-9`.
  - The number-row c6 key is pressed with the ring finger (the pinky
    doesn't reach it): `model.FINGER_POS`.
  - The one-shot Polish key on the number row (c5) works but is in a bad
    spot. One-shot layers look promising for more than Polish letters;
    finish `focus-7` to get their cost first.
  - `w y` both on layer 2 and typed with the layer key held through both:
    good, keep such pairs.
  - Thumbs: the outermost thumb key (t4, Space so far) is hard to reach.
    Ctrl, Shift and the layer key should be on the inner three; Space on
    t4 is not acceptable either.
- **2026-11-21, thumb keys** (user), innermost first: Shift, layer key,
  Space, and the outermost (hard to reach) for Alt/Super or the Polish
  one-shot key, undecided. Shift and the layer key need not be adjacent:
  shifted layer-2 keys were rare in the typing test. Ctrl: not decided
  yet (see what-next.md); Ctrl+Shift+letter shortcuts with a layer-2
  letter (Ctrl+Shift+V in the terminal) would need three modifiers held,
  one-shot modifiers make them sequential taps.
- **2026-11-21, shifted digits:** `! @ # $ % *` come from the shifted digits
  1-5 and 8 of the function layer (user), so the optimizer no longer
  places them (`anneal.SHIFTED_DIGITS`, costed like digits).
- **2026-11-22, more from the test layouts** (user):
  - A frequent letter (t) on the pinky bottom key will not work well.
    `e_pinky_bottom` 12 → 25 *(guess)*.
  - Index in the stretch column with the pinky: pinky bottom + index c1
    home uncomfortable, both bottom strain; pinky home + index c1 bottom
    uncomfortable, c1 home some effort. Model `spread_ip`,
    `spread_bottom_factor` *(guess)*; plan `focus-10`.
  - i and e on index top and bottom (first test layout) felt more
    comfortable than both on the home row (c1 and c2). c1 efforts raised
    *(guess)*.
  - Test the one-shot layer key alone first; the dual-use Ctrl hold later.
