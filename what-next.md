# Handoff (2026-11-22, midday)

One-handed right-hand layout for a Model 100, optimized from timed
measurements with discomfort ratings. The pipeline runs end to end:
corpus → cost model (guesses + fitted values) → annealing (numba) →
export to Chrysalis → typing test. Details: [docs/optimizer.md](docs/optimizer.md),
[docs/measurement-plan.md](docs/measurement-plan.md), decisions with
reasons in [docs/design-principles.md](docs/design-principles.md) (decision log).

## State

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
  `optimizer/fit.py`, K = 50 ms per discomfort step). Scores are now
  "ms + discomfort", ~240 ms/char (were ~160 with pure-time guesses):
  fitted values add ~56 (layer switch 402 ms alone +32), new guesses ~25.
  New guesses since the test layout, all to be replaced by measurements:
  `sc_far` (skipped-finger scissors), `spread_ip` + `spread_bottom_factor`
  (index c1 with pinky), `e_pinky_top` 35, `e_pinky_bottom` 25, c1
  efforts 25/35/30, r0c6 typed by the ring finger (`model.FINGER_POS`).
- **Optimizer options** (`uv run optimizer/anneal.py --params optimizer/fitted.json`):
  `--space grid` (Space on a finger key: 260 vs 235 ms/char, 2026-11-21
  model), `--dk-pos r2c6` (pin the Polish one-shot key: r2c6 236.5,
  r2c5 237.3, free 233.3). `! @ # $ % *` come from shifted digits on the
  function layer (`anneal.SHIFTED_DIGITS`), not placed in the grid.
  Latest free run (2026-11-22 model, 241.1): base
  `· \` d - ℙ ·` / `k o r g p l` / `s e i t n m` / `w a z h c /`.
  Not exported: too many guessed costs.
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
    `sc_index_up` 177, `sc_middle_up_i` 0). The user suspects it may b## Next steps

1. **Fit far scissors and the c1 + ring stretch** (started, not done):
   - `analysis/measurements.py`: `FOCUS_PLANS` ends at focus-7, so
     focus-8 to 13 trials don't reach `focus_data()` (report and fit)
     yet. Add them (and `scissors-far`, `pinky-reach`, `spread-ip`,
     `oneshot-pairs`), then add report sections for focus-8, 9, 13.
   - `optimizer/model.py`: split `sc_far` by direction like the
     adjacent scissors (inner finger up vs outer finger up, separately
     for index-ring and middle-pinky), maybe its own full (top-bottom)
     factor; add a cost for index c1 with the ring (today only `lateral`
     for c1 + middle and `spread_ip` for c1 + pinky exist, so c1 + ring
     is priced like c2 + ring plus the c1 effort).
   - `optimizer/fit.py`: estimates from focus-8/9 (vs home-home, same
     order) and focus-13 (vs the focus-8 pattern with the index in c2,
     same rows); also `space_top` from focus-6 (report section exists:
     Space next to the top row ~85 ms extra with index first, ~56 with
     middle first).
   - Then the sensitivity sweep on the new parameters (wrapper that
     loads `fitted.json`: sweep.py itself uses model.py guesses only).
2. **Re-optimize and export the second test layout** (layers 3-5;
   `export_layout.py` refuses non-empty layers: clear them or use
   `--base`). Keep the user's thumb plan; place the one-shot key on
   r2c6 if the user still wants it there. The user wants a layout to try
   soon: focus-10/11 guesses cost < 0.6 ms/char if wrong, so they can
   wait; the one-shot layer key isn't modelled yet (step 4) and can
   stay a held layer key in the model for now.
3. **Measurements still to do** (the user; pause keystats; the hand
   needed a longer rest after focus-13): `python3 measure/measure.py run
   --plan focus-12,focus-11,focus-10` (mixed: similar movements in a row
   tire the hand). focus-12 = thumb vs pinky one-shot before pairs (12).
   Rounds 2-3 of everything on later days, one round per day.
4. **Model the one-shot layer key** from focus-7 (+ focus-12):
   `fit.cycle_cost` skips tapped layer keys now. Look at per-transition
   splits to place the cost (a one-shot + letter behaves like one unit:
   fast inside, the cost in the reset before it), fit its size from whole
   cycles.
5. **Visualize the costs for the user to check against their
   impressions** (asked 2026-11-22): per-key effort on the grid, plus
   click a key to see the cost to every other key and back, split into
   time and discomfort. An artifact page from `model.pos_cost` with the
   fitted params.
6. **Analyse typing-test runs** (above) and later everyday keylogs.

n `python3 analysis/measurements.py focus` (add report sections for
   focus-8 to 11) and extend `optimizer/fit.py`: `sc_far`, `spread_ip`,
   pinky efforts, one-shot cost, and **top-home vs home-bottom scissors**
   (user: home-bottom generally worse, sometimes much; the model treats
   them alike; focus-1 already has the index-middle data).
2. **Visualize the costs for the user to check against their
   impressions** (asked 2026-11-22): per-key effort on the grid, plus
   something between that and all transitions, e.g. click a key to see
   the cost from it to every other key (and back), split into time and
   discomfort. An artifact page generated from `model.pos_cost` with the
   fitted params.
3. **Model the one-shot layer key** once focus-7 is in (`fit.cycle_cost`
   skips tapped layer keys now), and consider more one-shot content.
4. **Refit, re-optimize, export the second test layout** (layers 3-5;
   `export_layout.py` refuses non-empty layers: clear them or use
   `--base`). Keep the user's thumb plan; place the one-shot key on
   r2c6 if the user still wants it there.
5. **Analyse typing-test runs** (above) and later everyday keylogs.

## Open questions for the user

- When did dictation start for notes? The cut is 2026-07-01, from note
  lengths.
- Outermost thumb key: Alt/Super, or the Polish one-shot key?
- Shifted 6, 7, 9, 0 on the function layer: usable for `^ & ( )`? Then
  they leave the grid too.
