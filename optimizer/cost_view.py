#!/usr/bin/env python3
"""Cost model as data for the cost visualization (optimizer/cost_view.html).

Every transition cost of model.pos_cost is a sum of terms, each the value
of one parameter times a multiplier (the full-scissor and bottom-row factors
only scale another parameter's term). So a parameter's share of a cost is
cost(P) - cost(P with that parameter at 0). Each share is then split into
  time        measured time (phase 1-2a medians, or the time part of a fit),
  discomfort  measured discomfort (fit with ratings minus the fit without),
  guess       not measured (guesses and values derived from other fits).

  uv run optimizer/cost_view.py [--out analysis/cost-view.html]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fit import fit  # noqa: E402
from model import GRID, PARAMS, effort, pos_cost  # noqa: E402

FACTORS = {"sc_full_factor", "sc_far_full_factor", "spread_bottom_factor"}
# Measured as plain time in phases 1-2a (docs/measurement-plan.md).
MEASURED_TIME = {"repeat_index", "repeat_middle", "repeat_ring", "repeat_pinky", "repeat_thumb",
                 "sf_middle", "sf_ring", "sf_pinky", "sf_dist_index", "sf_dist_middle",
                 "sf_dist_ring", "sf_dist_pinky", "outward", "to_space", "from_space",
                 "space_finger_step"}
POSITIONS = ["r0c0", "r1c0", "r3c0"] + GRID + ["t4"]
LABELS = {"r0c0": "Tab", "r1c0": "Ent", "r3c0": "Bsp", "t4": "Spc"}


def split(P0, P50, rows):
    """param -> (kind, time share): kind 'fit' / 'time' / 'guess'."""
    fitted = {name for name, *_rest, note in rows if not note.startswith("derived")}
    out = {}
    for name in P50:
        if name in FACTORS:
            continue
        if name in fitted:
            v, t = P50[name], max(0.0, P0[name])
            out[name] = ("fit", min(t, v) / v if v > 0 else 1.0)
        elif name in MEASURED_TIME:
            out[name] = ("time", 1.0)
        else:
            out[name] = ("guess", 0.0)
    return out


def terms(p, q, P):
    """[(param, share)] of pos_cost(p, q), shares > 0.05 ms."""
    full = pos_cost(p, q, P)
    out = []
    for name in P:
        if name in FACTORS or not P[name]:
            continue
        d = full - pos_cost(p, q, dict(P, **{name: 0.0}))
        if abs(d) > 0.05:
            out.append((name, round(d, 1)))
    assert abs(sum(d for _, d in out) - full) < 1, (p, q, out, full)
    return out


def layout_labels(path):
    lay = json.load(open(path))
    base = {k["pos"]: k["char"] for k in lay["keys"] if k["layer"] == 0 and k["shift"] == 0}
    l2 = {k["pos"]: k["char"] for k in lay["keys"] if k["layer"] == 1 and k["shift"] == 0}
    return {"base": base, "l2": l2}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "..", "analysis", "cost-view.html"))
    ap.add_argument("--k", type=float, default=50)
    a = ap.parse_args()
    P50, rows, info = fit(a.k)
    P0, _, _ = fit(0)
    kinds = split(P0, P50, rows)
    P = dict(PARAMS, **P50)
    data = {
        "k": a.k,
        "info": info.split(";")[0],
        "positions": POSITIONS,
        "labels": LABELS,
        "kinds": kinds,
        "values": {n: round(v, 2) for n, v in P.items()},
        "guesses": {n: v for n, v in PARAMS.items()},
        "effort": {p: round(effort(p, P), 1) for p in POSITIONS if p[0] == "r"},
        "cost": {p: {q: terms(p, q, P) for q in POSITIONS} for p in POSITIONS},
        "layouts": {
            "test 2 (2026-11-22)": layout_labels(os.path.join(HERE, "layouts", "2026-11-22-oneshot.json")),
            "test 1 (2026-11-21)": layout_labels(os.path.join(HERE, "layouts", "2026-11-21-oneshot.json")),
        },
    }
    tpl = open(os.path.join(HERE, "cost_view.html")).read()
    html = tpl.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    with open(a.out, "w") as f:
        f.write(html)
    print(f"-> {os.path.relpath(a.out)} ({len(html) // 1024} kB)")


if __name__ == "__main__":
    main()
