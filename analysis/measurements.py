#!/usr/bin/env python3
"""Analyse the key-sequence measurements in data/measurements/trials.jsonl.

  python3 analysis/measurements.py report   # phases 1 and 2a (protocol 2)
  python3 analysis/measurements.py warmup [PLAN]   # word pilot (default pilot-chain):
                                                   # how fast cycle time settles
  python3 analysis/measurements.py focus    # index-middle scissors, index
                                            # lateral stretch, same-finger, layer switch

Everything is recomputed from the raw trials; nothing is stored. Findings
are summarised in docs/measurement-plan.md.
"""
import collections
import itertools
import math
import os
import statistics as st
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "measure"))
from measure import (FINGERS, LABEL, LAYER_KEY, ONESHOT_PINKY, ROLL_IN, ROLL_OUT, canonical,  # noqa: E402
                     cycle_time, focus_plan, label, layer_plan, scissors_im_plan, sf_index_plan,
                     load_trials, phase1_plan, phase2a_plan, transitions)


def name(p):
    return " ".join(label(x) for x in p)


def trials(control=False, plan=None):
    """ok trials of protocol 2 on; plan = value of the trial's 'plan' field, if
    given. Protocol-3 trials that never settled into counted cycles (the cap
    hit while lost) are left out entirely, their rating too."""
    return [t for t in load_trials()
            if t.get("protocol", 1) >= 2 and t["status"] == "ok"
            and not (t.get("protocol", 1) >= 3 and cycle_time(t) is None)
            and t["control"] == control and (plan is None or t.get("plan") == plan)]


def cycle_times(ts):
    """canonical pattern -> {session: cycle time}"""
    ct = collections.defaultdict(dict)
    for t in ts:
        c = cycle_time(t)
        if c:
            ct[canonical(t["pattern"])][t["session"]] = c
    return ct


