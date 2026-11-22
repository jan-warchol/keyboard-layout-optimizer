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
# only the middle-finger key (c3) takes letters (c6 excluded by the user,
# 2026-11-21).
NO_LETTER_POS = {"r0c1", "r0c2", "r0c4", "r0c5", "r0c6"}
# Symbols come as key-code pairs: Shift gives the US partner (a key sends a
# key code; other pairings need the CharShift plugin). Each pair fills a
# whole key, like a letter and its capital. ( and ) are shifted-only in US
# and the firmware has no CharShift, so each takes a key of its own (loose).
# /? and \| are pinned (model.PINNED_POS).
PAIRS = ["-_", ".>", ",<", "'\"", ";:", "=+", "`~", "]}", "[{"]
ITEMS = [(l, l.upper()) for l in LETTERS] + [(p[0], p[1]) for p in PAIRS]
# Polish one-shot key (design-principles.md, 2026-11-21): tapped before a
# Latin letter it gives the Polish letter on the same physical key, so the
# Polish letters need no keys of their own. Its shifted half is unused.
DK, DK_UP = "ℙ", "ℙ⇧"
LATIN = list("abcdefghijklmnopqrstuvwxyz")
# Shifted digits 1 2 3 4 5 8 on the function layer give these (user,
# 2026-11-21): typed like digits (palm), not placed in the grid.
SHIFTED_DIGITS = set("!@#$%*")
# Space on a finger key in the grid instead of the thumb (--space grid): a
# whole key on the base layer, its shifted half unused.
SPACE_UP = "␣⇧"


def load(n):
    out = {}
    with open(os.path.join(CORPUS, f"{n}grams.tsv"), encoding="utf-8") as f:
        for line in f:
            k, v = line.rstrip("\n").split("\t")
            out[json.loads(k)] = float(v)
    return out


