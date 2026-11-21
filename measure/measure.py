#!/usr/bin/env python3
"""Measure the cost of key-position sequences on the right half of a Model 100.

Each trial highlights 1-4 keys and shows the sequence to type cyclically
(e.g. "u n u n ..." or "u n r u n r ..."), typed as if it were part of a
word - separate key presses, not a back-and-forth oscillation or a sprint.
Afterwards rate the discomfort on the top row keys . u i o b = 1-5
(Backspace = redo, Del = skip). Del during a trial pauses, Backspace
starts it over (nothing saved). A wrong key counts as an error and the
sequence moves on, so the rhythm isn't lost (since 2026-11-21; before, the
correct key had to be pressed).

Works on the measurement layer (see make_measurement_layer.py) or on layer 4
(the typing layer, plain keys since 2026-11-19): both send the same keys
except the number row and t1, which are recognised in both versions.
Timestamps come from the kernel input device, not the terminal. The device
sees every key press, so measuring is paused while the terminal is not
focused (terminal focus reporting).

  python3 measure/measure.py run [--stretches 5] [--plan phase1|phase2a|scissors|...]
                                 [--patterns FILE] [--repeats N]
      phase1:  home-row fingers + Space thumb (the baseline, see
               docs/design-principles.md); each pattern once per session
      phase2a: same finger, two different keys, hand position free
      pilot-chain: 4-key words, each starting with the last two keys of
               the previous one; 15 cycles, no warm-up removed: measures
               how many cycles a new word needs to settle
      pilot-words: (first pilot, 4-6 key random words: too hard to learn)
      pilot-real: 8 Polish words typed on layer 4 (4 as they are, 4 with one
               letter swapped to its layer-4 key), each followed by Space
      scissors: adjacent fingers in all row combinations, each followed by
               Space ("l h Spc", both orders): row-change and scissor costs
      scissors-im: the index-middle part of scissors (18 patterns)
      lateral: index stretch column with the middle finger + Space (18)
      sf-index: index same-finger bigrams followed by Space (10 patterns)
      layer:   home-row pairs + Space with the layer key held for none,
               the first, the second or both letters (24 patterns)
      layer-fingers: home-row finger triples, no Space, layer key held
               for none, one, two or all three letters (16 patterns)
      space-row: same-row finger triples with and without Space, top /
               home / bottom row: the hand stretch of Space + top row (12)
      focus-1..focus-6: the above split into sessions of <= 20
               patterns, each with its references (see FOCUS_SPLIT)
      bigrams: all 2-key position pairs (exploratory, protocol 1)
      FILE: one sequence per line, key labels or position ids,
            e.g. "u n r" or "r1c2 r2c2 r2c3"; "Sft+r" = r with Sft held
  python3 measure/measure.py stats
"""
import argparse
import collections
import datetime
import glob
import itertools
import json
import os
import random
import select
import statistics
import struct
import sys
import termios
import time
import tty

from model100 import BASE_LAYER_ALT, DIAGRAM_ROWS, HOME_KEYS, LABEL, LAYER_KEYS, MEASURED, THUMB_ROW

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "measurements")
TRIALS = os.path.join(DATA, "trials.jsonl")

CODE_TO_POS = {linux: pos for pos, (_label, _hid, linux) in LAYER_KEYS.items()}
CODE_TO_POS.update({linux: pos for pos, linux in BASE_LAYER_ALT.items()})
LABEL_TO_POS = {label: pos for pos, label in LABEL.items()}

# Top row: the same keys on the measurement layer and on layer 4.
RATING_KEYS = {"r1c1": 1, "r1c2": 2, "r1c3": 3, "r1c4": 4, "r1c5": 5}
REDO_KEY, SKIP_KEY = "r3c0", "r0c0"
PAUSE_KEYS = {"r0c0", "palm"}   # palm only sends a key on the measurement layer
RATING_TEXT = "1 effortless · 2 fine · 3 some effort · 4 uncomfortable · 5 strain"

# Protocol 1: 2-key cycles, 2 warm-up cycles, "comfortable pace", control
# every 13th trial. Protocol 2: longer warm-up, "as part of a word",
# controls at session start and end, phase-1 baseline plan.
PROTOCOL = 2
CYCLES = {1: 30, 2: 20, 3: 13, 4: 10, 5: 8, 6: 7}      # cycles per trial, by pattern length
WARMUP_CYCLES = {1: 8, 2: 5, 3: 3, 4: 3, 5: 3, 6: 3}   # >= 8 presses; 5-6: to be set by the pilot
# Plans that override the above: plan -> (cycles, warm-up cycles)
PLAN_CYCLES = {"pilot-words": (20, 0), "pilot-chain": (15, 0), "pilot-real": (15, 0)}
# Patterns with a held layer key: the first runs needed ~8 restarts (user,
# 2026-11-21), so more warm-up before measuring.
MOD_CYCLES = (20, 8)
PAUSE_MS = 1500                 # longer gaps don't count as transitions
STRETCH_S = 3 * 60              # active measuring time between breaks
BREAK_S = 30
CORE = {f"r{r}c{c}" for r in (1, 2, 3) for c in range(1, 6)}