def cycle_times_all(ts):
    """canonical pattern -> {session: median cycle time}, several trials per
    session allowed (controls run at start and end)."""
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for t in ts:
        c = cycle_time(t)
        if c:
            by[canonical(t["pattern"])][t["session"]].append(c)
    return {p: {s: st.median(v) for s, v in d.items()} for p, d in by.items()}


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
        if idx == -1:   # an error: the cycle containing the next correct press is unreliable
            nxt = next((x[3] for x in t["presses"][i:] if x[3] >= 0), None)
            if nxt is not None:
                bad.add(nxt // k)
    return [down[(c + 1) * k] - down[c * k]
            if c * k in down and (c + 1) * k in down and c not in bad else None
            for c in range(t["cycles"] - 1)]


def warmup(plan="pilot-chain"):
    ts = trials(plan=plan)
    if not ts:
        sys.exit(f"no {plan} trials yet")
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
        err = sum(1 for p in t["presses"] if p[3] == -1)
        print(f"  {t['time'][11:16]} {t.get('word') or name(t['pattern']):14} {ref:5.0f} ms  [{first}]"
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


FOCUS_PLANS = {"scissors", "scissors-im", "lateral", "sf-index", "layer", "layer-fingers",
               "space-row", "oneshot", "oneshot-space", "focus-1", "focus-2", "focus-3", "focus-4", "focus-5",
               "focus-6", "focus-7", "focus-8", "focus-9", "focus-10", "focus-11", "focus-12",
               "focus-13", "oneshot-pairs", "scissors-far", "pinky-reach", "spread-ip"}
ROW = {1: "top", 2: "home", 3: "bottom"}


def focus_data():
    """(get, info): get(*pattern) -> (session-corrected time, median rating,
    n sessions) or None, for the focus plans; info = summary line."""
    ts = [t for t in trials() if t.get("plan") in FOCUS_PLANS]
    ct = cycle_times(ts)
    ratings = collections.defaultdict(list)
    for t in ts:
        ratings[canonical(t["pattern"])].append(t["rating"])
    sessions = sorted({t["session"] for t in ts})
    # session speed from the controls (start and end of every session): the
    # focus sessions share few or no patterns with each other
    cts = [t for t in trials(control=True) if t["session"] in sessions]
    cc = cycle_times_all(cts)
    sf = session_factors(cc, list(cc)) if cc else {}
    sf = {s: sf.get(s, 1.0) for s in sessions}
    info = (f"{len(ts)} trials, {len(sessions)} sessions; session factors (controls): "
            + ", ".join(f"{s[5:16]} {f:.2f}" for s, f in sf.items()))

    def get(*pattern):
        """(time, median rating, n sessions) or None."""
        c = canonical(pattern)
        if not ct.get(c):
            return None
        v = [x / sf.get(s, 1.0) for s, x in ct[c].items()]
        return math.exp(st.mean(math.log(x) for x in v)), st.median(ratings[c]), len(v)
    return get, info


def focus():
    """Session-corrected cycle times (geometric mean over sessions, ms) and
    median ratings of the focus plans, with the differences that map onto
    the optimizer's parameters. Whole-cycle times of 'a b Spc'."""
    get, info = focus_data()
    if info.startswith("0 trials"):
        print("no trials of the focus plans yet")
        return
    print(info)

    def cell(r, ref=None):
        if r is None:
            return f"{'-':>13}"
        d = f"{r[0] - ref[0]:+5.0f}" if ref else "     "
        return f"{r[0]:4.0f}{d} ({r[1]:g})"

    print("\nINDEX-MIDDLE SCISSORS: cycle 'a b Spc' ms, diff vs home-home (median rating)")
    for order in ("index first", "middle first"):
        print(f"  {order}; rows: index, columns: middle")
        print("  " + " " * 8 + "".join(f"{ROW[rm]:>15}" for rm in (1, 2, 3)))
        for ri in (1, 2, 3):
            out = []
            for rm in (1, 2, 3):
                a, b = f"r{ri}c2", f"r{rm}c3"
                pat = (a, b, "t4") if order == "index first" else (b, a, "t4")
                ref = get(*(("r2c2", "r2c3", "t4") if order == "index first"
                            else ("r2c3", "r2c2", "t4")))
                out.append(cell(get(*pat), ref))
            print(f"  {ROW[ri]:>8}" + "".join(f"{x:>15}" for x in out))
    print("  index up + middle down: index top row with middle home/bottom (upper right);"
          "\n  middle up + index down: lower left.")

    print("\nLATERAL STRETCH: index in column 1 with middle, cycle 'a b Spc' ms,"
          "\n  diff vs the same pattern with index in column 2 (median rating)")
    for order in ("index first", "middle first"):
        print(f"  {order}; rows: index, columns: middle")
        print("  " + " " * 8 + "".join(f"{ROW[rm]:>15}" for rm in (1, 2, 3)))
        for ri in (1, 2, 3):
            out = []
            for rm in (1, 2, 3):
                m = f"r{rm}c3"
                pat, ref = (f"r{ri}c1", m), (f"r{ri}c2", m)
                if order == "middle first":
                    pat, ref = pat[::-1], ref[::-1]
                out.append(cell(get(*pat, "t4"), get(*ref, "t4")))
            print(f"  {ROW[ri]:>8}" + "".join(f"{x:>15}" for x in out))

    print("\nINDEX SAME-FINGER: cycle 'a b Spc' ms (rating), diff vs the index-middle"
          "\n  pattern with the same rows ('a m Spc', index in column 2)")
    for pat in sf_index_plan():
        pat = list(pat)
        i = pat.index("t4")
        pat = pat[i + 1:] + pat[:i + 1]
        a, b = pat[0], pat[1]
        ref = get(f"r{a[1]}c2", f"r{b[1]}c3", "t4")
        print(f"  {name(pat):12} {cell(get(*pat), ref)}")

    print(f"\nLAYER SWITCH ({LABEL[LAYER_KEY]} held): cycle 'a b Spc' ms (rating), diff vs plain")
    L = LAYER_KEY + "+"
    print(f"  {'pair':6}{'plain':>13}{'layer first':>15}{'layer second':>15}{'layer both':>15}")
    pats = layer_plan()
    for i in range(0, len(pats), 4):
        plain = [x for x in pats[i] if x != "t4"]
        a, b = (plain if canonical((plain[0], plain[1], "t4")) == pats[i]
                else plain[::-1])
        ref = get(a, b, "t4")
        row = [cell(ref), cell(get(L + a, b, "t4"), ref), cell(get(a, L + b, "t4"), ref),
               cell(get(L + a, L + b, "t4"), ref)]
        print(f"  {LABEL[a]} {LABEL[b]:4}" + "".join(f"{x:>15}" for x in row))

    print(f"\nLAYER SWITCH WITHOUT SPACE ({LABEL[LAYER_KEY]} held, thumb presses nothing else):"
          "\n  cycle ms, diff vs plain (rating); held for: which letters")
    for tri in (("r2c2", "r2c3", "r2c4"), ("r2c4", "r2c3", "r2c2")):
        ref = get(*tri)
        print(f"  {' '.join(LABEL[x] for x in tri)}")
        for mask in itertools.product((0, 1), repeat=3):
            pat = tuple(L + x if m else x for x, m in zip(tri, mask))
            which = " ".join(LABEL[x] for x, m in zip(tri, mask) if m) or "none"
            print(f"    {which:8} {cell(get(*pat), None if not any(mask) else ref)}")

    S = LAYER_KEY
    print(f"\nONE-SHOT vs HELD LAYER KEY, no Space ({LABEL[S]} tapped before each layered"
          f"\n  letter vs held through it): cycle ms, diff vs plain (rating)")
    for tri in (("r2c2", "r2c3", "r2c4"), ("r2c4", "r2c3", "r2c2")):
        ref = get(*tri)
        print(f"  {' '.join(LABEL[x] for x in tri):8}{'held':>15}{'one-shot':>15}")
        for mask in itertools.product((0, 1), repeat=3):
            if not any(mask):
                continue
            held = tuple(L + x if m else x for x, m in zip(tri, mask))
            tap = tuple(k for x, m in zip(tri, mask) for k in ((S, x) if m else (x,)))
            which = " ".join(LABEL[x] for x, m in zip(tri, mask) if m)
            print(f"    {which:6}{cell(get(*held), ref):>15}{cell(get(*tap), ref):>15}")

    P = ONESHOT_PINKY
    print(f"\nONE-SHOT ON THE PINKY ({LABEL[P]} = {P} tapped before one letter of a triple):"
          f"\n  cycle ms, diff vs plain (rating)")
    for tri in (("r2c2", "r2c3", "r2c4"), ("r2c4", "r2c3", "r2c2")):
        ref = get(*tri)
        print(f"  {' '.join(LABEL[x] for x in tri)}")
        for i in range(3):
            print(f"    {LABEL[tri[i]]:6}{cell(get(*tri[:i], P, *tri[i:]), ref):>15}")

    P = ONESHOT_PINKY
    print(f"\nONE-SHOT ON THE PINKY ({LABEL[P]} = {P}) vs THUMB ({LABEL[S]}), tapped, then"
          f"\n  two letters: cycle ms, diff vs the plain pair (rating)")
    print(f"  {'':8}{'pinky':>15}{'thumb':>15}")
    for a, b in itertools.permutations(("r2c2", "r2c3", "r2c4"), 2):
        ref = get(a, b)
        print(f"  {LABEL[a]} {LABEL[b]:5}{cell(get(P, a, b), ref):>15}"
              f"{cell(get(S, a, b), ref):>15}")


    print("\nSPACE AND ROW: index-middle + Space vs index-middle-ring, by row;"
          "\n  diff vs the home row (rating). Space stretch = Space diff - ring diff")
    for order in ("index first", "middle first"):
        print(f"  {order}{'with Space':>22}{'with ring':>15}")
        for r in (1, 2, 3):
            i, m, ring = f"r{r}c2", f"r{r}c3", f"r{r}c4"
            sp, rg = ((i, m, "t4"), (i, m, ring)) if order == "index first" else \
                ((m, i, "t4"), (ring, m, i))
            sp0, rg0 = [tuple(x.replace(f"r{r}", "r2") for x in pat) for pat in (sp, rg)]
            print(f"  {ROW[r]:>8}{'':6}{cell(get(*sp), get(*sp0)):>15}"
                  f"{cell(get(*rg), get(*rg0)):>15}")

    print("\nFAR SCISSORS (a finger skipped): cycle 'a b Spc' ms, diff vs home-home"
          "\n  in the same order (median rating); rows: inner finger, columns: outer finger")
    for label_, ci, co in (("index c2 + ring", 2, 4), ("middle + pinky", 3, 5),
                           ("index c1 + ring", 1, 4)):
        for order in ("inner first", "outer first"):
            print(f"  {label_}, {order}")
            print("  " + " " * 8 + "".join(f"{ROW[r]:>15}" for r in (1, 2, 3)))
            for ri in (1, 2, 3):
                out = []
                for ro in (1, 2, 3):
                    a, b = f"r{ri}c{ci}", f"r{ro}c{co}"
                    a0, b0 = f"r2c{ci}", f"r2c{co}"
                    pat, ref = ((a, b, "t4"), (a0, b0, "t4")) if order == "inner first" \
                        else ((b, a, "t4"), (b0, a0, "t4"))
                    out.append(cell(get(*pat), get(*ref) if pat != ref else None))
                print(f"  {ROW[ri]:>8}" + "".join(f"{x:>15}" for x in out))
    print("  index c1 + ring: diff vs home-home with the index in c1 (the c1 cost cancels);"
          "\n  compare with index c2 + ring for the extra cost of the stretch column.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"report": report, "warmup": warmup, "focus": focus}[cmd](*sys.argv[2:])
