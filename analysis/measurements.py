#!/usr/bin/env python3
"""Analyse the key-sequence measurements in data/measurements/trials.jsonl.

  python3 analysis/measurements.py report   # phases 1 and 2a (protocol 2)
  python3 analysis/measurements.py warmup   # word pilot: how fast cycle time settles

Everything is recomputed from the raw trials; nothing is stored. Findings
are summarised in docs/measurement-plan.md.
"""
import collections
import math
import os
import statistics as st
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "measure"))
from measure import (FINGERS, LABEL, ROLL_IN, ROLL_OUT, canonical, cycle_time,  # noqa: E402
                     load_trials, phase1_plan, phase2a_plan, transitions)


def name(p):
    return " ".join(LABEL[x] for x in p)


def trials(control=False, plan=None):
    """ok protocol-2 trials; plan = value of the trial's 'plan' field, if given."""
    return [t for t in load_trials()
            if t.get("protocol", 1) >= 2 and t["status"] == "ok"
            and t["control"] == control and (plan is None or t.get("plan") == plan)]


def cycle_times(ts):
    """canonical pattern -> {session: cycle time}"""
    ct = collections.defaultdict(dict)
    for t in ts:
        c = cycle_time(t)
        if c:
            ct[canonical(t["pattern"])][t["session"]] = c
    return ct


def session_factors(ct, plan):
    """Geometric-mean ratio of each session's times to the patterns' means."""
    pm = {p: math.exp(st.mean(math.log(v) for v in ct[p].values())) for p in plan if ct[p]}
    sess = sorted({s for p in plan for s in ct[p]})
    return {s: math.exp(st.mean(math.log(ct[p][s] / pm[p])
                                for p in plan if s in ct[p] and len(ct[p]) >= 2))
            for s in sess}


def cv(values):
    return st.stdev(values) / st.mean(values)


def report():
    ts = trials()
    ct = cycle_times(ts)
    p1, p2a = phase1_plan(), phase2a_plan()

    print("REPEATABILITY: median CV of cycle time across sessions, raw -> session-corrected")
    for label, plan in (("phase 1", p1), ("phase 2a", p2a)):
        sf = session_factors(ct, plan)
        for k in sorted({len(p) for p in plan}):
            ps = [p for p in plan if len(p) == k and len(ct[p]) >= 2]
            raw = [cv(list(ct[p].values())) for p in ps]
            cor = [cv([v / sf[s] for s, v in ct[p].items()]) for p in ps]
            print(f"  {label}, {k}-key: {st.median(raw):.3f} -> {st.median(cor):.3f}  (n={len(ps)})")
        print("    session factors: " + ", ".join(f"{s[5:16]} {f:.2f}" for s, f in sf.items()))

    print("\nCONTROLS: mean cycle time per session")
    ctl = collections.defaultdict(lambda: collections.defaultdict(list))
    for t in trials(control=True):
        c = cycle_time(t)
        if c:
            ctl[t["session"]][name(t["pattern"])].append(c)
    for s, d in sorted(ctl.items()):
        print(f"  {s}  " + "   ".join(f"{k}: {st.mean(v):.0f}" for k, v in d.items()))

    print("\nPHASE 2a: cycle time per session, ratings, median time per direction")
    for p in sorted(p2a, key=lambda p: (p[0][3], p)):
        pts = [t for t in ts if canonical(t["pattern"]) == p]
        d = collections.defaultdict(list)
        for t in pts:
            for a, b, ms in transitions(t):
                d[(a, b)].append(ms)
        dirs = "  ".join(f"{LABEL[a]}>{LABEL[b]} {st.median(v):.0f}" for (a, b), v in sorted(d.items()))
        print(f"  {name(p):6} {' '.join(f'{v:4.0f}' for v in ct[p].values()):16}"
              f" r {[t['rating'] for t in pts]}  | {dirs}")

    mean = lambda p: st.mean(ct[canonical(p)].values())
    print("\nTRIPLES vs PAIRS: triple cycle / sum of its pairs' half-cycles")
    ratios = []
    for p in (p for p in p1 if len(p) == 3):
        a, b, c = p
        pred = (mean((a, b)) + mean((b, c)) + mean((a, c))) / 2
        ratios.append(mean(p) / pred)
        print(f"  {name(p):10} {mean(p):4.0f}  pairs {pred:4.0f}  ratio {mean(p) / pred:.2f}")
    print(f"  median ratio {st.median(ratios):.2f}")

    print("\nCONTEXT: median time of a transition inside triples, by the third key")
    d = collections.defaultdict(lambda: collections.defaultdict(list))
    noise = []
    for t in ts:
        p = t["pattern"]
        if len(p) != 3 or canonical(p) not in p1:
            continue
        g = collections.defaultdict(list)
        for a, b, ms in transitions(t):
            d[(a, b)][[x for x in p if x not in (a, b)][0]].append(ms)
            g[(a, b)].append(ms)
        for v in g.values():
            if len(v) >= 6:
                q = st.quantiles(v, n=4)
                noise.append(q[2] - q[0])
    spread = []
    for (a, b), v in sorted(d.items()):
        meds = {LABEL[c]: st.median(x) for c, x in v.items()}
        spread.append(max(meds.values()) - min(meds.values()))
        print(f"  {LABEL[a]:>3}>{LABEL[b]:<3} " + "  ".join(f"(…{k}) {m:4.0f}" for k, m in meds.items()))
    print(f"  median range across contexts {st.median(spread):.0f} ms;"
          f" median within-trial IQR {st.median(noise):.0f} ms")

    print("\nBIGRAM FIT on triples (cycle = sum of directed transition costs)")
    edges = [(a, b) for a in FINGERS for b in FINGERS if a != b]
    idx = {e: i for i, e in enumerate(edges)}

    def row(p):
        r = np.zeros(len(edges))
        for i in range(len(p)):
            r[idx[(p[i], p[(i + 1) % len(p)])]] += 1
        return r
    tri = [p for p in p1 if len(p) == 3]
    A, y = np.array([row(p) for p in tri]), np.array([mean(p) for p in tri])
    x, *_ = np.linalg.lstsq(A, y, rcond=None)
    print(f"  rank {np.linalg.matrix_rank(A)} of {len(edges)} (the missing 4 are per-key offsets,"
          f" which cancel in text); residual rms {np.sqrt(np.mean((A @ x - y) ** 2)):.1f} ms")
    for p in (ROLL_IN, ROLL_OUT):
        print(f"  {name(p)}: predicted {row(p) @ x:.0f}, measured "
              + " ".join(f"{v:.0f}" for v in ct[canonical(p)].values()))

    xs, ys = [], []
    for t in ts:
        c = cycle_time(t)
        if len(t["pattern"]) == 2 and c:
            xs.append(c / 2)
            ys.append(t["rating"])
    print(f"\nrating vs time per transition, 2-key trials: r = {np.corrcoef(xs, ys)[0, 1]:.2f} (n={len(xs)})")


