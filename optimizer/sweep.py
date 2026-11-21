#!/usr/bin/env python3
"""Sensitivity of the optimized layout to each cost parameter.

For every parameter, re-optimize with a low and a high value and compare
with the baseline layout:
  regret: how much worse the baseline layout scores than the new optimum,
          under the changed parameter (ms/char). Large = the parameter
          decides the layout and is worth measuring.
  moved:  share of typed characters whose slot differs from the baseline.
The baseline's own restarts give the noise level of both numbers.
Each variant runs `restarts` cold starts and as many warm starts from the
baseline layout (t0 = 1), so regret >= 0 and its noise is ~0.05 ms/char.

  uv run optimizer/sweep.py [--restarts 4] [--steps 1000000] [--only name ...]
      -> analysis/sensitivity.tsv
"""
import argparse
import multiprocessing as mp
import os
import random
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from anneal import Problem  # noqa: E402
from model import PARAMS  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis", "sensitivity.tsv")
# Parameters with phase 1-2a data behind them: varied ±25%; the rest ×0.5 / ×2.
MEASURED = {k for k in PARAMS if k.startswith(("repeat_", "sf_")) and "dist" not in k} | {
    "outward", "ring_pinky", "from_space", "to_space",
    "df_base"}   # phase-1 triples: 112-150 ms per different-finger transition


def variants(only):
    for k, v in PARAMS.items():
        if only and k not in only:
            continue
        if k == "sc_full_factor":
            factors = (2 / v, 4 / v, 5 / v)
        elif k.startswith("sc_"):
            factors = (0.5, 2, 4, 6)    # the worst may be 4x or more (user)
        elif k in MEASURED:
            factors = (0.75, 1.25)
        else:
            factors = (0.5, 2)
        for f in factors:
            yield k, v * f


def job(args):
    P, seed, steps, t0, start = args
    prob = Problem(P)
    return prob.anneal(random.Random(seed), steps, t0=t0, start=start)


def moved(prob, a, b):
    """Frequency-weighted share of characters on a different slot."""
    w = prob.uni.copy()
    for u in ("palm", "other", " ", "\n", "⇥"):
        w[prob.uidx[u]] = 0
    return float((w * (a != b)).sum() / w.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restarts", type=int, default=4)
    ap.add_argument("--baseline-restarts", type=int, default=16)
    ap.add_argument("--steps", type=int, default=1000000)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    t_start = time.time()

    Problem(dict(PARAMS)).anneal(random.Random(0), 10)     # compile once (cached)
    vs = list(variants(a.only))
    with mp.Pool() as pool:
        base = pool.map(job, [(dict(PARAMS), 100 + i, 2 * a.steps, 3.0, None)
                              for i in range(a.baseline_restarts)], chunksize=1)
        L0, s0 = min(base, key=lambda x: x[1])
        runs = []
        for k, v in vs:
            P = dict(PARAMS)
            P[k] = v
            runs += [(P, 200 + i, a.steps, 3.0, None) for i in range(a.restarts)]
            runs += [(P, 300 + i, a.steps, 1.0, L0) for i in range(a.restarts)]
        res = pool.map(job, runs, chunksize=1)

    base_prob = Problem(dict(PARAMS))
    noise_regret = [s - s0 for _, s in base]
    noise_moved = [moved(base_prob, L0, L) for L, _ in base]
    print(f"baseline {s0:.2f} ms/char; restarts: regret median {np.median(noise_regret):.2f} "
          f"max {max(noise_regret):.2f}, moved median {np.median(noise_moved):.1%} max {max(noise_moved):.1%}")
    print(base_prob.show(L0))

    rows = []
    i = 0
    for k, v in vs:
        group = res[i:i + 2 * a.restarts]
        i += 2 * a.restarts
        P = dict(PARAMS)
        P[k] = v
        prob = Problem(P)
        Lp, sp = min(group, key=lambda x: x[1])
        regret = prob.score(L0) - sp
        rows.append((k, PARAMS[k], v, regret, moved(prob, L0, Lp), sp))
    with open(OUT, "w") as f:
        f.write(f"# baseline {s0:.3f} ms/char; noise regret max {max(noise_regret):.3f}, "
                f"moved max {max(noise_moved):.3f}\n")
        f.write("param\tbase\tvalue\tregret_ms\tmoved\tscore\n")
        for r in sorted(rows, key=lambda r: -r[3]):
            f.write("%s\t%g\t%g\t%.3f\t%.3f\t%.3f\n" % r)
    by = {}
    for k, _, v, reg, mv, _ in rows:
        by.setdefault(k, []).append((v, reg, mv))
    print(f"{'param':18s} {'base':>6s}   value: regret moved ...")
    for k, lst in sorted(by.items(), key=lambda kv: -max(x[1] for x in kv[1])):
        cells = "   ".join(f"{v:6g}: {r:5.2f} {m:5.1%}" for v, r, m in lst)
        print(f"{k:18s} {PARAMS[k]:6g}   {cells}")
    print(f"{len(runs) + len(base)} runs in {time.time() - t_start:.0f} s")


if __name__ == "__main__":
    main()
