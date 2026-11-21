#!/usr/bin/env python3
"""Simulated annealing over letter and symbol placement.

Score = Σ bigram frequency × transition cost between their slots (+ the
Polish-letter preference), in ms per typed character.

  python3 optimizer/anneal.py [--restarts 4] [--steps 200000] [--set name=value ...]
"""
import argparse
import json
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import FIXED, GRID, PARAMS, PINNED_POS, PSEUDO, Slots  # noqa: E402

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis", "corpus")
POLISH = dict(zip("ąćęłńóśźż", "acelnoszx"))
LETTERS = list("abcdefghijklmnopqrstuvwxyz") + list(POLISH)
BASE_ONLY = {"z"}          # pinned to the base layer (design-principles.md)
N_SYMBOL_HALVES = None     # computed: free halves after letters


def load(n):
    out = {}
    with open(os.path.join(CORPUS, f"{n}grams.tsv"), encoding="utf-8") as f:
        for line in f:
            k, v = line.rstrip("\n").split("\t")
            out[json.loads(k)] = float(v)
    return out


class Problem:
    def __init__(self, P):
        self.P = P
        self.S = Slots(P)
        uni, bi = load(1), load(2)
        pinned = {ch for d in PINNED_POS.values() for ch in d.values()}
        n_cells = len(GRID) * 2 - 2 * len(PINNED_POS)
        free_halves = 2 * (n_cells - len(LETTERS)) + len(PINNED_POS) * 2
        syms = [c for c, _ in sorted(uni.items(), key=lambda x: -x[1])
                if not c.isalnum() and c not in FIXED and c not in pinned and c.isprintable()
                and len(c) == 1 and c not in "⎘"][:free_halves]
        self.symbols = syms
        # units: one per character we place or pin, plus pseudo units
        self.units = (LETTERS + [c.upper() for c in LETTERS] + syms + sorted(pinned)
                      + list(FIXED) + PSEUDO)
        self.uidx = {u: i for i, u in enumerate(self.units)}

        def unit(ch):
            if ch in self.uidx:
                return self.uidx[ch]
            return self.uidx["palm"] if ch.isdigit() else self.uidx["other"]

        n = len(self.units)
        self.F = np.zeros((n, n))
        for k, v in bi.items():
            self.F[unit(k[0]), unit(k[1])] += v
        self.uni = np.zeros(n)
        for k, v in uni.items():
            self.uni[unit(k)] += v
        # fixed slots
        self.fixed_slot = {}
        for ch, pos in FIXED.items():
            self.fixed_slot[self.uidx[ch]] = self.S.index[(pos, 0, 0)]
        for p in PSEUDO:
            self.fixed_slot[self.uidx[p]] = self.S.index[(p, 0, 0)]
        for pos, d in PINNED_POS.items():
            for (layer, shift), ch in d.items():
                self.fixed_slot[self.uidx[ch]] = self.S.index[(pos, layer, shift)]
        self.cells = [(pos, l) for pos in GRID for l in (0, 1) if pos not in PINNED_POS]
        self.sym_halves = ([self.S.index[(pos, l, s)] for pos, l in self.cells for s in (0, 1)]
                           + [self.S.index[(pos, l, s)] for pos in PINNED_POS for l in (0, 1)
                              for s in (0, 1) if (l, s) not in PINNED_POS[pos]])
        self.pl = [(self.uidx[p], self.uidx[p.upper()], self.uidx[b]) for p, b in POLISH.items()]

    # state: slot_of (unit -> slot), half (slot -> unit or -1)
    def random_state(self, rng):
        slot_of = np.zeros(len(self.units), dtype=int)
        for u, s in self.fixed_slot.items():
            slot_of[u] = s
        cells = list(self.cells)
        rng.shuffle(cells)
        base = [c for c in cells if c[1] == 0]
        used = set()
        letters = sorted(LETTERS, key=lambda l: l not in BASE_ONLY)
        for l in letters:
            pool = base if l in BASE_ONLY else cells
            c = next(c for c in pool if c not in used)
            used.add(c)
            lo, up = self.S.cell(*c)
            slot_of[self.uidx[l]], slot_of[self.uidx[l.upper()]] = lo, up
        occupied = {slot_of[self.uidx[x]] for x in LETTERS + [l.upper() for l in LETTERS]}
        halves = [h for h in self.sym_halves if h not in occupied]
        rng.shuffle(halves)
        for sym, h in zip(self.symbols, halves):
            slot_of[self.uidx[sym]] = h
        return slot_of

    def score(self, slot_of):
        C = self.S.C[np.ix_(slot_of, slot_of)]
        return float((self.F * C).sum()) + self.polish(slot_of)

    def polish(self, slot_of):
        s = 0.0
        for p, P_, b in self.pl:
            lo, up = self.S.slots[slot_of[p]], self.S.slots[slot_of[b]]
            if not (lo[0] == up[0] and lo[1] == 1):
                s += self.P["polish_off"] * (self.uni[p] + self.uni[P_])
        return s

    def part(self, U, slot_of):
        """Bigram cost of all bigrams touching units U."""
        C, F = self.S.C, self.F
        su = slot_of[U]
        rows = (F[U, :] * C[su][:, slot_of]).sum()
        cols = (F[:, U] * C[slot_of][:, su]).sum()
        both = (F[np.ix_(U, U)] * C[np.ix_(su, su)]).sum()
        return rows + cols - both

    def delta(self, old, new, U):
        return (self.part(U, new) - self.part(U, old)
                + self.polish(new) - self.polish(old))

    def neighbour(self, slot_of, rng):
        """Swap two letter cells (whole cells, both layers allowed) or two symbol halves."""
        new = slot_of.copy()
        slot_unit = {s: u for u, s in enumerate(slot_of)}
        if rng.random() < 0.6:
            c1, c2 = rng.sample(self.cells, 2)
            for s in (0, 1):
                a, b = self.S.index[(c1[0], c1[1], s)], self.S.index[(c2[0], c2[1], s)]
                ua, ub = slot_unit.get(a), slot_unit.get(b)
                if ua is not None:
                    new[ua] = b
                if ub is not None:
                    new[ub] = a
            for z in BASE_ONLY:
                if self.S.slots[new[self.uidx[z]]][1] != 0:
                    return None
            return new, np.nonzero(new != slot_of)[0]
        a, b = rng.sample(self.sym_halves, 2)
        ua, ub = slot_unit.get(a), slot_unit.get(b)
        letters = set(range(2 * len(LETTERS)))
        # a symbol half can't be swapped with half of a letter cell
        if ua in letters or ub in letters or (ua is None and ub is None):
            return None
        if ua is not None:
            new[ua] = b
        if ub is not None:
            new[ub] = a
        return new, np.array([u for u in (ua, ub) if u is not None])

    def anneal(self, rng, steps, t0=3.0, t1=0.005):
        cur = self.random_state(rng)
        cs = self.score(cur)
        best, bs = cur, cs
        for i in range(steps):
            t = t0 * (t1 / t0) ** (i / steps)
            mv = self.neighbour(cur, rng)
            if mv is None or len(mv[1]) == 0:
                continue
            nb = mv[0]
            # full rescoring: at this size it is faster than self.delta()
            d = self.score(nb) - cs
            if d <= 0 or rng.random() < math.exp(-d / t):
                cur, cs = nb, cs + d
                if cs < bs - 1e-9:
                    best, bs = cur, cs
        return best, self.score(best)

    def layout(self, slot_of):
        """(pos, layer, shift) -> character"""
        return {self.S.slots[s]: self.units[u] for u, s in enumerate(slot_of)
                if self.S.slots[s][0] in GRID}

    def show(self, slot_of):
        lay = self.layout(slot_of)
        lines = []
        for layer in (0, 1):
            lines.append(["base layer (shifted above)", "layer 2 (shifted above)"][layer])
            for r in range(4):
                top, bot = [], []
                for c in range(1, 7):
                    pos = f"r{r}c{c}"
                    lo = lay.get((pos, layer, 0), "·")
                    up = lay.get((pos, layer, 1), "·")
                    if lo.isalpha() and up == lo.upper():
                        up = " "
                    top.append(f"{up:^4}")
                    bot.append(f"{lo:^4}")
                lines.append("  " + "".join(top))
                lines.append("  " + "".join(bot))
            lines.append("")
        return "\n".join(lines)


def run(P, restarts, steps, seed=0):
    prob = Problem(P)
    results = []
    for i in range(restarts):
        rng = random.Random(seed + i)
        results.append(prob.anneal(rng, steps))
    results.sort(key=lambda x: x[1])
    return prob, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--restarts", type=int, default=4)
    ap.add_argument("--steps", type=int, default=200000)
    ap.add_argument("--set", nargs="*", default=[])
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    P = dict(PARAMS)
    for kv in a.set:
        k, v = kv.split("=")
        assert k in P, k
        P[k] = float(v)
    prob, res = run(P, a.restarts, a.steps, a.seed)
    print("symbols placed:", "".join(prob.symbols))
    for slot_of, s in res:
        print(f"score {s:.2f} ms/char")
    print(prob.show(res[0][0]))


if __name__ == "__main__":
    main()
