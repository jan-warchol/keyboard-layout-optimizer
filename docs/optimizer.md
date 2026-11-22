# Optimizer: corpus, cost model, sensitivity

How layouts are scored and searched, and what the sensitivity analysis has
shown. The *why* of the layout is in [design-principles.md](design-principles.md),
the measurements in [measurement-plan.md](measurement-plan.md). Claims marked
*(guess)* have no measurement behind them.

## Pipeline

```sh
uv sync                               # numpy + numba (pyproject.toml)
python3 analysis/corpus.py            # -> analysis/corpus/{1,2,3}grams.tsv
python3 analysis/corpus_report.py OUT.json   # per-source statistics (review page)
uv run optimizer/anneal.py [--restarts 4] [--steps 200000] [--set name=value ...]
uv run optimizer/sweep.py [--only param ...] [--restarts 4] [--steps 1000000]
                                      # -> analysis/sensitivity.tsv
```

Our own optimizer instead of the dariogoetz one: its metrics are built for
two-handed layouts and it needs a Rust toolchain; ours scores with the
transition-cost model directly. The annealing loop is compiled with numba
(decided 2026-11-21: one language; Rust would be similarly fast); setup
and full scoring stay in Python, and every run asserts that the
incremental score equals a full rescoring. Speed: ~1.5M steps/s per core,
~100× the pure-Python loop; the full sweep (900 runs of 1-2M steps) takes
5 min on 8 cores, a sweep of 3 parameters 30 s.

Search quality: restarts of 2-20M steps still end 0.1-0.25 ms/char apart,
whatever the temperature schedule (t0 1-10, t1 0.0005-0.005 all alike;
t1 0.05 is worse). The landscape is full of near-ties, so the sweep
takes the best of several runs and adds warm starts (see below).

## Corpus (`analysis/corpus.py`)