class Problem:
    def __init__(self, P, polish="oneshot", space="thumb", dk_pos=None):
        """polish: "oneshot" (Polish letters = one-shot key + Latin letter) or
        "layer" (Polish letters on their own keys, preferably under their
        Latin letters on layer 2)."""
        self.P = P
        self.mode = polish
        fixed = dict(FIXED)
        if space == "grid":
            del fixed[" "]
        self.fixed = fixed
        self.S = Slots(P)
        uni, bi = load(1), load(2)
        if polish == "oneshot":
            self.items = [(l, l.upper()) for l in LATIN] + [(p[0], p[1]) for p in PAIRS] \
                + ([] if dk_pos else [(DK, DK_UP)])
            self.base_only = BASE_ONLY | ({DK} if not dk_pos else set())
        else:
            self.items = ITEMS
            self.base_only = BASE_ONLY
        if space == "grid":
            self.items = self.items + [(" ", SPACE_UP)]
            self.base_only = self.base_only | {" "}
        pinned = {ch for d in PINNED_POS.values() for ch in d.values()}
        n_cells = len(GRID) * 2 - 2 * len(PINNED_POS) - (1 if dk_pos else 0)
        # loose symbols: one per free key, unshifted half only (unrelated
        # symbols sharing a key surprised the user)
        free = n_cells - len(self.items)
        in_items = {c for it in self.items for c in it} | set(POLISH) \
            | {c.upper() for c in POLISH}
        syms = [c for c, _ in sorted(uni.items(), key=lambda x: -x[1])
                if not c.isalnum() and c not in FIXED and c not in pinned and c.isprintable()
                and len(c) == 1 and c.isascii() and c not in in_items
                and c not in SHIFTED_DIGITS][:free]
        self.symbols = syms
        # units: whole-key items (letters and symbol pairs: lower halves, then
        # upper halves), loose symbols, pinned, fixed, pseudo
        self.units = ([lo for lo, _ in self.items] + [up for _, up in self.items] + syms
                      + sorted(pinned) + ([DK, DK_UP] if dk_pos else []) + list(fixed) + PSEUDO)
        self.uidx = {u: i for i, u in enumerate(self.units)}

        def unit(ch):
            if ch in self.uidx:
                return self.uidx[ch]
            return self.uidx["palm"] if ch.isdigit() or ch in SHIFTED_DIGITS else self.uidx["other"]

        def seq(ch):
            """Units typed for a character (one-shot: Polish = DK + Latin)."""
            if polish == "oneshot" and ch.lower() in POLISH:
                lat = POLISH[ch.lower()]
                return [self.uidx[DK], unit(lat.upper() if ch.isupper() else lat)]
            return [unit(ch)]

        n = len(self.units)
        self.F = np.zeros((n, n))
        for k, v in bi.items():
            self.F[seq(k[0])[-1], seq(k[1])[0]] += v
        self.uni = np.zeros(n)
        for k, v in uni.items():
            sq = seq(k)
            for u in sq:
                self.uni[u] += v
            for a, b in zip(sq, sq[1:]):        # DK -> letter inside one character
                self.F[a, b] += v
        # fixed slots
        self.fixed_slot = {}
        for ch, pos in fixed.items():
            self.fixed_slot[self.uidx[ch]] = self.S.index[(pos, 0, 0)]
        for p in PSEUDO:
            self.fixed_slot[self.uidx[p]] = self.S.index[(p, 0, 0)]
        for pos, d in PINNED_POS.items():
            for (layer, shift), ch in d.items():
                self.fixed_slot[self.uidx[ch]] = self.S.index[(pos, layer, shift)]
        if dk_pos:
            # one-shot key pinned (e.g. dual-use: tap = one-shot, hold = Ctrl)
            self.fixed_slot[self.uidx[DK]] = self.S.index[(dk_pos, 0, 0)]
            self.fixed_slot[self.uidx[DK_UP]] = self.S.index[(dk_pos, 0, 1)]
            # after the one-shot key, the Polish layer has every Polish letter
            # on the physical key of its Latin letter, so a Latin letter from
            # layer 2 is typed without the layer key: no layer switch. Only
            # the one-shot key's slots start such transitions (rows of C).
            for sl in (self.S.index[(dk_pos, 0, 0)], self.S.index[(dk_pos, 0, 1)]):
                for j, (_q, lq, _sq) in enumerate(self.S.slots):
                    if lq:
                        self.S.C[sl, j] -= P["layer"]
        self.cells = [(pos, l) for pos in GRID for l in (0, 1)
                      if pos not in PINNED_POS and (pos, l) != (dk_pos, 0)]
        self.sym_halves = ([self.S.index[(pos, l, 0)] for pos, l in self.cells]
                           + [self.S.index[(pos, l, 0)] for pos in PINNED_POS for l in (0, 1)
                              if (l, 0) not in PINNED_POS[pos]])
        if polish == "oneshot":
            self.pl = []
            # Latin bases of Polish letters on distinct physical keys
            self.distinct = [self.uidx[b] for b in POLISH.values()]
        else:
            self.pl = [(self.uidx[p], self.uidx[p.upper()], self.uidx[b])
                       for p, b in POLISH.items()]
            self.distinct = []

    # state: slot_of (unit -> slot), half (slot -> unit or -1)
    def random_state(self, rng):
        slot_of = np.zeros(len(self.units), dtype=int)
        for u, s in self.fixed_slot.items():
            slot_of[u] = s
        cells = list(self.cells)
        rng.shuffle(cells)
        base = [c for c in cells if c[1] == 0]
        used = set()
        items = sorted(self.items, key=lambda it: (it[0] not in self.base_only,
                                                   it[0] not in LETTERS))
        distinct = set(POLISH.values()) if self.distinct else set()
        used_pos = set()
        for lo_ch, up_ch in items:
            pool = base if lo_ch in self.base_only else cells
            if lo_ch in LETTERS or lo_ch == " ":
                pool = [c for c in pool if c[0] not in NO_LETTER_POS]
            if lo_ch in distinct:
                pool = [c for c in pool if c[0] not in used_pos]
            c = next(c for c in pool if c not in used)
            if lo_ch in distinct:
                used_pos.add(c[0])
            used.add(c)
            lo, up = self.S.cell(*c)
            slot_of[self.uidx[lo_ch]], slot_of[self.uidx[up_ch]] = lo, up
        occupied = {slot_of[self.uidx[x]] for it in self.items for x in it}
        halves = [h for h in self.sym_halves if h not in occupied]
        rng.shuffle(halves)
        for sym, h in zip(self.symbols, halves):
            slot_of[self.uidx[sym]] = h
        return slot_of

    def to_json(self, slot_of, description, score):
        """The layout file format of optimizer/layouts (export_layout.py)."""
        keys = [{"pos": pos, "layer": layer, "shift": shift, "char": ch}
                for (pos, layer, shift), ch in sorted(self.layout(slot_of).items())]
        return {"description": description, "score": score, "polish": self.mode,
                "polish_map": dict(POLISH) if self.mode == "oneshot" else {},
                "params": {k: self.P[k] for k in sorted(self.P)}, "keys": keys}

    def from_json(self, lay):
        """slot_of of a saved layout; units the layout lacks get free halves."""
        slot_of = np.zeros(len(self.units), dtype=int)
        for u, s in self.fixed_slot.items():
            slot_of[u] = s
        placed = set()
        for k in lay["keys"]:
            if k["char"] in self.uidx and self.uidx[k["char"]] not in self.fixed_slot:
                slot_of[self.uidx[k["char"]]] = self.S.index[(k["pos"], k["layer"], k["shift"])]
                placed.add(self.uidx[k["char"]])
        used = {slot_of[u] for u in placed} | set(self.fixed_slot.values())
        free = [h for h in self.sym_halves if h not in used]
        missing = [u for u in range(len(self.units)) if u not in placed and u not in self.fixed_slot]
        for u, h in zip(missing, free):
            slot_of[u] = h
        return slot_of, [self.units[u] for u in missing]

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
            pl = np.array(self.pl, dtype=np.int64).reshape(-1, 3)
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
                            cell_slots, np.array(self.sym_halves), 2 * len(self.items),
                            np.array([self.uidx[z] for z in self.base_only]),
                            np.array(self.distinct, dtype=np.int64),
                            np.array([p in NO_LETTER_POS for p, _, _ in S.slots]),
                            np.array([u in LETTERS or u.lower() in LETTERS and u.isupper()
                                      or u in (" ", SPACE_UP) for u in self.units]),
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
                    if (lo.isalpha() and up == lo.upper()) or up in (DK_UP, SPACE_UP):
                        up = " "
                    lo = "␣" if lo == " " else lo
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
            base_only, distinct, no_letter, is_letter, slot_pos, slot_layer, pl, pl_w,
            n_slots):
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
            if is_letter[U[k]] and no_letter[slot_of[U[k]]]:
                ok = False
        if ok:
            for i in range(distinct.shape[0]):
                for j in range(i):
                    if slot_pos[slot_of[distinct[i]]] == slot_pos[slot_of[distinct[j]]]:
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


