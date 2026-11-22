# Measurement plan

How transition costs are measured: the plan, the trial protocol, and what
the data has shown so far. The *why* of the layout and the scoring model is
in [design-principles.md](design-principles.md). Claims marked *(guess)* have
no measurement behind them yet.

## Current state

The current handoff is in `what-next.md` (2026-11-21): the optimizer and a
sensitivity sweep now decide what to measure. Added since: the `scissors`
plan in `measure.py` (adjacent fingers in all row combinations followed by
Space, both orders, 54 patterns), not run yet.

### Focus measurements (2026-11-21, not run yet)

The sensitivity sweep (docs/optimizer.md) found four parameters that
move the layout: the index-middle scissors, the index lateral stretch,
the index same-finger cost and the layer switch. They are measured in
four sessions of at most 20 patterns (user's limit), each with the
references it needs, `measure.py run --plan focus-N`:

| Plan | Patterns |
|---|---|
| `focus-1` | `scissors-im` (18) |
| `focus-2` | `lateral` (18) + home-row `n r Spc`, `r n Spc` |
| `focus-3` | `sf-index` (10) + `layer` for `n r` (8, includes the plain pair) |
| `focus-4` | `layer` for `n l` and `r l` (16) |
| `focus-5` | `layer-fingers` (16): `n r l` both orders, no Space, layer held for none / one / two / all letters |
| `focus-6` | `space-row` (12): index-middle + Space vs index-middle-ring, top / home / bottom row |
| `focus-7` | `oneshot` (20): the `layer-fingers` triples, no Space, with Sft *tapped* before each layered letter (14), and with the one-shot key on the pinky (r2c6) before one letter (6) |
| `focus-8` | `scissors-far` index-ring (14): c2 with c4, top-home, home-bottom and top-bottom in both directions, both orders, + Space, + home-home reference |
| `focus-9` | `scissors-far` middle-pinky (14): c3 with c5, the same |
| `focus-10` | `pinky-reach` (16): index or middle at home with pinky home / top / c6 home / c6 top, both orders, + Space |
| `focus-11` | `spread-ip` (12): index c1 with pinky c5, home / bottom rows, both orders, + Space, vs index in c2 |
| `focus-12` | `oneshot-pairs` (12): Sft or the pinky (r2c6) tapped before home-row pairs, `Sft a b` and `; a b`: thumb vs pinky one-shot |

`focus-8` to `focus-11` (added after the first typing test, 2026-11-21):
the user found `n o` (ring top, index bottom) straining, about 4 of 5,
and middle-pinky scissors too; the pinky top key needs the hand to move
up, about as far as c6 top. The model now has `sc_far` and a higher
`e_pinky_top`, both *(guess)* until these plans are measured.

`focus-7`: a one-shot layer key (tap it, the next letter comes from layer 2;
held, it works as a normal layer key) removes the release timing that
makes held single layered letters slow and error-prone. Tapping the
layer key is a plain thumb press, so it is emulated by tapping Sft as an
ordinary pattern key (`Sft n r l`); no keymap change needed. 12 cycles,
3 warm-up: the user practises the pattern with Backspace until it goes
well before starting (2026-11-22; was 15 and 6, new movement). The user has used one-shot keys only briefly,
for modifier chords.
Redesigned 2026-11-22 after one trial (user): with Space (the `layer`
pairs, now plan `oneshot-space`) the thumb made up to 3 of 5 presses on
two keys (`Sft n Sft r Spc`) and became the bottleneck. Now like
`focus-5`: `n r l` in both orders, no Space, every non-empty set of
layered letters, so tapped vs held compare directly (plain triples are
in `focus-5`). The one-shot key may not end up on a thumb: on the pinky's
outer key (r2c6) it comes before each letter of the triples in turn; the
move to the next finger is inward *(guess: fast)*. The user typed
`; n l r` as two units, `; n` and `l r` (gaps 107, 303, 59, 251 ms);
`; l r n` as one inward roll (99, 93, 74, 216). `focus-12` has the
pinky before home-row pairs and the thumb version of the same, for
comparing the two directly.

`focus-5` and `focus-6` were added after the first rounds (user, 2026-11-21):
- With Space, the layer key and Space alternate on one thumb; the first
  `focus-3` run needed ~8 restarts, mostly thumb errors. That measures
  the layer switch *plus* the thumb's next press. It occurs in text and
  stays measured, but `layer-fingers` isolates the switch itself
  (all-three-held = holding without switching). Patterns with a held
  layer key now get 20 cycles, 8 of them warm-up (`MOD_CYCLES`).
  From 2026-11-22 15 cycles, 3 warm-up: the user restarts a run until
  fluent, so the practice happens before it. Still 12 measured cycles,
  comparable with round 1.
- Space next to a top-row key stretches the whole hand (thumb down,
  finger up), so with-Space patterns overstate top-row discomfort.
  `space-row` separates it: the top-vs-home difference with Space minus
  the same difference with the ring finger instead of Space. Swept in the
  model as `space_top` (docs/optimizer.md): it moves the layout from
  ~4× the 20 ms guess.
Each is run 3 times on different days (`--repeats 3`). For these plans a
pattern counts as done only from trials of the same plan, so the
references are re-measured in-session even though phase 1 measured
`n r Spc` before. All patterns are 3-key
cycles `a b Spc`, the context of the phase-1 triples, shown with Space
last. Report: `python3 analysis/measurements.py focus` (all focus plans together).

Round notes:
- `focus-1` round 1 (2026-11-21 evening): the user would afterwards rate
  `u k Spc` (full scissor, index up) 5, not the 4 given, like `k u Spc`.
  Raw data left as typed; the median over three rounds absorbs it.
  First look (one session, not session-corrected): index up + middle down
  costs +70-120 ms per one-row scissor and +95-135 for the full one, rated
  3-5, i.e. 3-4× the 30 ms guess; middle up + index down +10-70 ms, rated
  1-2, more than the "nearly free" 5 ms guess but comfortable.
- Ratings of `n r Spc` (2 in every session, also phase 1) vs `r n Spc`
  and the pair `n r` (always 1): the 2 belongs to the outward direction
  followed by Space, not to the pair.
- `focus-3` round 1: stopped after 4 trials (layer patterns, see above).
- `focus-3`, `focus-4` round 1 (2026-11-21 evening). Session speed is now
  taken from the controls (the focus sessions share few patterns).
  - Index same-finger `a b Spc` vs the index-middle pattern on the same
    rows: +7 to +194 ms per cycle (median ~+100), rated 1-2 (`u n Spc` 3).
    The model's +55 per same-finger transition is low, but each cycle
    also has the index travelling back during Space.
  - **Layer with Space: +250-600 ms per cycle**, yet rated 1-2. Shift held
    for both letters costs *less* than for one (+100-400): in all three
    variants the thumb makes one Space → Shift → Space round trip, and
    holding across both letters gives it the most time. So these numbers
    are mostly the thumb shuttling between the layer key and Space, not
    the switch itself (the user's point). Corrected by the user: with one
    layered letter the thumb has three states to time against the
    fingers (Shift down, Shift up before the next letter, Space); with
    both layered it is one gesture (press and hold Shift, two letters,
    Space, the release barely needs thinking about). So the cost is
    largely *coordinating the release*, not only thumb travel. The
    errors (6-10 restarts of the first run) came from this; the patterns
    themselves felt mostly comfortable, hence ratings 1-2. The model has no such term: a
    layer-2 letter next to Space costs only `layer` (60). `focus-5`
    measures the switch without Space; the difference will give a new
    parameter for a layer-2 letter next to Space (common in Polish: word-
    final `ę`, `ą`, word-initial `ż`).
  - The user holds Shift across two consecutive layered letters (one
    press per cycle, confirmed in the logs), as the model assumes
    (`layer` for entering, `layer_cont` for each further letter).
- `focus-2` round 1 (2026-11-21 evening, 15 min after focus-1; controls
  ~7% faster than in focus-1). Lateral stretch vs the same pattern with
  the index in column 2, session-corrected through the shared home-row
  patterns: mostly +25-100 ms (up to +250 with the middle finger in the
  bottom row), i.e. above the 40 ms guess, and **ratings 1-2 steps worse**:
  `y r Spc` (both home) 3 vs 2; every pattern with the middle finger in
  the bottom row rated 4-5. Fits the user's G-D experience.

Not measured yet, though the user finds them straining too: middle-ring
scissors (both directions) and ring up + pinky down. In the sweep they
matter less (regret ≤ 0.4 even at 6× the guess), because good layouts
avoid them anyway; measure them in a later round (`--plan scissors`).

- **`scissors-im`** (18): index in column 2, middle in column 3, each in
  rows 1-3 (9 combinations), both orders. Home-home is the reference.
  Ratings matter as much as times (comfort first).
- **`lateral`** (18): index in the stretch column (`r?c1`) with the middle
  finger, all row combinations, both orders. Reference: the same pattern
  with the index in column 2 (from `scissors-im`). The user's experience:
  QWERTY G-D on the left hand was straining.
- **`sf-index`** (10): index same-finger bigrams, both orders: vertical in
  column 2 (`u n`, `n m`) and to/from the stretch column (`y n`, `y u`,
  `y m`). Reference: the index-middle pattern with the same rows. Caveat:
  in `a b Spc` the index also travels back from b to a during Space; in
  `a m Spc` it doesn't. Text has the same effect (the index must reach
  its next key), so this is part of the cost, not an artefact *(guess)*.
- **`layer`** (24): home-row pairs `n r`, `n l`, `r l`, both orders, with
  the layer key held for neither, the first, the second or both letters.
  Layer keys send no key code, so thumb Shift (`t3`, next to Space;
  `LAYER_KEY` in `measure.py`; confirmed by the user 2026-11-21) stands
  in for the layer key: the same held
  thumb movement. A letter typed with the wrong layer state (e.g. the next
  letter pressed before the layer key is released) counts as an error,
  since on the real layout it would type the wrong character. Space
  ignores the layer state. Modifier presses are logged with index -2.
  Differences against the plain pattern give the `layer` (one layered
  letter) and `layer_cont` (both) costs.

### Word pilots (handoff, 2026-11-20 evening)

Phases 1 and 2a are done and analysed (findings below). The off-home
method is still being searched for; three word pilots were run on
2026-11-20, the user tired by the third:

1. Random 4-6 key sequences: failed (memorising, not motor cost).
2. Chained random 4-key sequences: failed the same way; also too much
   pinky, too few adjacent-finger row changes, no text-like letters.
3. Real Polish words on layer 4 (`pilot-real`): 6 of 8 words done
   (`robimy`, `przy` not reached: crash on 7-key words, fixed since; end
   controls missing). Start controls were normal (`n r` 180 ms), but the
   words were slow: settled cycles 1180-1530 ms, i.e. 200-300 ms per key
   including Space (phase-1 triples: ~150), 5-22 errors per trial, and the
   time was still dropping after 10 cycles. The user's impression:
   "slightly better than random, not sure", possibly fatigue. One-swap
   words were not clearly worse than unchanged ones (too few to tell).

**Open questions for the next session** (discuss with the user before
building phase 4):

- Is pilot 3 representative when repeated fresh (morning, not after two
  other pilots)? Finishing it: `measure.py run --plan pilot-real` resumes
  with `robimy`, `przy`. Also compare with how fast these words are typed
  in everyday use (keylogs, layer 4/5) to see what speed is realistic.
- Why are real words still slow and error-prone? Candidates: the layer-4
  letters alone are rarely typed as whole words (most words need the palm
  key), so even unchanged words aren't practised as motor sequences;
  Space in every cycle; 15 cycles too long or too short.
- If words stay slow: more warm-up (the user suggested 10-20 practice
  cycles before measuring), or shorter units (3-4 key fragments of
  frequent words), or a different approach altogether.
- Pending decisions: keep the Wiktionary list in the repo or download it
  on demand (`analysis/word_pool.py` has the command)?

Tools: `analysis/measurements.py warmup PLAN` (settling per cycle),
`analysis/word_pool.py WIKTIONARY_FILE` (word pool).

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
| 3 word pilot | which words, warm-up and cycle count | random and chained random words failed; real words inconclusive (see handoff) |
| 4 word trials | transitions in varied contexts, fitted by a feature model | to do |
| 5 layer switch | cost of a layer-2 key inside a word | plan `layer` ready (part of `focus`), not run |
| validation | type real text on 2-3 emulated candidate layouts, compare with prediction | to do |

Word trials replace the earlier phases 2b (same finger, anchored), 3
(off-home positions as differences against home-row cycles) and 4 (both keys
off home): those all measured relative to the home row.

### Phase 3: word pilot

**First pilot** (`--plan pilot-words`, 2026-11-20, 6 of 21 words done):
random words of 4, 5 and 6 keys, 20 cycles each. It failed:

- The words were unlike anything usually typed and hard to remember. A
  settled 4-key word took ~220 ms per key (phase-1 triples: ~150); 5-6 key
  words took 300-400 ms per key with 5-31 errors, and were still speeding
  up in the last cycles (`/ o - l u`: 5100 → 1440 ms). That measures
  memorising, not finger movement.
- 20 cycles of the same awkward movement tired the fingers before the
  time settled.
- After a wrong key it was hard to find the place in the sequence again.

So: **at most 5 keys for random words, 4 more likely to settle quickly.**

**Second pilot** (`--plan pilot-chain`, then
`python3 analysis/measurements.py warmup`):

- 14 words of 4 keys, **chained**: each word starts with the last two keys
  of the previous one (a moving window over one random key sequence), so
  half of every new word is already practised. Then the first two words
  again (agreement within the session). Words are shown starting where the
  previous one ended.
- Keys from rows 1-3, columns 1-6; no Space (see phase 4).
- 15 cycles, nothing discarded, to see where the time settles.
- **The whole run is shown as text** (one group per cycle): typed keys
  turn dim green, the next key is highlighted. Acts as a progress bar and
  shows where to continue after a wrong key (applies to all trials).

Result (2026-11-20, 16 trials): **random sequences are the wrong kind of
trial**, chained or not.

- Settled cycles took 200-370 ms per key (phase-1 triples: ~150), with
  1-17 errors per trial; on average the time settled only after ~9 of 15
  cycles. Most words never felt fluent: the time measures learning an
  unfamiliar sequence, while the model needs the cost of practised
  movements (what the new layout becomes after adaptation).
- Uniform sampling over keys overrepresented the pinky: it owns 6 of the 18
  keys and got 41% of the presses (ring: 5%), often two pinky keys in one
  word, which a good layout avoids. Adjacent fingers in different rows were
  rare.
- The sequences had nothing in common with text (hardly any vowels).

**Third pilot: real words** (`--plan pilot-real`). Words typed on
layer 4, each followed by Space, cyclically (`humor humor …`).

- Letters on the palm layer, and Polish letters, are replaced by the
  layer-4 key at the same position: `f d w q / t e s a / c v x z` →
  `u i o b / n r l h / m k j g`, `ę` → `r` etc. Typing `mogr` for `mogę`
  uses the muscle memory of the word minus the palm key.
- 8 words alternating between none and one swapped letter: `humor`,
  `nigdy`→`nigiy`, `mogli`, `tylko`→`nylko`, `okno`, `mogę`→`mogr`,
  `robimy`, `przy`→`prgy`. 15 cycles each, nothing discarded; the first
  cycles slowly until the word flows, then normal speed.
- Answers: do real words settle quickly, and do one-swap words behave
  like unchanged ones (if so, the pool is ~4× larger).

Result: see the handoff section at the top.

**Word pool** (`analysis/word_pool.py`) for phase 4: Polish words of 3-7 letters, ranked by the
user's task database (`keystats/processed-janek-3.txt`) and the
[Wiktionary frequency list](https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Polish_wordlist)
(5000 words, from subtitles). No immediate same-key repeats. 153 words
need no swap, 576 one swap; together they contain 167 of the 182
letter-to-letter transitions, and the pinky gets 16% of the presses.
Transitions the words don't cover (column 6, `.`, rare pairs) get a few
designed sequences, practised longer (10-20 cycles of warm-up).

### Phase 4: word trials

- Each word, typed cyclically with Space, gives one cycle time (the sum
  of its transitions) and one rating.
- **Words** from the pool above, chosen greedily: every transition in at
  least two different words, extra weight on the strain transitions, few
  pinky-heavy words. A rating mostly reflects the word's worst transition;
  transitions shared between words let the fit localise both time and
  discomfort.
- **Practice effect.** Sequences frequent in current typing are faster.
  Partly real (frequent sequences on the new layout get practised too);
  the fit can include each transition's keylog frequency as a covariate.
- **Space only as the word separator.** The thumb is probably hardly
  influenced by what the fingers do (user's experience), so its cost comes
  from the phase-1 triples; in words it is a nuisance term of the fit.
  In those triples, the two cyclic orders with Space differ by 4-120 ms,
  and in all 6 the faster one is the order whose finger-to-finger
  transition goes inward. That fits the hypothesis "Space adds a cost that
  depends little on the fingers"; the asymmetry is the fingers' own. *(To check: a few
  triples with Space next to keys that need a hand shift.)*
- **Anchor words** repeat every session (session speed, repeatability).
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
- **Length (protocol 3, from 2026-11-22):** no fixed number of cycles.
  A clean cycle has all keys right, no wrong key in between, and no long
  gaps. A clean cycle counts only in a streak of 4+ clean cycles in a
  row, and the first 2 of each streak are dropped (re-warm-up after a
  slip; user, 2026-11-22: isolated clean cycles between slips aren't
  flowing typing). By position in a streak (17 streaks of 6+): 1st +11%
  vs the rest, 2nd +3% (24% of them >10% slower), 3rd on par; slippery
  patterns start more streaks, so keeping the 2nd would favour easy
  ones slightly. Trials store the rule as `streak` [4, 2]; the
  first protocol-3 trials (until ~11:40, no field) used 3 and 1. The first 3 counted cycles are warm-up; the trial stops when the
  last 10 counted cycles have settled: the median of their second half is
  at most 10% faster than the first half's (within-trial noise is
  ~30 ms, so a 4-cycle median moves by a few %; 10% flags real learning
  only). Cap: 40 cycles typed or 90 s of typing. Trials record `stable`
  (false = stopped by the cap) and `warmup_cycles`..`cycles` = the
  measured window. Before (protocol 2), a fixed number of cycles:

  | Keys | 1 | 2 | 3 | 4 | 5-6 |
  |---|---|---|---|---|---|
  | cycles | 30 | 20 | 13 | 10 | after the pilot |
  | warm-up cycles | 8 | 5 | 3 | 3 | after the pilot |

  Why the change (user, 2026-11-22): with a fixed run, one skipped or
  extra key shifted every later key into the wrong slot, so the rest of
  the run counted as errors and the user restarted runs until fluent;
  the fixed warm-up then came after the practice, and a late slip
  spoilt a mostly good run.