Character n-grams (1-3) of what is typed by hand, case-folded (a capital is
its letter's key plus Shift, the same cost anywhere).

| Category | Source | Share of category |
|---|---|---|
| prose 60% | keylog prose 2025 | 35% |
| | task notes (app dump) | 35% |
| | shell prose: commit messages, agent prompts | 20% |
| | keylog prose 2026 | 10% |
| code 40% | shell commands | 65% |
| | keylog code 2025 | 25% |
| | keylog code 2026 | 10% |

Each source is normalised before mixing, so a filter shifts the mix *inside*
a source, not the source's share. 60/40 is the 2026 keylog's mix; the
shares inside categories are *(guess)*. The 2026 keylog is only ~3k
characters, hence its small share.

- **Lines** are typing units between two Enters: the first key of a line
  is counted as entered from Enter (otherwise line-initial keys, e.g. `g`
  of `g d`, look free). Tab completion `⇥` is Tab; a paste `⎘` breaks
  n-grams.
- **Corrections for current one-handed use** (user's judgement,
  2026-11-21), applied when reading; sources untouched:
  - `git` → `g` (the alias will be used); commit and amend commands
    (`g ci`, `g commit`, `g amq`, `g amci`) dropped, agents commit now,
    and with them the `ZZ` that closed the commit editor; other git lines
    (incl. `g-`) weigh 0.3, which puts `g` at 3.3%, between `c` and `d`.
  - Vim (ex commands, `ZZ`, `dd`, `vim file`, normal-mode keys logged as
    code lines: `yap`, `sip`, `v:bu`, `cwe`, …) weighs 0.3: used much less now.
  - `q` closing the git pager before the next command (`qg d`) is a soft
    break: n-grams across it weigh 0.2.
  - fzf widget names in the history (`__fzf_git_checkout__`) are not typed: dropped.
  - Notes: lines with non-breaking spaces (pasted from the web) dropped;
    identical lines count at most 3 times (recurring tasks); notes created
    since 2026-07 longer than 300 characters dropped as probably dictated
    (long notes jump from 2026-07; date is a guess, ask the user if known).
  - Keylog: measurement sessions are removed from the raw 2026 logs
    (backup and script in `keystats-data/backup/`); the corpus also drops
    lines inside session windows as a safeguard.
- **Known leftovers:** 2026 keylog lines have no reviewed kinds, so some
  shell commands count as prose; `nrd`, `/res` and similar layer tests;
  `(2)` time-estimate suffixes in notes (typed then, kept). All small.

## Slots and cost model (`optimizer/model.py`)

- **Slots:** grid positions rows 0-3 × columns 1-6, on the base layer and
  layer 2, each with an unshifted and a shifted half. A letter fills a
  whole cell (capital on the shifted half); a symbol fills one half. Pinned:
  `/` and `\` on r3c6 (base / layer 2), Space on the thumb (t4), Enter
  r1c0, Tab r0c0 *(guess)*, `z` on the base layer. Digits cost a fixed
  palm-layer price; symbols that don't fit (the rarest) a fixed "other" price.
- **Score** = Σ bigram frequency × transition cost, in ms per typed
  character, plus a Polish-letter preference (under its Latin letter on
  layer 2).
- **Transition cost:** same key (phase 1 medians); same finger, different
  key (phase 2a, + distance); different fingers: base + outward penalty +
  ring-pinky + row change + scissor + lateral stretch + number row with
  bottom row; + effort of the target key by position; thumb (Space)
  transitions; layer and Shift cost on entering, cheaper when held on.
- **Scissors** (adjacent fingers in different rows) have a cost per finger
  pair and per *which finger is higher* (6 parameters), and a factor for a
  full (two-row) scissor over a one-row one (user: clearly more than 2).
  User's experience: index up + middle down much worse than the reverse
  (nearly free); middle-ring worse than index-middle; ring down + pinky up
  worst. Values are guesses.

## Sensitivity: which parameters matter

`optimizer/sweep.py` re-optimizes with each parameter changed and reports
the **regret**: how much worse the baseline layout scores than the new
optimum under the changed value (ms per typed character, of ~160). Small
regret = a wrong guess barely costs anything, so measuring the parameter
wouldn't change the layout. The baseline's own restarts give the noise.
Since the numba port, each value runs 4 cold restarts plus 4 warm starts
from the baseline layout at a lower temperature (t0 = 1): the result can't
be worse than the baseline, so regret ≥ 0, and best-of-8 is stable to
~0.05 ms/char (checked on index-up scissor ×4: 1.37-1.40).

- **Near-ties:** restarts find layouts that differ in 30-90% of typed
  characters but score within ~0.3-0.9 ms/char. "Which letters moved"
  means little; regret is the measure.
- **Focused sweep** (2026-11-21, 12 baseline + 6 restarts per value,
  `analysis/sensitivity-2026-11-21-focused.txt`, corpus before the last
  corrections, old symmetric scissor model): measured parameters ±25%,
  guesses ×0.5/×2.

  | Parameter | Regret ms/char |
  |---|---|
  | index same-finger cost | 1.8 (both directions) |
  | layer switch | 0.6 / 1.0 |
  | different-finger base | 0.8 / 0.5 |
  | finger after Space | 0.0 / 0.6 |
  | scissor, lateral, row change, outward, ring-pinky, key efforts | ≤ 0.2 (noise) |

  Even the largest is ~1% of the score: the rough model is good enough
  for a first layout, and precise values buy ~1%. The sweep cannot test
  effects the model lacks (hand shifts, redirects, trigram rolls).
- **Scissor sweep** (2026-11-21, corrected corpus, directional scissors
  ×0.5/×2/×4/×6, full factor 2-5; `analysis/sensitivity-2026-11-21-scissors.txt`,
  `analysis/sensitivity.tsv`). Noise ≤ 0.16 ms/char.

  | Parameter (guess, ms per row) | Regret at ×2 / ×4 / ×6 |
  |---|---|
  | index up + middle down (30) | -0.1 / **1.2** / **3.1** |
  | middle up + index down (5, "nearly free") | 0.1 / 0.6 / **1.2** |
  | pinky up + ring down (60) | 0.0 / 0.4 / 0.9 |
  | ring up + middle down (40) | 0.0 / 0.2 / 0.5 |
  | middle up + ring down (30) | 0.0 / 0.2 / 0.5 |
  | ring up + pinky down (30) | 0.0 / 0.0 / 0.1 |
  | full-scissor factor 3 → 2, 4, 5 | ≤ 0.1 |

  Plus, as before: index same-finger 1.8, layer switch 0.85,
  different-finger base 0.8, finger after Space 0.4.

  **Index-middle scissors are the parameter that decides most**, if they
  are as bad as the user suspects: index and middle carry the most
  frequent letters, so their bigrams are common. Pinky-up scissors are
  avoided by any good layout, whatever their exact cost; middle-ring
  matters only if very costly.
- **Numba sweep** (2026-11-21, same model and corpus as the scissor sweep,
  4 cold + 4 warm starts × 1M steps per value, baseline 16 × 2M;
  `analysis/sensitivity-2026-11-21-numba.txt`). Confirms the scissor sweep
  and shows the smaller effects more clearly:

  | Parameter | Regret ms/char |
  |---|---|
  | index up + middle down scissor ×4 / ×6 | 1.3 / 3.3 |
  | index same-finger ±25% | 1.8 / 1.6 |
  | middle up + index down ×4 / ×6 | 0.5 / 1.1 |
  | layer switch ×0.5 / ×2 | 0.9 / 0.7 |
  | pinky up + ring down ×4 / ×6 | 0.4 / 0.85 |
  | different-finger base ±25% | 0.7 / 0.75 |
  | index stretch top row (`e_col1_top`) ×2 | 0.5 |
  | ring up + middle down ×6 | 0.4 |
  | pinky top row, finger step after Space ×2 | 0.4 |
  | everything else | ≤ 0.3, mostly 0 |

  **Lateral stretch** (index in column 1 next to a middle-finger press,
  40 ms *(guess)*), swept to ×6 after the user pointed out it strained
  the left hand (QWERTY G-D): ×2 0.0, ×4 **1.4**, ×6 **3.1**, as strong
  as the index-up scissor. In the current layout 2.3% of bigrams use it,
  mostly `ti`/`it` (`i` at r2c1, `t` at r2c3), then `bi hi di zi`. Added
  to the focus measurements.

  **Space next to the top row** (`space_top`, 20 ms *(guess)*, ×2 for the
  number row; added after the user noted the whole hand stretches):
  ×0.5/×2 ≤ 0.1, ×4 **1.2**, ×6 **2.6**. Measured by `focus-6`.

  Base layer unchanged from the scissor sweep: `g o d l c f` / `i a t s n
  w` / `p e z m r /`.

## Fitted parameters (`optimizer/fit.py`, 2026-11-21, round 1 only)

`uv run optimizer/fit.py --k K` estimates parameters from the focus
measurements and writes `optimizer/fitted.json`; `anneal.py --params
optimizer/fitted.json` uses it. Each estimate: measured cycle-time
difference vs the reference pattern + K × difference in rating penalty
(0 1 3 6 12), minus what the model already predicts for that difference,
median over pattern pairs. K = ms per penalty step, 50 *(guess)*.

| Parameter | Guess | K=0 | K=50 | K=100 |
|---|---|---|---|---|
| layer (entering layer 2, held key) | 60 | 400 | 400 | 400 |
| layer_cont | 15 | <0 → 0 | 0 | 0 |
| sc_index_up | 30 | 20 | 180 | 300 |
| sc_middle_up_i | 5 | <0 → 0 | 0 | 0 |
| sc_full_factor | 3 | 3.1 | 2.7 | 3.0 |
| lateral | 40 | 36 | 174 | 299 |
| sf_index | 165 | 262 | 233 | 197 |

Derived *(guess)*: shift = layer (same thumb movement); middle-ring and
ring-up-pinky-down scissors = sc_index_up (user: similarly straining).

Findings and problems of the first fitted layouts:
- **Number row:** with layer = 400 the optimizer put letters on all
  number-row keys. Design-principles allows letters only on the middle
  (c3) and outer (c6) keys, so `NO_LETTER_POS` in `anneal.py` now enforces
  it (both layers). With it, 19 letters on the base layer, 9% of
  keypresses on layer 2 (old guesses: 18 letters, 15%).
- **Unbalanced costs:** measured parameters now carry the rating penalty,
  guessed ones (pinky efforts, ring-pinky, number-row reach) don't. At
  K=50 the pinky takes 24% of keypresses (old guesses 18%) and the middle
  finger 9%: not trustworthy. Fix: rate-and-fit the pinky costs too
  (phase 1-2a have ratings), or scale the guesses consistently.
- **Scissor direction:** index→middle with the index up is +100-145 ms,
  middle→index +-15 ms for the same rows; the model's scissor ignores the
  order of the two keys, the fit takes the median.
- The layer cost is from Shift held and unpractised; one-shot (`focus-7`)
  may be much cheaper.

### Review with the user (2026-11-21 night) and changes

- **Symbols as key-code pairs:** Shift gives the US partner, so a symbol
  pair fills a whole key like a letter (`-_ .> ,< '" ;: =+ `~ ]} [{`, and
  `()` as a CharShift pair); `/?` and `\|` pinned at r3c6. No separate
  keys for shifted symbols (user). The 46 free keys hold 35 letters, 10
  pairs and one key of loose symbols (`@ *`); rarer symbols are "other".