# Phase 1 baseline: home row index..pinky plus the Space thumb.
FINGERS = ["r2c2", "r2c3", "r2c4", "r2c5", "t4"]
ROLL_IN = ("r2c5", "r2c4", "r2c3", "r2c2")
ROLL_OUT = tuple(reversed(ROLL_IN))
# Run at the start and end of every session to track drift and fatigue.
CONTROLS = [("r2c2", "r2c3"), ROLL_IN]

EVENT = struct.Struct("llHHi")
EV_KEY = 1


# ---------------------------------------------------------------- patterns

def canonical(pattern):
    """Cyclic patterns are equal up to rotation: 'AB' == 'BA'."""
    p = list(pattern)
    return min(tuple(p[i:] + p[:i]) for i in range(len(p)))


# A pattern element is a position, or "mod+pos": pos pressed while the thumb
# key mod is held (the layer switch; the press of mod is logged with index
# MOD_INDEX and doesn't count as an error).
MOD_INDEX = -2


def key_of(e):
    return e.split("+")[-1]


def mod_of(e):
    return e.split("+")[0] if "+" in e else None


def label(e):
    m = mod_of(e)
    return f"{LABEL[m]}+{LABEL[key_of(e)]}" if m else LABEL[e]


def column(pos):
    pos = key_of(pos)
    return 0 if pos.startswith("t") else int(pos[3])   # thumb counts as innermost


def finger(pos):
    pos = key_of(pos)
    if pos.startswith("t"):
        return "thumb"
    return {0: "index", 1: "index", 2: "index", 3: "middle", 4: "ring",
            5: "pinky", 6: "pinky"}[int(pos[3])]


def spread_fingers(todo, done):
    """Reorder so consecutive trials share as few fingers as possible (fatigue
    builds up when one finger is measured several times in a row). Patterns
    measured in fewer sessions still come first."""
    rest, out, recent = list(todo), [], []
    while rest:
        def key(ip):
            i, p = ip
            f = {finger(x) for x in p}
            load = sum(len(f & r) * w for r, w in zip(recent, (2, 1)))
            # prefer fingers with many trials left, so they don't pile up at the end
            backlog = sum(1 for q in rest if f & {finger(x) for x in q})
            return (done.get(p, 0), load, -backlog, i)
        i, p = min(enumerate(rest), key=key)
        out.append(rest.pop(i))
        recent = [{finger(x) for x in p}] + recent[:1]
    return out


def display_order(pattern):
    """Rotate a cyclic pattern so it is shown starting where the movement starts:
    the largest jump comes at the wrap-around (e.g. 'n h l' -> 'h l n')."""
    p = list(pattern)
    if len(p) < 3:
        return p
    jump = lambda i: abs(column(p[i - 1]) - column(p[i]))
    start = max(range(len(p)), key=jump)
    return p[start:] + p[:start]


def tier(pattern):
    s = set(pattern)
    if s <= CORE:
        return 1
    if not any(p.startswith("t") for p in s):
        return 2
    return 3


def bigram_plan():
    pats = [(p,) for p in MEASURED] + list(itertools.combinations(MEASURED, 2))
    return [canonical(p) for p in pats]


def phase1_plan():
    """Same-key repeats, finger pairs, finger triples (both cyclic orders), 4-finger rolls."""
    pats = [(p,) for p in FINGERS] + list(itertools.combinations(FINGERS, 2))
    for a, b, c in itertools.combinations(FINGERS, 3):
        pats += [(a, b, c), (a, c, b)]
    pats += [ROLL_IN, ROLL_OUT]
    return [canonical(p) for p in pats]


def phase2a_plan():
    """Same finger, different keys, unanchored: the hand may settle into whatever
    position suits the movement. Vertical moves for index..pinky (top-home,
    home-bottom, top-bottom) and horizontal moves for index and pinky."""
    pats = []
    for c in range(2, 6):
        pats += [(f"r1c{c}", f"r2c{c}"), (f"r2c{c}", f"r3c{c}"), (f"r1c{c}", f"r3c{c}")]
    for a, b in ((1, 2), (5, 6)):
        pats += [(f"r{r}c{a}", f"r{r}c{b}") for r in (1, 2, 3)]
    return [canonical(p) for p in pats]


# Word trials: candidate positions (rows 1-3, columns 1-6). The first pilot
# also had Space; word trials leave it out (thumb cost from phase 1).
WORD_KEYS = [f"r{r}c{c}" for r in (1, 2, 3) for c in range(1, 7)]


