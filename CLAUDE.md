# keyboard-layout-optimizer

One-handed (right-hand) layout for a Keyboardio Model 100, optimized from
timed measurements on the real keyboard. Comfort first, speed second.

## Start here
- `what-next.md`: current state and next steps (handoff). Read it first.
- `docs/design-principles.md`: goals, layout structure, scoring model,
  corpus weighting, decision log. Record decisions there with their reason.
- `docs/measurement-plan.md`: phase plan and status, findings so far,
  trial protocol.
- `docs/optimizer.md`: corpus and its corrections, slots and cost model,
  sensitivity sweep and findings.

## Layout of the repo
- `measure/model100.py`: key geometry. Positions `r{row}c{col}` (row 0 =
  number row … 3 = bottom; col 0 inner column, 1 index stretch, 2-5 index..
  pinky, 6 pinky stretch), thumbs `t1..t4` (t1 innermost), `palm`. Labels
  are layer-4 keys; home row is `n r l h`.
- `measure/measure.py`: `run --plan ...` runs trials (reads
  `/dev/input`, needs a focused terminal, so only the user can run it);
  `stats` prints a quick summary.
- `measure/make_measurement_layer.py`: builds the Chrysalis layout with the
  measurement layer. Root `*.json` files are Chrysalis exports.
- `data/measurements/trials.jsonl`: raw trials, append-only, one JSON per
  trial; `presses` = [pos, t_down, t_up, index], index -1 = wrong key,
  -2 = held modifier (layer-key stand-in).
  Protocol-1 trials are exploratory only.
- `analysis/measurements.py`: `report` (phases 1-2a), `warmup PLAN` (word
  pilots), `focus` (scissors, index same-finger, layer);
  `analysis/word_pool.py`: Polish words typeable on layer 4.
  Analysis scripts and derived tables live in `analysis/`.
- `analysis/corpus.py` → `analysis/corpus/{1,2,3}grams.tsv` (corpus);
  `optimizer/model.py` (slots, cost model, parameters), `anneal.py`
  (optimizer, numba loop), `sweep.py` (sensitivity). Run the optimizer
  with `uv run` (numpy + numba from `pyproject.toml`).
- `keystats-data` → keylogger output, `dariogoetz_optimizer` → upstream
  optimizer: both external symlinks, read-only, never write analysis there.

## Conventions
- The user dictates: expect transcription errors; ask if a term is unclear.
- Analyse whole-cycle times, not per-transition splits; correct for
  session speed (see docs).
- Mark unmeasured claims *(guess)* in the docs.
- Commit data after each session ("Phase 2a session 3 data").
