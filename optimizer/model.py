"""Slots and a rough transition-cost model for the one-handed layout.

Every number in PARAMS is a rough value: phase 1-2a medians where they
exist (see docs/measurement-plan.md), otherwise *(guess)* from the strain
list. Units are milliseconds of a practised transition, with discomfort
folded in as extra "milliseconds". The point of this model is the
sensitivity analysis: find which parameters change the layout, then
measure those.

Positions are model100 ids. Slots are (position, layer, shift):
layer 0 = base, 1 = second letter layer (held thumb key); shift = held Shift.
A letter fills a whole cell (position, layer): lower case unshifted, its
capital shifted. A symbol fills one half-cell.
"""
import itertools
import numpy as np

FINGER = {0: "index", 1: "index", 2: "index", 3: "middle", 4: "ring", 5: "pinky", 6: "pinky"}
FINGER_NO = {"index": 1, "middle": 2, "ring": 3, "pinky": 4}
# Scissor parameter by (finger in the higher row, finger in the lower row).
SCISSOR = {("index", "middle"): "sc_index_up", ("middle", "index"): "sc_middle_up_i",
           ("middle", "ring"): "sc_middle_up_r", ("ring", "middle"): "sc_ring_up_m",
           ("ring", "pinky"): "sc_ring_up_p", ("pinky", "ring"): "sc_pinky_up"}

# Grid positions the optimizer fills (r3c6 is pinned to / and \).
GRID = [f"r{r}c{c}" for r in range(4) for c in range(1, 7)]
PINNED_POS = {"r3c6": {(0, 0): "/", (1, 0): "\\"}}
# Fixed keys outside the grid: char -> position. Tab position is a guess.
FIXED = {" ": "t4", "\n": "r1c0", "⇥": "r0c0"}
# Pseudo-positions: digits on the palm layer, rare symbols somewhere costly.
PSEUDO = ["palm", "other"]

PARAMS = {
    # same key twice, per finger (phase 1 medians)
    "repeat_index": 131, "repeat_middle": 139, "repeat_ring": 149, "repeat_pinky": 172,
    "repeat_thumb": 150,
    # same finger, different key (phase 2a): base + per extra unit of distance
    "sf_index": 165, "sf_middle": 165, "sf_ring": 195, "sf_pinky": 225,
    "sf_dist_index": 5, "sf_dist_middle": 5, "sf_dist_ring": 15, "sf_dist_pinky": 50,
    # different fingers
    "df_base": 110,            # (guess, legacy keylogs: 125-160 incl. thumbs)
    "outward": 40,             # towards the pinky (triples: inward ≫ outward)
    "ring_pinky": 40,          # l h rated 4
    "row_change": 10,          # per row of difference *(guess)*
    # scissors: adjacent fingers in different rows, per row of difference,
    # by finger pair and by which finger is in the higher row. The user's
    # experience: discomfort varies a lot between pairs and directions;
    # index up + middle down is much worse than the reverse (nearly free),
    # middle-ring scissors are worse than index-middle, ring down + pinky up
    # is the worst of all. Values *(guess)*.
    "sc_index_up": 30, "sc_middle_up_i": 5,      # index-middle pair
    "sc_middle_up_r": 30, "sc_ring_up_m": 40,    # middle-ring pair
    "sc_ring_up_p": 30, "sc_pinky_up": 60,       # ring-pinky pair
    # a full scissor (top + bottom row) costs this many one-row scissors;
    # user: clearly more than 2 *(guess)*
    "sc_full_factor": 3,
    "lateral": 40,             # col 1 with middle, col 6 with ring/middle *(guess)*
    "numrow_low": 25,          # number row ↔ bottom row, half of it ↔ home *(guess)*
    # entering a key: effort by position *(guess, by feel)*
    "e_top": 8, "e_bottom": 8, "e_pinky_top": 25, "e_pinky_bottom": 12,
    "e_col1_home": 12, "e_col1_top": 25, "e_col1_bottom": 15,
    "e_col6_home": 25, "e_col6_top": 35,
    "e_num_middle": 45, "e_num_col6": 50, "e_num_other": 80, "e_col0": 20,
    # thumb (phase 1: finger→Space nearly simultaneous, Space→finger ~130)
    "to_space": 60, "from_space": 120, "space_finger_step": 20,
    # modifiers *(guess; phase 5 is the layer-switch experiment)*
    "layer": 60, "layer_cont": 15, "shift": 50, "shift_cont": 15,
    # elsewhere
    "palm": 250, "other": 400,
    # preference: Polish letter on layer 2 under its Latin letter
    "polish_off": 30,
}


