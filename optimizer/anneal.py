#!/usr/bin/env python3
"""Simulated annealing over letter and symbol placement.

Score = Σ bigram frequency × transition cost between their slots (+ the
Polish-letter preference), in ms per typed character.

  uv run optimizer/anneal.py [--restarts 4] [--steps 200000] [--set name=value ...]
                             [--params optimizer/fitted.json]
"""
import argparse
import json
import os
import random
import sys

import numpy as np
from numba import njit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from model import FIXED, GRID, PARAMS, PINNED_POS, PSEUDO, Slots  # noqa: E402

CORPUS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis", "corpus")
POLISH = dict(zip("ąćęłńóśźż", "acelnoszx"))
LETTERS = list("abcdefghijklmnopqrstuvwxyz") + list(POLISH)
BASE_ONLY = {"z"}          # pinned to the base layer (design-principles.md)
# Number-row keys too awkward for letters (design-principles.md, base layer):
# only the middle-finger key (c3) and the outer key (c6) take letters.
NO_LETTER_POS = {"r0c1", "r0c2", "r0c4", "r0c5"}
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
            pool = [c for c in (base if l in BASE_ONLY else cells) if c[0] not in NO_LETTER_POS]
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

    def arrays(self):
        """Flat arrays for the compiled loop."""
        if getattr(self, "_arrays", None) is None:
            S = self.S
            n_slots = len(S.slots)
            pos_ids = {}
            slot_pos = np.array([pos_ids.setdefault(p, len(pos_ids)) for p, _, _ in S.slots])
            slot_layer = np.array([l for _, l, _ in S.slots])
            cell_slots = np.array([S.cell(*c) for c in self.cells])
            pl = np.array(self.pl, dtype=np.int64)
            pl_w = np.array([self.P["polish_off"] * (self.uni[p] + self.uni[P_])
                             for p, P_, _ in self.pl])
            # sparse bigrams per unit: neighbours v with F[u,v] or F[v,u] > 0
            F = self.F
            nb_ptr, nb_v, nb_out, nb_in = [0], [], [], []
            for u in range(len(F)):
                vs = np.nonzero((F[u] + F[:, u]) > 0)[0]
                nb_v += list(vs)
                nb_out += list(F[u, vs])
                nb_in += list(F[vs, u])
                nb_ptr.append(len(nb_v))
            self._arrays = (np.ascontiguousarray(F), np.ascontiguousarray(S.C),
                            np.array(nb_ptr), np.array(nb_v, dtype=np.int64),
                            np.array(nb_out), np.array(nb_in),
                            cell_slots, np.array(self.sym_halves), 2 * len(LETTERS),
                            np.array([self.uidx[z] for z in BASE_ONLY]),
                            np.array([p in NO_LETTER_POS for p, _, _ in S.slots]),
                            slot_pos, slot_layer, pl, pl_w, n_slots)
        return self._arrays

    def anneal(self, rng, steps, t0=3.0, t1=0.005, start=None):
        """Simulated annealing from a random state (or from `start`); rng
        seeds both the start state and the compiled loop."""
        cur = self.random_state(rng) if start is None else start.copy()
        best, bs = _anneal(cur.astype(np.int64), steps, t0, t1, rng.getrandbits(31),
                           *self.arrays())
        s = self.score(best)
        assert abs(s - bs) < 1e-6 * max(1.0, abs(s)), (s, bs)   # incremental == full
        return best, s

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


@njit(cache=True)
def _polish(slot_of, slot_pos, slot_layer, pl, pl_w):
    s = 0.0
    for k in range(pl.shape[0]):
        a, b = slot_of[pl[k, 0]], slot_of[pl[k, 2]]
        if not (slot_pos[a] == slot_pos[b] and slot_layer[a] == 1):
            s += pl_w[k]
    return s


@njit(cache=True)
def _part(U, nu, slot_of, F, C, nb_ptr, nb_v, nb_out, nb_in):
    """Bigram cost of all bigrams touching the units U[:nu]."""
    s = 0.0
    for k in range(nu):
        u = U[k]
        su = slot_of[u]
        for j in range(nb_ptr[u], nb_ptr[u + 1]):
            sv = slot_of[nb_v[j]]
            s += nb_out[j] * C[su, sv] + nb_in[j] * C[sv, su]
    for k in range(nu):
        for m in range(nu):
            s -= F[U[k], U[m]] * C[slot_of[U[k]], slot_of[U[m]]]
    return s


