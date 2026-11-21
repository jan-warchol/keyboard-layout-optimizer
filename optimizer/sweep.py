#!/usr/bin/env python3
"""Sensitivity of the optimized layout to each cost parameter.

For every parameter, re-optimize with a low and a high value and compare
with the baseline layout:
  regret: how much worse the baseline layout scores than the new optimum,
          under the changed parameter (ms/char). Large = the parameter
          decides the layout and is worth measuring.
  moved:  share of typed characters whose slot differs from the baseline.
The baseline's own restarts give the noise level of both numbers.

  python3 optimizer/sweep.py [--restarts 3] [--steps 200000] [--only name ...]
      -> analysis/sensitivity.tsv
"""
import argparse
import multiprocessing as mp
import os
import random
import sys

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
        if k.startswith("sc_"):
            factors = (0.5, 2, 4, 6)    # the worst may be 4x or more (user)
        elif k in MEASURED:
            factors = (0.75, 1.25)
        else:
            factors = (0.5, 2)
        for f in factors:
            yield k, v * f


def job(args):
    P, seed, steps = args
    prob = Problem(P)
    slot_of, s = prob.anneal(random.Random(seed), steps)
    return slot_of, s


def moved(prob, a, b):
    """Frequency-weighted share of characters on a different slot."""
    w = prob.uni.copy()
    for u in ("palm", "other", " ", "\n", "⇥"):
        w[prob.uidx[u]] = 0
    return float((w * (a != b)).sum() / w.sum())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restarts", type=int, default=3)
    ap.add_argument("--baseline-restarts", type=int, default=8)
    ap.add_argument("--steps", type=int, default=200000)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()

    runs = [(dict(PARAMS), 100 + i, a.steps) for i in range(a.baseline_restarts)]
    vs = list(variants(a.only))
    for k, v in vs:
        P = dict(PARAMS)
        P[k] = v
        runs += [(P, 200 + i, a.steps) for i in range(a.restarts)]
    with mp.Pool() as pool:
        res = pool.map(job, runs, chunksize=1)

    base_prob = Problem(dict(PARAMS))
    base = res[:a.baseline_restarts]
    L0, s0 = min(base, key=lambda x: x[1])
    noise_regret = [s - s0 for _, s in base]
    noise_moved = [moved(base_prob, L0, L) for L, _ in base]
    print(f"baseline {s0:.2f} ms/char; restarts: regret median {np.median(noise_regret):.2f} "
          f"max {max(noise_regret):.2f}, moved median {np.median(noise_moved):.1%} max {max(noise_moved):.1%}")
    print(base_prob.show(L0))

    rows = []
    i = a.baseline_restarts
    for k, v in vs:
        group = res[i:i + a.restarts]
        i += a.restarts
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


if __name__ == "__main__":
    main()