- **Number row:** index keys (c1, c2) and the outer key (c6) cost 500
  *(guess)*, more than a layer switch: the user prefers layer 2 to them,
  infrequent symbols only. No letter on r0c6.
- `fitted.json` holds only the fitted values (it used to override model.py).
- Open, from the review: `.` and `-` placement unacceptable so far (now
  `.` `,` on number-row c4/c5, whose cost of 80 is a guess; `-` on layer
  2); `)` placement; brackets now on layer 2 c6/c2. Vowels on the index
  are fine by the user (interleaving). Pinky load (24%): test in
  practice. Middle finger: more load welcome, but then the index-middle
  scissors and lateral stretches matter more.

### Polish one-shot key and first test layout (2026-11-21 night)

- `Problem(P, polish="oneshot")` (now the default): a Polish letter is
  typed as the one-shot key ℙ + its Latin letter (corpus transformed: +1.7%
  keystrokes); ℙ is a base-layer key placed by the optimizer; the nine Latin
  bases `a c e l n o s z x` must be on distinct physical keys (the Polish
  layer maps one key to one letter). `polish="layer"` is the old model.
  Score with the same costs: 223.6 vs 224.1 ms/char (layer mode): the same,
  but 9 keys freed.
- Loose symbols take one key each (unshifted half only): unrelated symbols
  sharing a key surprised the user. `()` is no longer a pair: the firmware
  has no CharShift plugin. Only ASCII symbols are placed.
