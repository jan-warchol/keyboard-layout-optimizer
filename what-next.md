# Handoff (2026-11-22, afternoon)

One-handed right-hand layout for a Model 100, optimized from timed
measurements with discomfort ratings. The pipeline runs end to end:
corpus → cost model (guesses + fitted values) → annealing (numba) →
export to Chrysalis → typing test. Details: [docs/optimizer.md](docs/optimizer.md),
[docs/measurement-plan.md](docs/measurement-plan.md), decisions with
reasons in [docs/design-principles.md](docs/design-principles.md) (decision log).

## State

- **Second test layout** (2026-11-22) is on layers 3-5 of
  `Keyboardio-Model-100_layout_2026-11-22_optimized-test-2.json`
  (`optimizer/layouts/2026-11-22-oneshot.json`, 245.5 ms/char; the first
  scores 277.4 under the same model). Made from the 2026-11-21 test file
  with `export_layout.py --replace`: none of the saved files has the
  user's layer keys for layers 3-5 (placed on the device only), so after
  loading it they must be placed again, or the user exports the current
  keymap and it is re-run on that file. One-shot key on r2c6 (free: back
  on number row c5, 2.9 ms/char better). Base `· \` d - . ·` /
  `m o i n l g` / `p a s t r ℙ` / `w e z h c /`, details in
  docs/optimizer.md. Not typed yet.
- **Cost visualization** (asked 2026-11-22): https://claude.ai/artifact/VbeKkTnEtAXju5UxtdRp26
  (private), from `uv run optimizer/cost_view.py` → `analysis/cost-view.html`.
  Not reviewed by the user yet: next step 1.
- **First test layout** (Polish one-shot key, 2026-11-21) is on layers 3-5
  of `Keyboardio-Model-100_layout_2026-11-21_optimized-test.json`
  (saved as `optimizer/layouts/2026-11-21-oneshot.json`; export with
  `optimizer/export_layout.py`). The user placed the layer keys. Verdict
  after one typing run: much better than both earlier attempts, flows,
  few straining moves. Problems found are in the decision log
  (2026-11-21 first typing test, 2026-11-22 entries): skipped-finger
  scissors (`n o`), pinky top and bottom keys, index c1 + pinky, i/e
  placement (top/bottom index preferred over both on the home row), the
  one-shot key's spot (number row c5). Liked: `w y` both on layer 2, held
  through both.
- **Typing test:** `python3 measure/measure.py type --layout NAME`, text
  `data/typing-test.txt` (236 chars, shortened after the first 572-char
  run took 17 min), raw key events + characters → `data/measurements/typing.jsonl`.
  One run so far (old text). Not analysed yet: map key codes to physical
  keys via the layout file (layer keys and one-shot send nothing; infer
  them from the next character).
- **Cost model** (`optimizer/model.py` + `optimizer/fitted.json` from
  `optimizer/fit.py`, K = 50 ms per discomfort step), "ms + discomfort".
  Fitted 2026-11-22 afternoon: far scissors by direction (index up over
  ring 244, pinky up over middle 243, the reverse 0), `sc_far_full_factor`
  2.3, `lateral_ring` 259 (index c1 + ring, new), `space_top` 27.
  Still guesses: `spread_ip` + `spread_bottom_factor` (index c1 with
  pinky), `e_pinky_top` 35, `e_pinky_bottom` 25, c1 efforts 25/35/30,
  derived scissors of middle-ring and ring-pinky; r0c6 typed by the ring.
- **Optimizer options** (`uv run optimizer/anneal.py --params optimizer/fitted.json`):
  `--space grid` (Space on a finger key: 260 vs 235 ms/char, 2026-11-21
  model), `--dk-pos r2c6` (pin the Polish one-shot key: r2c6 236.5,
  r2c5 237.3, free 233.3). `! @ # $ % *` come from shifted digits on the
  function layer (`anneal.SHIFTED_DIGITS`), not placed in the grid.
  `--save`, `--score LAYOUT` (score a saved layout).
- **Measurements (2026-11-22):** round 1 of focus-1 to 9 and focus-13
  done. Protocol 3 since today (continuous trials, highlighted key always
  next, streaks of 4+ clean cycles with the first 2 dropped, stops when
  10 counted cycles have settled; Bsp = start the pattern again; half
  ratings = two neighbouring numbers pressed together; 1 s blank before
  the rating; one round per day; `--plan a,b,c` alternates plans).
  History and reasons: docs/measurement-plan.md, Protocol. Edited
  trials carry `rating_edited` or `status: discarded` + reason.
  - focus-8 (index c2 + ring): index up + ring down rated 3-5, the
    reverse 1-2. The same split as index-middle (focus-1: fitted
    `sc_index_up` 177, `sc_middle_up_i` 0). The user suspects a possible
    measurement error: check in rounds 2-3.
  - focus-9: the middle-pinky home-home reference is itself slow and
    rated 2-3 (model: no term for it).
  - focus-13: index c1 + ring rated 3.5-5 in every row combination.

## Next steps