@njit(cache=True)
def _anneal(slot_of, steps, t0, t1, seed, F, C, nb_ptr, nb_v, nb_out, nb_in, cell_slots, sym_halves, n_letter_units,
            base_only, no_letter, slot_pos, slot_layer, pl, pl_w, n_slots):
    """Compiled annealing loop with incremental scoring. Moves as before:
    60 % swap two letter cells (both halves), else swap two symbol halves
    (neither may hold a letter, not both empty)."""
    np.random.seed(seed)
    n = slot_of.shape[0]
    unit_at = np.full(n_slots, -1, np.int64)
    for u in range(n):
        unit_at[slot_of[u]] = u
    cur = 0.0
    for u in range(n):
        for v in range(n):
            cur += F[u, v] * C[slot_of[u], slot_of[v]]
    cur += _polish(slot_of, slot_pos, slot_layer, pl, pl_w)
    best = slot_of.copy()
    bs = cur
    U = np.empty(4, np.int64)
    A = np.empty(4, np.int64)      # slots swapped pairwise: A[2k] <-> A[2k+1]
    n_cells = cell_slots.shape[0]
    n_sym = sym_halves.shape[0]
    ratio = t1 / t0
    for i in range(steps):
        t = t0 * ratio ** (i / steps)
        if np.random.random() < 0.6:
            c1 = np.random.randint(n_cells)
            c2 = np.random.randint(n_cells - 1)
            if c2 >= c1:
                c2 += 1
            A[0], A[1] = cell_slots[c1, 0], cell_slots[c2, 0]
            A[2], A[3] = cell_slots[c1, 1], cell_slots[c2, 1]
            npairs = 2
        else:
            h1 = np.random.randint(n_sym)
            h2 = np.random.randint(n_sym - 1)
            if h2 >= h1:
                h2 += 1
            a, b = sym_halves[h1], sym_halves[h2]
            ua, ub = unit_at[a], unit_at[b]
            if (ua == -1 and ub == -1) or (0 <= ua < n_letter_units) or (0 <= ub < n_letter_units):
                continue
            A[0], A[1] = a, b
            npairs = 1
        nu = 0
        for k in range(2 * npairs):
            if unit_at[A[k]] != -1:
                U[nu] = unit_at[A[k]]
                nu += 1
        if nu == 0:
            continue
        old = _part(U, nu, slot_of, F, C, nb_ptr, nb_v, nb_out, nb_in) + _polish(slot_of, slot_pos, slot_layer, pl, pl_w)
        for k in range(npairs):
            a, b = A[2 * k], A[2 * k + 1]
            ua, ub = unit_at[a], unit_at[b]
            if ua != -1:
                slot_of[ua] = b
            if ub != -1:
                slot_of[ub] = a
            unit_at[a], unit_at[b] = ub, ua
        ok = True
        for z in base_only:
            if slot_layer[slot_of[z]] != 0:
                ok = False
        for k in range(nu):
            if U[k] < n_letter_units and no_letter[slot_of[U[k]]]:
                ok = False
        d = 0.0
        if ok:
            d = _part(U, nu, slot_of, F, C, nb_ptr, nb_v, nb_out, nb_in) + _polish(slot_of, slot_pos, slot_layer, pl, pl_w) - old
        if ok and (d <= 0 or np.random.random() < np.exp(-d / t)):
            cur += d
            if cur < bs - 1e-9:
                bs = cur
                best[:] = slot_of
        else:                       # undo
            for k in range(npairs):
                a, b = A[2 * k], A[2 * k + 1]
                ua, ub = unit_at[a], unit_at[b]
                if ua != -1:
                    slot_of[ua] = b
                if ub != -1:
                    slot_of[ub] = a
                unit_at[a], unit_at[b] = ub, ua
    return best, bs


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
    ap.add_argument("--params", help="JSON from optimizer/fit.py (fitted parameters)")
    a = ap.parse_args()
    P = dict(PARAMS)
    if a.params:
        with open(a.params) as f:
            P.update(json.load(f)["params"])
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
