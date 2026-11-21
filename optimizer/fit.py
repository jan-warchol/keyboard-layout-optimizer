#!/usr/bin/env python3
"""Cost parameters from the focus measurements (docs/measurement-plan.md).

Each estimate compares a measured pattern with its reference pattern from
the same plan: the measured difference in cycle time, plus the difference
in discomfort penalty × K, minus what the model already predicts for that
difference with the parameter at zero, divided by how many times the
parameter occurs in the cycle. The median over all pattern pairs is the
value. Ratings become penalties on the scale 0 1 3 6 12 (effortless …
strain; design-principles.md, 2026-11-21).

  uv run optimizer/fit.py [--k 50] [--out optimizer/fitted.json]

Parameters the focus plans don't measure keep the guesses of model.py,
except where noted in DERIVED.
"""
import argparse
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "analysis"))
sys.path.insert(0, os.path.join(HERE, "..", "measure"))
from measure import LAYER_KEY, key_of, mod_of  # noqa: E402
from measurements import focus_data  # noqa: E402
from model import PARAMS, pos_cost  # noqa: E402

PENALTY = {1: 0, 2: 1, 3: 3, 4: 6, 5: 12}


def penalty(r):
    """Rating -> penalty; medians like 2.5 interpolate."""
    lo = int(r)
    return PENALTY[lo] if r == lo else (PENALTY[lo] + PENALTY[lo + 1]) / 2


def cycle_cost(pattern, P):
    """Model cost of one pass through a cyclic pattern; 'mod+pos' = layer 2."""
    total = 0.0
    for i, e in enumerate(pattern):
        prev = pattern[i - 1]
        if key_of(prev) == LAYER_KEY and not mod_of(prev):
            continue        # tapped layer key (one-shot): not modelled yet
        c = pos_cost(key_of(prev), key_of(e), P)
        if mod_of(e):
            c += P["layer_cont"] if mod_of(prev) else P["layer"]
        total += c
    return total


def estimate(name, pairs, get, k, P):
    """Median estimate of parameter `name` over (pattern, reference) pairs."""
    vals = []
    for pat, ref in pairs:
        m, r = get(*pat), get(*ref)
        if not m or not r:
            continue
        meas = m[0] - r[0] + k * (penalty(m[1]) - penalty(r[1]))
        P0 = dict(P, **{name: 0.0})
        P1 = dict(P, **{name: 1.0})
        b = cycle_cost(pat, P0) - cycle_cost(ref, P0)
        a = (cycle_cost(pat, P1) - cycle_cost(ref, P1)) - b
        if a > 0:
            vals.append((meas - b) / a)
    return (st.median(vals), len(vals)) if vals else (None, 0)


def pairs_scissor(rows):
    """Index-middle patterns with (index row, middle row) in rows, both orders,
    against home-home in the same order."""
    out = []
    for ri, rm in rows:
        a, b = f"r{ri}c2", f"r{rm}c3"
        out += [((a, b, "t4"), ("r2c2", "r2c3", "t4")), ((b, a, "t4"), ("r2c3", "r2c2", "t4"))]
    return out


def pairs_lateral():
    out = []
    for ri in (1, 2, 3):
        for rm in (1, 2, 3):
            m = f"r{rm}c3"
            out += [((f"r{ri}c1", m, "t4"), (f"r{ri}c2", m, "t4")),
                    ((m, f"r{ri}c1", "t4"), (m, f"r{ri}c2", "t4"))]
    return out


def pairs_sf():
    sf = [("r1c2", "r2c2"), ("r2c2", "r3c2"), ("r2c1", "r2c2"), ("r2c1", "r1c2"), ("r2c1", "r3c2")]
    out = []
    for x, y in sf:
        for a, b in ((x, y), (y, x)):
            out.append(((a, b, "t4"), (f"r{a[1]}c2", f"r{b[1]}c3", "t4")))
    return out


def pairs_layer(n_held):
    """Layer patterns without Space (layer-fingers): n_held consecutive letters
    of 'n r l' (both orders) on layer 2, against the plain triple."""
    L = LAYER_KEY + "+"
    out = []
    for tri in (("r2c2", "r2c3", "r2c4"), ("r2c4", "r2c3", "r2c2")):
        for s in range(3):
            held = {(s + j) % 3 for j in range(n_held)}
            out.append((tuple(L + x if i in held else x for i, x in enumerate(tri)), tri))
    return out


def fit(k):
    get, info = focus_data()
    P = dict(PARAMS)
    rows = []

    def put(name, pairs, note):
        v, n = estimate(name, pairs, get, k, P)
        if v is not None:
            rows.append((name, PARAMS[name], v, n, note))
            P[name] = max(0.0, v)

    # order matters a little: later estimates use earlier values
    put("layer", pairs_layer(1), "layer-fingers, one letter on layer 2")
    put("layer_cont", pairs_layer(2), "layer-fingers, two letters (one hold)")
    put("sc_index_up", pairs_scissor([(1, 2), (2, 3)]), "scissors-im, one row")
    put("sc_middle_up_i", pairs_scissor([(2, 1), (3, 2)]), "scissors-im, one row")
    put("sc_full_factor", pairs_scissor([(1, 3)]), "scissors-im, index top + middle bottom")
    put("lateral", pairs_lateral(), "lateral vs index in column 2")
    put("sf_index", pairs_sf(), "sf-index vs index-middle, same rows")
    # derived *(guess)*
    derived = {
        # same thumb movement as the layer key
        "shift": P["layer"], "shift_cont": P["layer_cont"],
        # the user: middle-ring scissors (both directions) and ring up +
        # pinky down are similarly straining as index up + middle down
        "sc_middle_up_r": P["sc_index_up"], "sc_ring_up_m": P["sc_index_up"],
        "sc_ring_up_p": P["sc_index_up"],
        "sc_pinky_up": max(PARAMS["sc_pinky_up"], P["sc_index_up"]),
    }
    for name, v in derived.items():
        rows.append((name, PARAMS[name], v, 0, "derived (guess)"))
        P[name] = v
    return P, rows, info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=float, default=50, help="ms per discomfort penalty step")
    ap.add_argument("--out", default=os.path.join(HERE, "fitted.json"))
    a = ap.parse_args()
    P, rows, info = fit(a.k)
    print(info)
    print(f"k = {a.k:g} ms per penalty step\n")
    print(f"{'param':16}{'guess':>8}{'fitted':>9}{'pairs':>7}   source")
    for name, old, new, n, note in rows:
        print(f"{name:16}{old:8g}{new:9.1f}{n:7d}   {note}")
    with open(a.out, "w") as f:
        json.dump({"k": a.k, "params": P}, f, indent=1)
    print(f"\n-> {os.path.relpath(a.out)}")


if __name__ == "__main__":
    main()