def finger(pos):
    return "thumb" if pos.startswith("t") else FINGER[int(pos[3])]


def rc(pos):
    return int(pos[1]), int(pos[3])


def effort(pos, P):
    r, c = rc(pos)
    if c == 0:
        return P["e_col0"]
    if r == 0:
        return P["e_num_middle"] if c == 3 else P["e_num_col6"] if c == 6 else P["e_num_other"]
    if c == 1:
        return P[("e_col1_top", "e_col1_home", "e_col1_bottom")[r - 1]]
    if c == 6:
        return P[("e_col6_top", "e_col6_home", "e_pinky_bottom")[r - 1]]
    if c == 5:
        return (P["e_pinky_top"], 0, P["e_pinky_bottom"])[r - 1]
    return (P["e_top"], 0, P["e_bottom"])[r - 1]


def pos_cost(p, q, P):
    """Cost of the transition p → q between physical positions."""
    if p in PSEUDO or q in PSEUDO:
        return P["palm"] if "palm" in (p, q) else P["other"]
    fp, fq = finger(p), finger(q)
    if p == q:
        return P[f"repeat_{fp}"]
    if fq == "thumb":
        return P["to_space"] if fp != "thumb" else P["repeat_thumb"]
    if fp == "thumb":
        return P["from_space"] + P["space_finger_step"] * (FINGER_NO[fq] - 1) + effort(q, P)
    (rp, cp), (rq, cq) = rc(p), rc(q)
    e = effort(q, P)
    if fp == fq:
        dist = max(abs(rp - rq), abs(cp - cq))
        return P[f"sf_{fp}"] + P[f"sf_dist_{fp}"] * (dist - 1) + e
    cost = P["df_base"] + e + P["row_change"] * abs(rp - rq)
    if FINGER_NO[fq] > FINGER_NO[fp]:
        cost += P["outward"]
    pair = {fp, fq}
    if pair == {"ring", "pinky"}:
        cost += P["ring_pinky"]
    if abs(FINGER_NO[fp] - FINGER_NO[fq]) == 1 and rp != rq:
        high = fp if rp < rq else fq          # finger in the higher row
        other = fq if high == fp else fp
        rows = abs(rp - rq)
        cost += P[SCISSOR[(high, other)]] * (1 if rows == 1 else P["sc_full_factor"] * (rows - 1))
    for (a, ca), (b, _) in (((fp, cp), (fq, cq)), ((fq, cq), (fp, cp))):
        if (ca == 1 and b == "middle") or (ca == 6 and b in ("ring", "middle")):
            cost += P["lateral"]
    if 0 in (rp, rq):
        other = max(rp, rq)
        cost += P["numrow_low"] * {0: 0, 1: 0, 2: 0.5, 3: 1}[other]
    return cost


class Slots:
    """All slots, with a cost matrix between them."""

    def __init__(self, P):
        self.P = P
        self.slots = []            # (pos, layer, shift)
        for pos in GRID:
            for layer, shift in itertools.product((0, 1), (0, 1)):
                self.slots.append((pos, layer, shift))
        for pos in sorted(set(FIXED.values())) + PSEUDO:
            self.slots.append((pos, 0, 0))
        self.index = {s: i for i, s in enumerate(self.slots)}
        n = len(self.slots)
        C = np.zeros((n, n))
        for i, (p, lp, sp) in enumerate(self.slots):
            for j, (q, lq, sq) in enumerate(self.slots):
                c = pos_cost(p, q, P)
                if lq:
                    c += P["layer_cont"] if lp else P["layer"]
                if sq:
                    c += P["shift_cont"] if sp else P["shift"]
                C[i, j] = c
        self.C = C

    def cell(self, pos, layer):
        return self.index[(pos, layer, 0)], self.index[(pos, layer, 1)]
