#!/usr/bin/env python3
"""Measure the cost of key-position sequences on the right half of a Model 100.

Each trial highlights 1-3 keys and shows the sequence to type cyclically
(e.g. "u n u n ..." or "u n r u n r ...") at a comfortable, fluent pace -
not a sprint. Afterwards rate the discomfort on the number row keys 1-5
(Backspace = redo, Del = skip).

Needs the measurement layer (see make_measurement_layer.py) to be active.
Timestamps come from the kernel input device, not the terminal.

  python3 measure/measure.py run [--minutes 20] [--patterns FILE]
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

from model100 import DIAGRAM_ROWS, HOME_KEYS, LABEL, LAYER_KEYS, MEASURED, THUMB_ROW

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "measurements")
TRIALS = os.path.join(DATA, "trials.jsonl")

CODE_TO_POS = {linux: pos for pos, (_label, _hid, linux) in LAYER_KEYS.items()}
LABEL_TO_POS = {label: pos for pos, label in LABEL.items()}

RATING_KEYS = {"r0c1": 1, "r0c2": 2, "r0c3": 3, "r0c4": 4, "r0c5": 5}
REDO_KEY, SKIP_KEY, PAUSE_KEY = "r3c0", "r0c0", "palm"
RATING_TEXT = "1 effortless · 2 fine · 3 some effort · 4 uncomfortable · 5 strain"

CYCLES = {1: 30, 2: 20, 3: 13}  # cycles per trial, by pattern length
WARMUP_CYCLES = 2
PAUSE_MS = 1500                 # longer gaps don't count as transitions
BREAK_EVERY_S = 13 * 60
CONTROL_EVERY = 13
CONTROLS = [("r2c2", "r2c3"), ("r1c3", "r3c2"), ("r2c2", "r2c5")]
CORE = {f"r{r}c{c}" for r in (1, 2, 3) for c in range(1, 6)}

EVENT = struct.Struct("llHHi")
EV_KEY = 1


# ---------------------------------------------------------------- patterns

def canonical(pattern):
    """Cyclic patterns are equal up to rotation: 'AB' == 'BA'."""
    p = list(pattern)
    return min(tuple(p[i:] + p[:i]) for i in range(len(p)))


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


def load_trials():
    if not os.path.exists(TRIALS):
        return []
    with open(TRIALS) as f:
        return [json.loads(line) for line in f if line.strip()]


def transitions(trial):
    """Valid (from, to, ms) transitions of a trial, warm-up and errors excluded."""
    k = len(trial["pattern"])
    out, prev = [], None
    for pos, t_down, _t_up, idx in trial["presses"]:
        if idx < 0:            # wrong key: breaks the chain
            prev = None
            continue
        if prev is not None and idx >= WARMUP_CYCLES * k:
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

    show("   start whenever ready   (palm = pause)")
    open_presses = {}
    while nxt < total:
        for pos, down, t in kb.events(None):
            if pos == "quit":
                return "quit", presses
            if not down:
                if pos in open_presses:
                    presses[open_presses.pop(pos)][2] = t
                continue
            if pos == PAUSE_KEY:
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
               f"   number row:  {RATING_TEXT}",
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
    done = {}
    for t in load_trials():
        if t["status"] == "ok" and not t.get("control"):
            done[canonical(t["pattern"])] = done.get(canonical(t["pattern"]), 0) + 1
    if args.patterns:
        with open(args.patterns) as f:
            plan = [canonical([LABEL_TO_POS.get(x, x) for x in l.split()])
                    for l in f if l.strip() and not l.startswith("#")]
        bad = {p for pat in plan for p in pat if p not in LABEL}
        if bad:
            sys.exit(f"unknown keys in {args.patterns}: {sorted(bad)}")
    else:
        plan = bigram_plan()
    todo = [p for p in plan if done.get(p, 0) < args.repeats]
    random.shuffle(todo)
    todo.sort(key=tier)
    total_plan = len(plan) * args.repeats

    session = datetime.datetime.now().isoformat(timespec="seconds")
    kb = Keyboard()
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    t_start = t_break = time.time()
    n, last_summary = 0, ""
    try:
        screen("Measurement session", "",
               "   Activate the measurement layer (palm + outer home key).",
               "   Type the shown sequence cyclically at a comfortable, fluent pace.",
               "   Palm key pauses; Esc / Ctrl-C on any keyboard quits.", "",
               "   Press any measurement key to start.")
        if kb.next_press()[0] == "quit":
            return
        while todo and time.time() - t_start < args.minutes * 60:
            control = n > 0 and n % CONTROL_EVERY == 0
            pattern = list(random.choice(CONTROLS)) if control else list(todo[0])
            if not control and len(pattern) == 2 and random.random() < 0.5:
                pattern.reverse()   # balance which key comes first
            elapsed = int((time.time() - t_start) / 60)
            header = (f"trial {sum(done.values()) + 1}/{total_plan}"
                      f"{'  (control)' if control else ''}   ·   {elapsed} min   ·   "
                      f"previous: {last_summary or '-'}")
            status, presses = run_trial(kb, pattern, header)
            if status == "quit":
                break
            if status == "paused":
                screen("Paused.", "", "   Press any measurement key to continue, Esc to quit.")
                if kb.next_press()[0] == "quit":
                    break
                continue
            rating = ask_rating(kb, header)
            if rating == "quit":
                break
            if rating == "redo":
                continue
            rec = {"session": session, "time": datetime.datetime.now().isoformat(timespec="seconds"),
                   "pattern": pattern, "control": control,
                   "status": "skipped" if rating == "skip" else "ok",
                   "rating": rating if isinstance(rating, int) else None,
                   "cycles": CYCLES[len(pattern)], "warmup_cycles": WARMUP_CYCLES,
                   "presses": presses}
            with open(TRIALS, "a") as f:
                f.write(json.dumps(rec) + "\n")
            last_summary = summarize(pattern, presses)
            n += 1
            if not control:
                todo.pop(0)
                if rec["status"] == "ok":
                    c = canonical(pattern)
                    done[c] = done.get(c, 0) + 1
            if time.time() - t_break > BREAK_EVERY_S:
                screen("Time for a short break - shake out the hand.", "",
                       "   Press any measurement key to continue, Esc to quit.")
                if kb.next_press()[0] == "quit":
                    break
                t_break = time.time()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        print(f"\nSaved {n} trials to {os.path.relpath(TRIALS)}")


def cmd_stats(args):
    trials = load_trials()
    ok = [t for t in trials if t["status"] == "ok"]
    print(f"{len(trials)} trials ({len(ok)} ok, {len(trials) - len(ok)} skipped)")
    plan = set(bigram_plan())
    covered = {canonical(t["pattern"]) for t in ok if not t["control"]}
    for tr in (1, 2, 3):
        p = {x for x in plan if tier(x) == tr}
        print(f"  tier {tr}: {len(p & covered)}/{len(p)} bigram patterns measured")
    print("controls by session (median ms):")
    by = {}
    for t in ok:
        if t["control"]:
            by.setdefault(t["session"], []).extend(ms for *_, ms in transitions(t))
    for s, v in sorted(by.items()):
        print(f"  {s}: {statistics.median(v):.0f} ms over {len(v)} transitions")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--minutes", type=float, default=20)
    r.add_argument("--patterns", help="file with one pattern per line, e.g. 'r2c2 r2c3 r1c4'")
    r.add_argument("--repeats", type=int, default=1, help="target measurements per pattern")
    sub.add_parser("stats")
    args = ap.parse_args()
    {"run": cmd_run, "stats": cmd_stats}[args.cmd](args)


if __name__ == "__main__":
    main()