def run(P, restarts, steps, seed=0, space="thumb", dk_pos=None):
    prob = Problem(P, space=space, dk_pos=dk_pos)
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
    ap.add_argument("--space", choices=("thumb", "grid"), default="thumb",
                    help="Space on the thumb (t4) or on a finger key in the grid")
    ap.add_argument("--dk-pos", help="pin the Polish one-shot key to this grid position, e.g. r2c5")
    ap.add_argument("--save", help="write the best layout here (optimizer/layouts format)")
    ap.add_argument("--description", default="")
    ap.add_argument("--score", help="only score this saved layout under the given parameters")
    a = ap.parse_args()
    P = dict(PARAMS)
    if a.params:
        with open(a.params) as f:
            P.update(json.load(f)["params"])
    for kv in a.set:
        k, v = kv.split("=")
        assert k in P, k
        P[k] = float(v)
    if a.score:
        lay = json.load(open(a.score))
        dk = next((k["pos"] for k in lay["keys"] if k["char"] == DK and a.dk_pos), None)
        prob = Problem(P, polish=lay["polish"], space=a.space, dk_pos=dk)
        slot_of, missing = prob.from_json(lay)
        print(f"score {prob.score(slot_of):.2f} ms/char"
              + (f" (not in the layout, put anywhere: {''.join(missing)})" if missing else ""))
        print(prob.show(slot_of))
        return
    prob, res = run(P, a.restarts, a.steps, a.seed, a.space, a.dk_pos)
    print("symbols placed:", "".join(prob.symbols))
    for slot_of, s in res:
        print(f"score {s:.2f} ms/char")
    print(prob.show(res[0][0]))
    if a.save:
        with open(a.save, "w") as f:
            json.dump(prob.to_json(res[0][0], a.description, res[0][1]), f, indent=1,
                      ensure_ascii=False)
        print(f"-> {a.save}")


if __name__ == "__main__":
    main()