def word_ok(w):
    """Distinct keys, at least 3 fingers, at most one same-finger transition
    (wrap-around included), as in text."""
    k = len(w)
    same = sum(finger(w[i]) == finger(w[(i + 1) % k]) for i in range(k))
    return len(set(w)) == k and len({finger(x) for x in w}) >= 3 and same <= 1


def random_word(rng, k, keys=WORD_KEYS + ["t4"]):
    while True:
        w = tuple(rng.sample(keys, k))
        if word_ok(w):
            return w


def chain_words(rng, n, k=4, step=2):
    """n words of k keys, each starting with the last k-step keys of the
    previous one (a moving window over one random key sequence)."""
    words = [random_word(rng, k, WORD_KEYS)]
    while len(words) < n:
        head = words[-1][step:]
        while True:
            w = head + tuple(rng.sample(WORD_KEYS, step))
            if word_ok(w):
                words.append(w)
                break
    return words


def pilot_chain_plan():
    """Second warm-up pilot: 14 chained 4-key words, then the first two again.
    Not rotated: each word is shown starting where the previous one ended."""
    words = chain_words(random.Random(2), 14)
    return words + words[:2]


# Real words: letters typed with the palm key (layer 5) or with AltGr map to
# the layer-4 key at the same position, e.g. "mogę" is typed "mogr".
LETTER_POS = {label: pos for pos, label in LABEL.items()
              if len(label) == 1 and label.isalpha() and pos[1] in "123"}
SWAPS = dict(zip("fdwqtesacvxz", "uiobnrlhmkjg"))
SWAPS.update(zip("ąęłóśćńżź", "hrlolmngj"))
WORD_TEXT = {}   # pattern -> the real word it was made from


def word_pattern(word):
    """Positions for typing `word` on layer 4, followed by Space."""
    p = tuple(LETTER_POS[SWAPS.get(ch, ch)] for ch in word) + ("t4",)
    WORD_TEXT[p] = word
    return p


def pilot_real_plan():
    """Third pilot: real Polish words, 4 typed as they are, 4 with one letter
    swapped (the layer-4 key under it), alternating."""
    words = ["humor", "nigdy", "mogli", "tylko", "okno", "mogę", "robimy", "przy"]
    return [word_pattern(w) for w in words]


def pilot_words_plan():
    """Warm-up pilot: 6 words each of 4, 5 and 6 keys, lengths interleaved; the
    first word of each length is repeated at the end (within-session agreement)."""
    rng = random.Random(1)
    words = {k: [random_word(rng, k) for _ in range(6)] for k in (4, 5, 6)}
    plan = [words[k][i] for i in range(6) for k in (4, 5, 6)]
    return [canonical(p) for p in plan + [words[k][0] for k in (4, 5, 6)]]


def scissors_plan(cols=(2, 3, 4)):
    """Adjacent fingers (index-middle, middle-ring, ring-pinky), each finger in
    rows 1-3 (9 combinations, home-home is the in-session reference), both
    orders, followed by Space: 3-key cycles like the phase-1 triples, which
    settled without speed-up. Space as the third key keeps the cycle a
    word-like 'a b Spc' instead of a trill. Opposite rows are the scissors
    (ring down + pinky up suspected worst)."""
    pats = []
    for c in cols:
        for ra, rb in itertools.product((1, 2, 3), repeat=2):
            a, b = f"r{ra}c{c}", f"r{rb}c{c + 1}"
            pats += [(a, b, "t4"), (b, a, "t4")]
    return [canonical(p) for p in pats]


def scissors_im_plan():
    """Index-middle scissors only (columns 2-3): 18 patterns. The optimizer's
    layout depends most on these (docs/optimizer.md)."""
    return scissors_plan(cols=(2,))


def lateral_plan():
    """Index in the stretch column (1) with the middle finger (column 3), all
    row combinations, both orders, + Space: 18 patterns. Compare with
    scissors-im (index in column 2) for the cost of the lateral stretch
    (QWERTY G-D on the left hand was straining)."""
    pats = []
    for ra, rb in itertools.product((1, 2, 3), repeat=2):
        a, b = f"r{ra}c1", f"r{rb}c3"
        pats += [(a, b, "t4"), (b, a, "t4")]
    return [canonical(p) for p in pats]


def sf_index_plan():
    """Index same-finger bigram followed by Space ('a b Spc', both orders),
    the same context as the scissors plans, whose index-middle home-row
    patterns are the different-finger reference. Vertical moves in the home
    column and moves to and from the stretch column (the optimizer puts
    letters there): 5 pairs, 10 patterns."""
    pairs = [("r1c2", "r2c2"), ("r2c2", "r3c2"), ("r2c1", "r2c2"),
             ("r2c1", "r1c2"), ("r2c1", "r3c2")]
    return [canonical(p) for a, b in pairs for p in ((a, b, "t4"), (b, a, "t4"))]