def per_cycle(t):
    """Duration of every complete cycle of a trial (None where an error broke it)."""
    k = len(t["pattern"])
    down = {idx: d for _p, d, _u, idx in t["presses"] if idx >= 0}
    bad = set()
    for i, (_p, _d, _u, idx) in enumerate(t["presses"]):
        if idx < 0:   # an error: the cycle containing the next correct press is unreliable
            nxt = next((x[3] for x in t["presses"][i:] if x[3] >= 0), None)
            if nxt is not None:
                bad.add(nxt // k)
    return [down[(c + 1) * k] - down[c * k]
            if c * k in down and (c + 1) * k in down and c not in bad else None
            for c in range(t["cycles"] - 1)]


def warmup():
    ts = [t for t in trials() if t.get("plan") == "pilot-words"]
    if not ts:
        sys.exit("no pilot-words trials yet")
    print("WORD PILOT: cycle time relative to the trial's last-half median, by cycle")
    print("(1.00 = settled; the warm-up should cover the cycles clearly above 1)")
    by_len = collections.defaultdict(list)
    for t in ts:
        cyc = per_cycle(t)
        late = [c for c in cyc[len(cyc) // 2:] if c]
        if late:
            ref = st.median(late)
            by_len[len(t["pattern"])].append([c / ref if c else None for c in cyc])
    for k, rows in sorted(by_len.items()):
        n = max(len(r) for r in rows)
        cols = [[r[i] for r in rows if i < len(r) and r[i]] for i in range(n)]
        print(f"  {k} keys ({len(rows)} trials): "
              + " ".join(f"{st.median(c):.2f}" if c else "  - " for c in cols))
    print("\nPER TRIAL: settled cycle time, first 3 cycles relative to it, rating, errors")
    for t in ts:
        cyc = per_cycle(t)
        late = [c for c in cyc[len(cyc) // 2:] if c]
        if not late:
            continue
        ref = st.median(late)
        first = " ".join(f"{c / ref:.2f}" if c else "  - " for c in cyc[:3])
        err = sum(1 for p in t["presses"] if p[3] < 0)
        print(f"  {t['time'][11:16]} {name(t['pattern']):14} {ref:5.0f} ms  [{first}]"
              f"  rating {t['rating']}  errors {err}")
    rep = collections.defaultdict(list)
    for t in ts:
        cyc = [c for c in per_cycle(t)[len(per_cycle(t)) // 2:] if c]
        if cyc:
            rep[canonical(t["pattern"])].append(st.median(cyc))
    rep = {p: v for p, v in rep.items() if len(v) > 1}
    if rep:
        print("\nREPEATED WORDS (same session): settled cycle times")
        for p, v in rep.items():
            print(f"  {name(p):14} " + " -> ".join(f"{x:.0f}" for x in v)
                  + f"   ({(v[-1] / v[0] - 1) * 100:+.0f}%)")


if __name__ == "__main__":
    {"report": report, "warmup": warmup}[sys.argv[1] if len(sys.argv) > 1 else "report"]()
