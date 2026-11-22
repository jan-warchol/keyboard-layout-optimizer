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
    """Rating -> penalty; half ratings (3.5, since 2026-11-22) and medians
    like 3.25 interpolate linearly."""
    lo = int(r)
    return PENALTY[lo] if r == lo else PENALTY[lo] + (r - lo) * (PENALTY[lo + 1] - PENALTY[lo])


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
    """Median estimate of parameter `name` over (pattern, reference) pairs.
    A pair may also be a list of (sign, pattern) terms: a double difference
    (space_top: Space pattern minus its home-row version, minus the same
    for the ring finger in place of Space)."""
    vals = []
    for pair in pairs:
        terms = [(1, pair[0]), (-1, pair[1])] if isinstance(pair, tuple) else pair
        ms = [get(*pat) for _, pat in terms]
        if not all(ms):
            continue
        meas = sum(sg * (m[0] + k * penalty(m[1])) for (sg, _), m in zip(terms, ms))
        P0 = dict(P, **{name: 0.0})
        P1 = dict(P, **{name: 1.0})
        b = sum(sg * cycle_cost(pat, P0) for sg, pat in terms)
        a = sum(sg * cycle_cost(pat, P1) for sg, pat in terms) - b
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


def pairs_far(ci, co, rows, ref_col=None):
    """Far scissors, inner finger in column ci and outer in co, (inner row,
    outer row) in rows, both orders. Reference: home-home in the same order,
    or with ref_col the same rows with the inner finger in column ref_col."""
    out = []
    for ri, ro in rows:
        a, b = f"r{ri}c{ci}", f"r{ro}c{co}"
        a0, b0 = ((f"r{ri}c{ref_col}", b) if ref_col else (f"r2c{ci}", f"r2c{co}"))
        out += [((a, b, "t4"), (a0, b0, "t4")), ((b, a, "t4"), (b0, a0, "t4"))]
    return out


def pairs_space_top():
    """Index-middle in the top row + Space vs the home row, minus the same
    with the ring in place of Space (focus-6)."""
    out = []
    for r in (1,):
        i, m, g = f"r{r}c2", f"r{r}c3", f"r{r}c4"
        for sp, rg in (((i, m, "t4"), (i, m, g)), ((m, i, "t4"), (g, m, i))):
            sp0, rg0 = [tuple(x.replace(f"r{r}", "r2") for x in p) for p in (sp, rg)]
            out.append([(1, sp), (-1, sp0), (-1, rg), (1, rg0)])
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
    put("space_top", pairs_space_top(), "space-row, top vs home, minus the ring version")
    one = {"up": [(1, 2), (2, 3)], "down": [(2, 1), (3, 2)]}   # (inner row, outer row)
    put("sc_far_index_up", pairs_far(2, 4, one["up"]), "focus-8, one row")
    put("sc_far_ring_up", pairs_far(2, 4, one["down"]), "focus-8, one row")
    put("sc_far_middle_up", pairs_far(3, 5, one["up"]), "focus-9, one row")
    put("sc_far_pinky_up", pairs_far(3, 5, one["down"]), "focus-9, one row")
    put("sc_far_full_factor", pairs_far(2, 4, [(1, 3), (3, 1)]) + pairs_far(3, 5, [(1, 3), (3, 1)]),
        "focus-8, -9, top-bottom")
    put("lateral_ring", pairs_far(1, 4, [(r, o) for r in (1, 2, 3) for o in (1, 2, 3)
                                         if (r, o) not in ((1, 1), (3, 3))], ref_col=2),
        "focus-13 vs focus-8, same rows")
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
        # only the fitted and derived values: the rest stays with model.py
        json.dump({"k": a.k, "params": {name: P[name] for name, *_ in rows}}, f, indent=1)
    print(f"\n-> {os.path.relpath(a.out)}")


if __name__ == "__main__":
    main()