- First test layout: `optimizer/layouts/2026-11-21-oneshot.json`, written
  into the keymap by `optimizer/export_layout.py` (layers 3 = base, 4 =
  layer 2, 5 = Polish one-shot layer; only the right-hand grid, the rest
  transparent): `Keyboardio-Model-100_layout_2026-11-21_optimized-test.json`.
  Entry and layer keys are placed by the user.
- Still open from the review: `.` and `-` on layer 2; `[` `]` split between
  layers; pinky 25%, middle 9% (to be judged by typing).

### Sweep of the new guesses (2026-11-22)

Fitted parameters (`fitted.json`) as the baseline, 241.1 ms/char; noise
regret max 0.24; `analysis/sensitivity-2026-11-22-focus-guesses.tsv`.
- `sc_far` (skipped-finger scissors, guess 100) decides the layout:
  regret 0.3 / 1.0 / 11.2 / 23.5 ms/char at ×0.5 / ×2 / ×4 / ×6, most
  letters move. Measure first (`focus-8`, `focus-9`).
- Everything else ≤ 1.1: `spread_ip` 0.55 at ×0.5, `spread_bottom_factor`
  0.60 at ×2, `sc_full_factor` ≤ 0.52, `e_col6_top` 0.42 at ×2,
  `e_pinky_top` ≤ 0.17, `e_col6_home` ≤ 0.12, `e_pinky_bottom` ~0,
  `space_top` 1.1 only at ×6. Guesses are good enough for a test layout.
- The one-shot layer key is not modelled, so `focus-7`/`focus-12` can't be
  swept; they decide the layer key's kind and place.