# Thumb key standing in for the second-letter-layer key: layer keys send no
# key code, so a thumb modifier that does is held instead (same movement).
LAYER_KEY = "t3"


def layer_plan():
    """Layer switch inside a word: home-row pairs (index-middle, middle-ring,
    index-ring, both orders) + Space, with the layer key held for none, the
    first, the second or both letters. 24 patterns; the plain ones repeat
    phase-1 triples as the in-session reference."""
    L = LAYER_KEY + "+"
    pats = []
    for a, b in itertools.permutations(("r2c2", "r2c3", "r2c4"), 2):
        pats += [(a, b, "t4"), (L + a, b, "t4"), (a, L + b, "t4"), (L + a, L + b, "t4")]
    return [canonical(p) for p in pats]


def layer_fingers_plan():
    """Layer switch without Space: the thumb presses only the layer key.
    Finger triples n r l in both orders, the layer key held for none, each
    single letter, each two consecutive letters, or all three (held for the
    whole cycle: no switching). 16 patterns; plain = phase-1 triples."""
    L = LAYER_KEY + "+"
    pats = []
    for tri in (("r2c2", "r2c3", "r2c4"), ("r2c4", "r2c3", "r2c2")):
        for mask in itertools.product((0, 1), repeat=3):
            pats.append(tuple(L + x if m else x for x, m in zip(tri, mask)))
    return [canonical(p) for p in pats]


def space_row_plan():
    """Space next to top-row keys stretches the whole hand (user). Index-
    middle pairs + Space in the top, home and bottom row, against the same
    rows typed with the ring finger instead of Space (index-middle-ring,
    no thumb). Both orders: 12 patterns."""
    pats = []
    for r in (1, 2, 3):
        i, m, ring = f"r{r}c2", f"r{r}c3", f"r{r}c4"
        pats += [(i, m, "t4"), (m, i, "t4"), (i, m, ring), (ring, m, i)]
    return [canonical(p) for p in pats]


def focus_plan():
    return list(dict.fromkeys(scissors_im_plan() + lateral_plan() + sf_index_plan()
                              + layer_plan() + layer_fingers_plan() + space_row_plan()))


def _layer_pairs(pairs):
    """The layer patterns of the given unordered home-row pairs (4 per order)."""
    keys = [set(p) for p in pairs]
    return [p for p in layer_plan() if {key_of(e) for e in p} - {"t4"} in keys]


HOME_IM = [canonical(("r2c2", "r2c3", "t4")), canonical(("r2c3", "r2c2", "t4"))]
# Sessions of at most 20 patterns, each with its in-session references.
FOCUS_SPLIT = {
    "focus-1": lambda: scissors_im_plan(),                                   # 18
    "focus-2": lambda: lateral_plan() + HOME_IM,                             # 20
    "focus-3": lambda: sf_index_plan() + _layer_pairs([("r2c2", "r2c3")]),  # 18
    "focus-4": lambda: _layer_pairs([("r2c2", "r2c4"), ("r2c3", "r2c4")]),  # 16
    "focus-5": lambda: layer_fingers_plan(),                                 # 16
    "focus-6": lambda: space_row_plan(),                                     # 12
}


def space_last(pattern):
    """Rotate a cyclic pattern so Space comes last, like the end of a word."""
    p = list(pattern)
    if "t4" not in p:
        return display_order(p)
    i = p.index("t4")
    return p[i + 1:] + p[:i + 1]


PLANS = {"phase1": phase1_plan, "phase2a": phase2a_plan, "pilot-words": pilot_words_plan,
         "pilot-chain": pilot_chain_plan, "pilot-real": pilot_real_plan, "bigrams": bigram_plan,
         "scissors": scissors_plan, "scissors-im": scissors_im_plan, "lateral": lateral_plan,
         "sf-index": sf_index_plan,
         "layer": layer_plan, "layer-fingers": layer_fingers_plan,
         "space-row": space_row_plan, **FOCUS_SPLIT}
# Plans run in their own order, with planned repeats inside one session.
FIXED_ORDER = {"pilot-words", "pilot-chain", "pilot-real"}
# Plans whose words are shown as planned, not rotated by display_order.
AS_PLANNED = {"pilot-chain", "pilot-real"}
# Plans whose patterns are shown with Space last.
SPACE_LAST = {"scissors", "scissors-im", "lateral", "sf-index", "layer", "space-row",
              *FOCUS_SPLIT}
# Plans whose patterns count as done only from their own trials (their
# reference patterns were measured elsewhere too, but are needed in-session).
OWN_COUNT = set(FOCUS_SPLIT)


def load_trials():
    if not os.path.exists(TRIALS):
        return []
    with open(TRIALS) as f:
        return [json.loads(line) for line in f if line.strip()]


