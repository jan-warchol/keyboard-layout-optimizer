# Handoff (2026-11-22)

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
- **Thumbs** (user): innermost first Shift, layer key, Space; outermost
  (hard to reach) for Alt/Super or the one-shot key, undecided. Layer key
  planned as a Kaleidoscope one-shot layer key (tap = next key from
  layer 2, hold = layer 2).
- **Ctrl:** dual-use on a pinky home key (tap = Polish one-shot, hold =
  Ctrl) + a backup Ctrl. Test the one-shot key alone first. Must work
  with function-layer cursor keys, Backspace, Tab, Return (Shift too
  with Tab and Return). Unmodelled: roll misfires, Ctrl shortcuts on
  pinky-column letters, Ctrl+Shift+V with v/x on layer 2 (one-shot
  modifiers would make it sequential taps). Firmware: Chrysalis dual-use
  only takes a plain tap key; tap = one-shot layer needs a Qukey in the
  sketch *(guess, to check)*.

## Next steps

1. **Measurements** (the user; pause keystats). Protocol 3 since
   2026-11-22: continuous typing, the highlighted key is always next,
   stops when the speed settles; one round per day
   (docs/measurement-plan.md, Protocol). `python3 measure/measure.py
   run --plan focus-N`. Done: focus-1 to 7 round 1. To do, in this order
   (by sensitivity, `analysis/sensitivity-2026-11-22-focus-guesses.tsv`):
   - `focus-8` index-ring scissors (14, done 2026-11-22), `focus-9`
     middle-pinky (14): `sc_far` decides the layout (×4 of the guess:
     regret 11 ms/char). focus-8: index up + ring down rated 3-5, the
     reverse 1-2 (one round; the same split as index-middle in focus-1;
     user suspects possible measurement error: check in rounds 2-3);
   - `focus-13` index c1 + ring (14): the `n o` of the test layout (ring
     top, index c1 bottom); the model has no term for c1 + ring;
   - `focus-12` thumb vs pinky one-shot before pairs (12): where the
     one-shot key goes (not in the model yet, so not swept);
   - `focus-11` index c1 + pinky (12), `focus-10` pinky reach (16): their
     guesses cost < 0.6 ms/char if wrong; optional before the second
     test layout;
   - rounds 2-3 of focus-1 to 5 on other days.
   Then `python3 analysis/measurements.py focus` (add report sections for
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