- **Main measure is the cycle time** (one pass through the pattern).
- **Timing** from kernel input events (`/dev/input`), press-to-press.
  Releases are logged too (hold time, rollover). Rollover is normal in
  comfortable sequences (the old keylogs show it too).
- **Errors (protocol 3):** the highlighted key is always the next one. A
  wrong key is saved as an error (index -1, no slot) and the highlight
  stays until the right key comes; a slip costs only the streak it
  breaks. `errors` = slips (a run of wrong keys counts once); divide by
  the presses for a rate (an additional cost signal). Backspace (when not
  in the pattern) starts the pattern again: the highlight moves to the
  start of the next cycle, the unfinished cycle is never counted (user:
  simplest when lost in the middle).
  The screen lays the pattern out cycle after cycle (rows of whole
  cycles, 2 rows back and 2 ahead): typed slots green, the next key
  highlighted (red after a wrong key). A view of only the last keys
  typed, or of one cycle with a moving highlight, scrolled or jumped too
  fast to read (user).
  - A first protocol-3 version (2026-11-22, a few trials) found the
    position again from the next 2 keys typed after a slip, wherever in
    the pattern they fitted. Too clever: pressing the highlighted key
    alone didn't resume, and the user got lost (`Sft r Sft n l`, 11:21,
    23 errors, never settled; left out by the analysis, as is every
    protocol-3 trial without counted cycles).
  - Before: until 2026-11-21 the correct key had to follow a wrong one
    (after a slip the user lost track and made several errors in a row);
    then (`advance_on_error`) a wrong key took its slot.
  - Cycles with a wrong key inside are left out of the cycle time, for
    all protocols (since 2026-11-22; before, cycles with a corrected
    error counted in the blocking trials, which changes 83 of 398 old
    cycle times, mostly by 0.5-3%, the error-heavy word pilots by up to
    35%). A wrong key invalidates the transition into it.