def transitions(trial):
    """Valid (from, to, ms) transitions of a trial, warm-up and errors excluded."""
    k = len(trial["pattern"])
    warmup = trial.get("warmup_cycles", WARMUP_CYCLES[k])
    out, prev = [], None
    for pos, t_down, _t_up, idx in trial["presses"]:
        if idx == MOD_INDEX:   # held modifier: not a transition
            continue
        if idx < 0:            # wrong key: breaks the chain
            prev = None
            continue
        if prev is not None and idx >= warmup * k:
            gap = t_down - prev[1]
            if gap <= PAUSE_MS:
                out.append((prev[0], pos, gap))
        prev = (pos, t_down)
    return out


# ---------------------------------------------------------------- input

class Keyboard:
    def __init__(self):
        paths = sorted(set(os.path.realpath(p) for p in glob.glob("/dev/input/by-id/*Keyboardio*event*")))
        if not paths:
            sys.exit("No Keyboardio input device found under /dev/input/by-id")
        self.fds = [os.open(p, os.O_RDONLY | os.O_NONBLOCK) for p in paths]
        self.last = {}
        self.focused = True     # assumed at start; updated by focus reports

    def events(self, timeout):
        """Yield (pos, is_press, t_ms) for measurement-layer keys; ('quit',..) on Esc/Ctrl-C,
        ('blur',..) when the terminal loses focus. Keys are ignored while unfocused."""
        r, _, _ = select.select(self.fds + [sys.stdin.fileno()], [], [], timeout)
        for fd in r:
            if fd == sys.stdin.fileno():
                data = os.read(fd, 1024)
                # bare Esc or Ctrl-C quits; Del etc. arrive as \x1b[... sequences
                if b"\x03" in data or data == b"\x1b":
                    yield ("quit", True, 0.0)
                # focus reports: ESC[I = focus in, ESC[O = focus out (last one wins)
                i, o = data.rfind(b"\x1b[I"), data.rfind(b"\x1b[O")
                if i != o:
                    self.focused = i > o
                    if not self.focused:
                        yield ("blur", True, 0.0)
                continue
            if not self.focused:
                try:
                    os.read(fd, EVENT.size * 64)   # drain, ignore
                except BlockingIOError:
                    pass
                continue
            try:
                buf = os.read(fd, EVENT.size * 64)
            except BlockingIOError:
                continue
            for i in range(0, len(buf) - EVENT.size + 1, EVENT.size):
                sec, usec, typ, code, value = EVENT.unpack_from(buf, i)
                if typ != EV_KEY or value == 2 or code not in CODE_TO_POS:
                    continue
                t = sec * 1000 + usec / 1000
                key = (code, value)
                if abs(self.last.get(key, -1e9) - t) < 3:  # same event on two interfaces
                    continue
                self.last[key] = t
                yield (CODE_TO_POS[code], value == 1, t)

    def next_press(self, timeout=None):
        while True:
            for pos, down, t in self.events(timeout):
                if down and pos != "blur":
                    return pos, t
            if timeout is not None:
                return None, None


# ---------------------------------------------------------------- drawing

def draw_keyboard(labels):
    """labels: position -> text shown on the highlighted key."""
    def cell(pos):
        if pos is None:
            return "     "
        if pos in labels:
            return f"\x1b[30;43m{labels[pos]:^5}\x1b[0m"
        mark = " _ " if pos in HOME_KEYS else "   "
        return f"\x1b[2m[{mark}]\x1b[0m"
    lines = [" ".join(cell(p) for p in row) for row in DIAGRAM_ROWS]
    lines.append("")
    lines.append(" ".join(cell(p) for p in THUMB_ROW))
    return "\n".join("   " + l for l in lines)


def screen(*parts):
    sys.stdout.write("\x1b[H\x1b[2J" + "\r\n".join("\n".join(parts).split("\n")) + "\r\n")
    sys.stdout.flush()


# ---------------------------------------------------------------- trial