1. **Get the user's feedback on the cost map** (not seen yet; the user
   will look later): https://claude.ai/artifact/VbeKkTnEtAXju5UxtdRp26.
   Ask which costs look wrong against their impressions: key efforts
   (all guesses), transitions from/to a key they know well (e.g. the
   pinky keys of `l g`, the index stretch column), the time / discomfort
   / guess split. Record remarks in the decision log, mark the
   parameters they question, feed them into the model or measurement
   plans. Regenerate after model changes: `uv run optimizer/cost_view.py`,
   then republish `analysis/cost-view.html` to the same URL (its labels
   predate the user's `( ) : ^` edits; letters are unchanged).
   The second test layout is in everyday use (3 typing runs, impressions
   in the decision log); keep collecting typing runs
   (`python3 measure/measure.py type --layout opt-2026-11-22`).
2. **Measurements still to do** (the user; pause keystats):
   `python3 measure/measure.py run --plan focus-12,focus-11,focus-10`
   (mixed: similar movements in a row tire the hand). Rounds 2-3 of
   everything on later days, one round per day. Then refit (`fit.py` has
   no estimates for focus-10/11 yet: `spread_ip`, pinky efforts).
3. **Model the one-shot layer key** from focus-7 (+ focus-12):
   `fit.cycle_cost` skips tapped layer keys now. Look at per-transition
   splits to place the cost (a one-shot + letter behaves like one unit:
   fast inside, the cost in the reset before it), fit its size from whole
   cycles.
4. **Sensitivity sweep on the new parameters** (wrapper that loads
   `fitted.json`: sweep.py uses model.py guesses only); top-home vs
   home-bottom scissors (user: home-bottom worse; focus-1, -8, -9 have
   the data, the model treats them alike).
5. **Analyse typing-test runs** and later everyday keylogs: map key codes
   to physical keys via the layout file (layer keys and one-shot send
   nothing; infer them from the next character).

## Model gaps (to do; the user, 2026-11-22: "quite a few combinations
## we didn't account for")

- **Shift by key:** Shift costs a flat 404 ms everywhere (derived from
  the layer key, a guess). Shift + some keys is much worse than others
  (index number row bad, outer keys easier). Needs a Shift plan like
  `layer-fingers`, with off-home keys.
- **Layer 2 with the one-shot key:** the model prices layer 2 as a held
  key (404). Fit the one-shot cost from focus-7 (median ~350, rated 1-2)
  and focus-12; check whether easy layer-2 positions deserve letters.
- **One-shot Polish key by next finger:** ring/pinky letters after the
  pinky one-shot are awkward (see open questions).
- **Pinky top keys** (`l` r1c5, `g` r1c6 feel wrong): focus-10.
- **Paired symbols adjacent** (`( )`, `[ ]`, `{ }`): no model term.
- **Flow:** the first test layout flowed better, with more stretches;
  the model has bigrams only (no rolls, trigrams).
- **Thumbs:** the model puts Space on t4; the user now has it innermost.
- **Shortcuts:** Ctrl + letter comfort isn't modelled.
- **Typing runs as data:** typing.jsonl has 3 runs on this layout.
  Space → Space within ~25 ms is autorepeat: Space held by mistake for
  the layer key or Shift (run 1: one 888 ms hold sent 29 spaces). Drop
  those before analysing.
- **Coverage (2026-11-22):** 447 trials, 222 distinct patterns; 217 of
  784 ordered key pairs (28%) occur in measured patterns, but 55% of
  the current layout's key-pair transitions by corpus frequency (layer
  ignored). The rest rely on parameters. 17 more pairs give 70%, 41
  give 80%, 84 give 90%. Measuring everything is out of reach; once the
  layout settles, measure the layout's top unmeasured pairs (`r1c6 → Spc`,
  `Enter → r1c6`, `r2c5 → r3c2`, ...) as a check of the model.

## Open questions for the user

- **Polish letters on ring/pinky keys** (2026-11-22, after the second
  test layout): ℙ on r2c6 makes ł ń ć ż awkward. Options: (a) move the
  one-shot key to the index stretch column. Swapping it with `m` (r1c1)
  costs +0.55 ms/char, re-optimizing with it pinned there gives 244.3
  (vs 245.5, but every letter moves); swapping with `w` (r3c1) +2.5.
  With it on the index, ą ę ó become same-finger pairs (a e o are index
  letters). (b) Polish letters on keys of their own near the index, no
  longer on their Latin letters. (c) the one-shot key on a thumb. The
  model doesn't price the one-shot key itself yet (step 3): measure
  focus-12 (thumb vs pinky one-shot) before deciding.
- **One-shot Ctrl and Shift**: not in the Chrysalis UI; the user will ask
  for a keymap file with codes 49153 (Ctrl) / 49154 (Shift) on the thumbs.
- Consider additional space in second layer.

- When did dictation start for notes? The cut is 2026-07-01, from note
  lengths.
- Outermost thumb key: Alt/Super, or the Polish one-shot key?
- Shifted 6, 7, 9, 0 on the function layer: usable for `^ & ( )`? Then
  they leave the grid too.
