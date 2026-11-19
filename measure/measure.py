#!/usr/bin/env python3
"""Measure the cost of key-position sequences on the right half of a Model 100.

Each trial highlights 1-4 keys and shows the sequence to type cyclically
(e.g. "u n u n ..." or "u n r u n r ..."), typed as if it were part of a
word - separate key presses, not a back-and-forth oscillation or a sprint.
Afterwards rate the discomfort on the top row keys . u i o b = 1-5
(Backspace = redo, Del = skip). Del during a trial pauses.

Works on the measurement layer (see make_measurement_layer.py) or on layer 4
(the typing layer, plain keys since 2026-11-19): both send the same keys
except the number row and t1, which are recognised in both versions.
Timestamps come from the kernel input device, not the terminal.

  python3 measure/measure.py run [--minutes 20] [--plan phase1|bigrams]
                                 [--patterns FILE] [--repeats N]
      phase1:  home-row fingers + Space thumb (the baseline, see
               docs/design-principles.md); each pattern once per session
      phase2a: same finger, two different keys, hand position free
      bigrams: all 2-key position pairs (exploratory, protocol 1)
      FILE: one sequence per line, key labels or position ids,
            e.g. "u n r" or "r1c2 r2c2 r2c3"
  python3 measure/measure.py stats
"""
import argparse
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
CYCLES = {1: 30, 2: 20, 3: 13, 4: 10}       # cycles per trial, by pattern length
WARMUP_CYCLES = {1: 8, 2: 5, 3: 3, 4: 3}    # >= 8 presses before measuring
PAUSE_MS = 1500                 # longer gaps don't count as transitions
BREAK_EVERY_S = 13 * 60
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


def column(pos):
    return 0 if pos.startswith("t") else int(pos[3])   # thumb counts as innermost


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


PLANS = {"phase1": phase1_plan, "phase2a": phase2a_plan, "bigrams": bigram_plan}


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

    def events(self, timeout):
        """Yield (pos, is_press, t_ms) for measurement-layer keys; ('quit',..) on Esc/Ctrl-C."""
        r, _, _ = select.select(self.fds + [sys.stdin.fileno()], [], [], timeout)
        for fd in r:
            if fd == sys.stdin.fileno():
                data = os.read(fd, 1024)
                # bare Esc or Ctrl-C quits; Del etc. arrive as \x1b[... sequences
                if b"\x03" in data or data == b"\x1b":
                    yield ("quit", True, 0.0)
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
                if down:
                    return pos, t
            if timeout is not None:
                return None, None


# ---------------------------------------------------------------- drawing

def draw_keyboard(labels):
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

def run_trial(kb, pattern, header):
    k = len(pattern)
    total = CYCLES[k] * k
    labels = {pos: LABEL[pos] for pos in pattern}
    seq = " ".join(LABEL[pattern[i % k]] for i in range(max(2 * k, 3))) + " …"
    presses, nxt, errors = [], 0, 0

    def show(msg=""):
        bar = "█" * nxt + "░" * (total - nxt)
        screen(header, "", draw_keyboard(labels), "",
               f"   type cyclically:  {seq}", f"   {bar}  errors: {errors}", "", msg)

    show("   start whenever ready   (Del = pause)")
    open_presses = {}
    while nxt < total:
        for pos, down, t in kb.events(None):
            if pos == "quit":
                return "quit", presses
            if not down:
                if pos in open_presses:
                    presses[open_presses.pop(pos)][2] = t
                continue
            if pos in PAUSE_KEYS:
                return "paused", presses
            ok = pos == pattern[nxt % k]
            presses.append([pos, t, None, nxt if ok else -1])
            open_presses[pos] = len(presses) - 1
            if ok:
                nxt += 1
            else:
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
        if t["status"] == "ok" and not t.get("control") and t.get("protocol", 1) >= PROTOCOL:
            c = canonical(t["pattern"])
            done[c] = done.get(c, 0) + 1
    if args.patterns:
        with open(args.patterns) as f:
            plan = [canonical([LABEL_TO_POS.get(x, x) for x in l.split()])
                    for l in f if l.strip() and not l.startswith("#")]
        bad = {p for pat in plan for p in pat if p not in LABEL}
        if bad:
            sys.exit(f"unknown keys in {args.patterns}: {sorted(bad)}")
    else:
        plan = PLANS[args.plan]()
    # each pattern at most once per session; least-measured first
    todo = [p for p in plan if done.get(p, 0) < args.repeats]
    random.shuffle(todo)
    todo.sort(key=lambda p: (done.get(p, 0), tier(p)))
    total_plan = len(plan) * args.repeats

    session = datetime.datetime.now().isoformat(timespec="seconds")
    kb = Keyboard()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    t_start = t_break = time.time()
    n, last_summary = 0, ""

    def measure(pattern, control, label):
        """Run one trial until saved or abandoned: returns 'ok', 'skipped' or 'quit'."""
        nonlocal n, last_summary
        while True:
            elapsed = int((time.time() - t_start) / 60)
            header = (f"{label}   ·   {elapsed} min   ·   previous: {last_summary or '-'}")
            status, presses = run_trial(kb, pattern, header)
            if status == "quit":
                return "quit"
            if status == "paused":
                screen("Paused.", "", "   Press any measurement key to continue, Esc to quit.")
                if kb.next_press()[0] == "quit":
                    return "quit"
                continue
            rating = ask_rating(kb, header)
            if rating == "quit":
                return "quit"
            if rating == "redo":
                continue
            k = len(pattern)
            rec = {"session": session, "time": datetime.datetime.now().isoformat(timespec="seconds"),
                   "protocol": PROTOCOL, "pattern": pattern, "control": control,
                   "status": "skipped" if rating == "skip" else "ok",
                   "rating": rating if isinstance(rating, int) else None,
                   "cycles": CYCLES[k], "warmup_cycles": WARMUP_CYCLES[k],
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
        measured = sum(min(v, args.repeats) for p, v in done.items() if p in set(plan))
        while todo and time.time() - t_start < args.minutes * 60:
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
            if time.time() - t_break > BREAK_EVERY_S:
                screen("Time for a short break - shake out the hand.", "",
                       "   Press any measurement key to continue, Esc to quit.")
                if kb.next_press()[0] == "quit":
                    return
                t_break = time.time()
        controls("end")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(f"\nSaved {n} trials to {os.path.relpath(TRIALS)}")


def cycle_time(trial):
    """Median duration of one full pass through the pattern, in ms."""
    k = len(trial["pattern"])
    warmup = trial.get("warmup_cycles", WARMUP_CYCLES[k])
    t = {idx: down for _pos, down, _up, idx in trial["presses"] if idx >= 0}
    errs = {i for i, (_p, _d, _u, idx) in enumerate(trial["presses"]) if idx < 0}
    cyc = []
    for c in range(warmup, trial["cycles"]):
        a, b = c * k, c * k + k
        if a in t and b in t and b - a == k and t[b] - t[a] < PAUSE_MS * k:
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
    r.add_argument("--minutes", type=float, default=20)
    r.add_argument("--patterns", help="file with one pattern per line, e.g. 'r2c2 r2c3 r1c4'")
    r.add_argument("--plan", choices=sorted(PLANS), default="phase1")
    r.add_argument("--repeats", type=int, default=3,
                   help="target number of sessions in which each pattern is measured")
    sub.add_parser("stats")
    args = ap.parse_args()
    {"run": cmd_run, "stats": cmd_stats}[args.cmd](args)


if __name__ == "__main__":
    main()