def sequence_view(pattern, cycles, nxt, width=72):
    """The whole run as text, one group per cycle: typed keys dim green, the
    next key highlighted, the rest plain."""
    k = len(pattern)
    # real words: letters written together, Space as a visible gap
    word = tuple(pattern) in WORD_TEXT
    groups, lines = [], []
    for c in range(cycles):
        cells = []
        for i in range(c * k, c * k + k):
            lab = label(pattern[i % k])
            text = ("_" if lab == "Spc" else lab) if word else f"{lab:<3}"
            if i < nxt:
                cells.append(f"\x1b[2;32m{text}\x1b[0m")
            elif i == nxt:
                cells.append(f"\x1b[1;97;44m{text}\x1b[0m")
            else:
                cells.append(text)
        groups.append(("" if word else " ").join(cells))
    w = max(len(label(e)) for e in pattern)
    per_line = max(1, (width + 2) // ((k + 1) if word else ((max(w, 3) + 1) * k + 1)))
    for c in range(0, cycles, per_line):
        lines.append("   " + "  ".join(groups[c:c + per_line]))
    return "\n".join(lines)


def run_trial(kb, pattern, header, cycles):
    k = len(pattern)
    total = cycles * k
    # words: number the keys in typing order, to help remember the sequence
    word = WORD_TEXT.get(tuple(pattern))
    labels = {key_of(e): (f"{i + 1}:{LABEL[key_of(e)]}" if k >= 4 and not word
                          else LABEL[key_of(e)])
              for i, e in enumerate(pattern)}
    mods = {mod_of(e) for e in pattern} - {None}
    labels.update({m: LABEL[m] for m in mods})
    held = set()
    presses, nxt, errors = [], 0, 0

    def show(msg=""):
        intro = ([f"   word: {word}" + (f"  (typed {''.join(LABEL[p] for p in pattern[:-1])})"
                                         if any(ch in SWAPS for ch in word) else ""),
                  "   first cycles slowly until it flows, then normal speed", ""]
                 if word else [])
        screen(header, "", draw_keyboard(labels), "", *intro,
               sequence_view(pattern, cycles, nxt), "", f"   errors: {errors}", msg)

    restart_ok = REDO_KEY not in {key_of(e) for e in pattern}
    show("   start whenever ready   (Del = pause" + (", Bsp = start over)" if restart_ok else ")"))
    open_presses = {}
    while nxt < total:
        for pos, down, t in kb.events(None):
            if pos == "quit":
                return "quit", presses
            if not down:
                held.discard(pos)
                if pos in open_presses:
                    presses[open_presses.pop(pos)][2] = t
                continue
            if pos in PAUSE_KEYS or pos == "blur":
                return "paused", presses
            if pos == REDO_KEY and restart_ok:
                return "restart", presses
            if pos in mods:
                held.add(pos)
                presses.append([pos, t, None, MOD_INDEX])
                open_presses[pos] = len(presses) - 1
                continue
            e = pattern[nxt % k]
            want = {mod_of(e)} - {None}
            # a letter typed with the wrong layer is an error; Space isn't
            ok = pos == key_of(e) and (pos.startswith("t") or held == want)
            presses.append([pos, t, None, nxt if ok else -1])
            open_presses[pos] = len(presses) - 1
            nxt += 1            # a wrong key takes its slot: keep the rhythm
            if not ok:
                errors += 1
            show("" if ok else "   \x1b[31mwrong key\x1b[0m")
            if nxt >= total:
                break
    # collect releases of the last keys briefly
    deadline = time.time() + 0.4
    while open_presses and time.time() < deadline:
        for pos, down, t in kb.events(0.05):
            if not down and pos in open_presses:
                presses[open_presses.pop(pos)][2] = t
    return "done", presses


RATING_NAMES = {1: "effortless", 2: "fine", 3: "some effort", 4: "uncomfortable", 5: "strain"}
CONFIRM_KEYS = {"t4", "r1c0"}  # Space, Enter


def ask_rating(kb, header):
    """Rating is shown first and only stored after Space/Enter confirms it."""
    choice = None
    while True:
        if choice is None:
            status = "   (no rating selected)"
        else:
            status = (f"   selected: \x1b[30;43m {choice} – {RATING_NAMES[choice]} \x1b[0m"
                      "   → Spc / Ent to confirm, another number to change")
        screen(header, "", "   How did that feel?", "",
               f"   top row (. u i o b):  {RATING_TEXT}",
               "   Bsp = redo,   Del = skip (mark as weird)", "", status)
        pos, _ = kb.next_press()
        if pos == "quit":
            return "quit"
        if pos in RATING_KEYS:
            choice = RATING_KEYS[pos]
        elif pos in CONFIRM_KEYS and choice is not None:
            return choice
        elif pos == REDO_KEY:
            return "redo"
        elif pos == SKIP_KEY:
            return "skip"


def summarize(pattern, presses):
    tr = transitions({"pattern": pattern, "presses": presses})
    by = {}
    for a, b, ms in tr:
        by.setdefault((a, b), []).append(ms)
    return "   ".join(f"{LABEL[a]}→{LABEL[b]}: {statistics.median(v):.0f} ms"
                      for (a, b), v in by.items())


# ---------------------------------------------------------------- run

def cmd_run(args):
    os.makedirs(DATA, exist_ok=True)
    done = {}   # canonical pattern -> number of sessions with an ok protocol-2 trial
    for t in load_trials():
        if args.plan in OWN_COUNT and not args.patterns and t.get("plan") != args.plan:
            continue
        if t["status"] == "ok" and not t.get("control") and t.get("protocol", 1) >= PROTOCOL:
            c = canonical(t["pattern"])
            done[c] = done.get(c, 0) + 1
    if args.patterns:
        with open(args.patterns) as f:
            plan = [canonical(["+".join(LABEL_TO_POS.get(y, y) for y in x.split("+"))
                               for x in l.split()])
                    for l in f if l.strip() and not l.startswith("#")]
        bad = {p for pat in plan for e in pat for p in e.split("+") if p not in LABEL}
        if bad:
            sys.exit(f"unknown keys in {args.patterns}: {sorted(bad)}")
    else:
        plan = PLANS[args.plan]()
    plan_name = None if args.patterns else args.plan
    if plan_name in FIXED_ORDER:
        # planned order; resume after the trials already done (repeats counted)
        prior = collections.Counter(canonical(t["pattern"]) for t in load_trials()
                                    if t.get("plan") == plan_name and t["status"] == "ok")
        seen, todo = collections.Counter(), []
        for p in plan:
            seen[canonical(p)] += 1
            if seen[canonical(p)] > prior[canonical(p)]:
                todo.append(p)
        total_plan = len(plan)
        measured = total_plan - len(todo)
    else:
        # each pattern at most once per session; least-measured first
        todo = [p for p in plan if done.get(p, 0) < args.repeats]
        random.shuffle(todo)
        todo.sort(key=lambda p: (done.get(p, 0), tier(p)))
        todo = spread_fingers(todo, done)
        total_plan = len(plan) * args.repeats
        measured = sum(min(v, args.repeats) for p, v in done.items() if p in set(plan))

    session = datetime.datetime.now().isoformat(timespec="seconds")
    kb = Keyboard()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    sys.stdout.write("\x1b[?1004h")   # ask the terminal to report focus changes
    sys.stdout.flush()
    n, last_summary = 0, ""
    stretch, t_stretch, paused_s = 1, time.time(), 0.0

    def active_s():
        """Measuring time in the current stretch, pauses excluded."""
        return time.time() - t_stretch - paused_s

    def measure(pattern, control, label):
        """Run one trial until saved or abandoned: returns 'ok', 'skipped' or 'quit'."""
        nonlocal n, last_summary, paused_s
        while True:
            m, sec = divmod(int(active_s()), 60)
            header = (f"{label}   ·   stretch {stretch}/{args.stretches} {m}:{sec:02d}"
                      f"   ·   previous: {last_summary or '-'}")
            k = len(pattern)
            if plan_name in PLAN_CYCLES and not control:
                cycles, warmup = PLAN_CYCLES[plan_name]
            elif any(mod_of(e) for e in pattern):
                cycles, warmup = MOD_CYCLES   # layer switches need practice (user)
            else:
                cycles, warmup = CYCLES[k], WARMUP_CYCLES[k]
            status, presses = run_trial(kb, pattern, header, cycles)
            if status == "quit":
                return "quit"
            if status == "restart":
                continue
            if status == "paused":
                screen("Paused (trial discarded).", "",
                       "   Key presses in other windows are ignored.",
                       "   Press any measurement key here to continue, Esc to quit.")
                t_pause = time.time()
                key = kb.next_press()[0]
                paused_s += time.time() - t_pause
                if key == "quit":
                    return "quit"
                continue
            rating = ask_rating(kb, header)
            if rating == "quit":
                return "quit"
            if rating == "redo":
                continue
            rec = {"session": session, "time": datetime.datetime.now().isoformat(timespec="seconds"),
                   "protocol": PROTOCOL, "plan": None if control else plan_name,
                   "pattern": pattern, "word": WORD_TEXT.get(tuple(pattern)), "control": control,
                   "status": "skipped" if rating == "skip" else "ok",
                   "rating": rating if isinstance(rating, int) else None,
                   "cycles": cycles, "warmup_cycles": warmup, "advance_on_error": True,
                   "presses": presses}
            with open(TRIALS, "a") as f:
                f.write(json.dumps(rec) + "\n")
            last_summary = summarize(pattern, presses)
            n += 1
            return rec["status"]

    def controls(when):
        for i, c in enumerate(CONTROLS):
            if measure(display_order(c), True, f"control {i + 1}/{len(CONTROLS)} ({when})") == "quit":
                return "quit"

    def take_break():
        """Countdown, then ask: 'continue', 'finish' (with end controls) or 'quit'."""
        end = time.time() + BREAK_S
        while time.time() < end:
            screen(f"Stretch {stretch}/{args.stretches} done. Break - shake out the hand.", "",
                   f"   {int(end - time.time()) + 1:3d} s")
            for pos, _down, _t in kb.events(min(1.0, max(0.0, end - time.time()))):
                if pos == "quit":
                    return "quit"
        screen(f"Break over. Stretch {stretch}/{args.stretches} done.", "",
               "   Any measurement key: next stretch.",
               "   Del: finish the session (end controls).   Esc: quit without them.")
        key = kb.next_press()[0]
        return {"quit": "quit", SKIP_KEY: "finish"}.get(key, "continue")

    try:
        screen("Measurement session", "",
               "   Use layer 4 or the measurement layer (palm + outer home key).",
               "   Type the shown sequence cyclically, as if it were part of a word:",
               "   separate presses, not an oscillation and not a sprint.",
               "   Del pauses; Esc / Ctrl-C on any keyboard quits.", "",
               "   Press any measurement key to start.")
        if kb.next_press()[0] == "quit":
            return
        if controls("start") == "quit":
            return
        while todo:
            if plan_name in AS_PLANNED:
                pattern = list(todo[0])
            elif plan_name in SPACE_LAST:
                pattern = space_last(todo[0])
            else:
                pattern = display_order(todo[0])
            if len(pattern) == 2 and random.random() < 0.5:
                pattern.reverse()   # balance which key comes first
            status = measure(pattern, False, f"trial {measured + 1}/{total_plan}")
            if status == "quit":
                screen("Ending the session.", "",
                       "   Any measurement key: run the end controls first.",
                       "   Esc: quit without them.")
                if kb.next_press()[0] != "quit":
                    controls("end")
                return
            todo.pop(0)
            if status == "ok":
                measured += 1
            if active_s() >= STRETCH_S and todo:
                if stretch >= args.stretches:
                    break
                choice = take_break()
                if choice == "quit":
                    return
                if choice == "finish":
                    break
                stretch, t_stretch, paused_s = stretch + 1, time.time(), 0.0
        controls("end")
    finally:
        sys.stdout.write("\x1b[?1004l")
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(f"\nSaved {n} trials to {os.path.relpath(TRIALS)}")


def cycle_time(trial):
    """Median duration of one full pass through the pattern, in ms."""
    k = len(trial["pattern"])
    warmup = trial.get("warmup_cycles", WARMUP_CYCLES[k])
    t = {idx: down for _pos, down, _up, idx in trial["presses"] if idx >= 0}
    cyc = []
    for c in range(warmup, trial["cycles"]):
        a, b = c * k, c * k + k
        # all slots correct (a wrong key leaves its slot out, see run_trial)
        if all(i in t for i in range(a, b + 1)) and t[b] - t[a] < PAUSE_MS * k:
            cyc.append(t[b] - t[a])
    return statistics.median(cyc) if cyc else None


def cmd_stats(args):
    trials = load_trials()
    ok = [t for t in trials if t["status"] == "ok"]
    print(f"{len(trials)} trials ({len(ok)} ok, {len(trials) - len(ok)} skipped)")
    p2 = [t for t in ok if t.get("protocol", 1) >= PROTOCOL]
    print(f"  protocol 1 (exploratory): {len(ok) - len(p2)},  protocol {PROTOCOL}: {len(p2)}")

    sessions = sorted({t["session"] for t in p2})
    print("\nPhase 1, protocol 2: cycle time in ms (rating) per session")
    by = {}
    for t in p2:
        by.setdefault(canonical(t["pattern"]), {}).setdefault(t["session"], []).append(t)
    plan = phase1_plan()
    for p in plan:
        cells = []
        for s in sessions:
            ts = [t for t in by.get(p, {}).get(s, []) if not t["control"]]
            ct = [cycle_time(t) for t in ts]
            cells.append(" ".join(f"{c:4.0f}({t['rating']})" if c else "   ? " for c, t in zip(ct, ts)) or "    -   ")
        print(f"  {' '.join(LABEL[x] for x in p):<12} " + "  ".join(f"{c:>9}" for c in cells))
    print(f"  measured in >=1 session: {sum(1 for p in plan if p in by)}/{len(plan)}")

    print("\nControls: cycle time in ms per session (start → end)")
    for s in sessions:
        ctl = [t for t in p2 if t["session"] == s and t["control"]]
        parts = []
        for c in CONTROLS:
            v = [cycle_time(t) for t in ctl if canonical(t["pattern"]) == canonical(c)]
            parts.append(f"{' '.join(LABEL[x] for x in c)}: " + " → ".join(f"{x:.0f}" for x in v if x))
        print(f"  {s}   " + "   ".join(parts))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--stretches", type=int, default=5,
                   help=f"at most this many {STRETCH_S // 60}-minute stretches, "
                        f"with {BREAK_S} s breaks in between")
    r.add_argument("--patterns", help="file with one pattern per line, e.g. 'r2c2 r2c3 r1c4'")
    r.add_argument("--plan", choices=sorted(PLANS), default="phase1")
    r.add_argument("--repeats", type=int, default=3,
                   help="target number of sessions in which each pattern is measured")
    sub.add_parser("stats")
    args = ap.parse_args()
    {"run": cmd_run, "stats": cmd_stats}[args.cmd](args)


if __name__ == "__main__":
    main()
