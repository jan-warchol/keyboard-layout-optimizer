# Optimizer: corpus, cost model, sensitivity

How layouts are scored and searched, and what the sensitivity analysis has
shown. The *why* of the layout is in [design-principles.md](design-principles.md),
the measurements in [measurement-plan.md](measurement-plan.md). Claims marked
*(guess)* have no measurement behind them.

## Pipeline

```sh
python3 analysis/corpus.py            # -> analysis/corpus/{1,2,3}grams.tsv
python3 analysis/corpus_report.py OUT.json   # per-source statistics (review page)
python3 optimizer/anneal.py [--restarts 4] [--steps 300000] [--set name=value ...]
python3 optimizer/sweep.py [--only param ...] [--restarts 6] [--steps 400000]
                                      # -> analysis/sensitivity.tsv
```

Our own optimizer instead of the dariogoetz one: its metrics are built for
two-handed layouts and it needs a Rust toolchain; ours scores with the
transition-cost model directly. Python is too slow for sweeps (~15k
annealing steps/s per core, a sweep of 200+ runs takes ~30 min on 8
cores): port the annealing loop to numba with incremental scoring (decided
2026-11-21: one language; Rust would be similarly fast).

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