- **Discomfort rating** after every trial, on the top row `. u i o b`:
  1 effortless · 2 fine · 3 some effort · 4 uncomfortable · 5 strain.
- **Control trials** (`n r` and the inward roll `h l r n`) at the start and
  end of every session track drift, fatigue and session speed.
- **Repeatability:** phases 1-2a measured every pattern in 3 sessions (at
  most once per session); word trials use anchor words instead. Since
  2026-11-22 each round is on a separate day: a session skips patterns
  already measured that day, and rounds = days with an ok trial (`run
  --repeats`, default 3).
- **Stretches and breaks:** 3-minute stretches (pauses not counted), then a
  30 s break with a countdown; continue or finish with the end controls;
  at most 5 stretches.
- **Measuring only while the terminal is focused.** Switching away (or a
  screen lock) pauses the trial; key presses elsewhere are ignored. Since
  protocol 3 the trial goes on after the pause (the gap breaks no
  measured cycle: cycles with long gaps are left out).
- **Avoid patterns whose rotation is a familiar roll** unless the roll is
  what is measured (user, 2026-11-22): `; n l r` (focus-7) read as a
  shifted inward roll, and it took several attempts to type it as the
  intended two units `; n` + `l r`. The hand drifts into the roll, and the
  cycle then measures the roll instead.
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
