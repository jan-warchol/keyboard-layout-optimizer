#!/usr/bin/env python3
"""Character n-gram tables from the typing corpora, weighted by context.

Sources (in keystats-data/, see the keystats README):
  prose: 2025 keylog prose lines, 2026 keylog prose lines, task notes,
         prose typed in the shell (commit messages, agent prompts)
  code:  shell commands (weighted typed text), 2025 and 2026 keylog code lines
Shell history is split into commands and prose by keystats'
split_history_prose.py.

Each source is normalised to total weight 1, then mixed with SOURCE_WEIGHT
inside its category and CATEGORY_WEIGHT between categories (measurement sessions are dropped from the keylogs; the 2026 keylog,
typed on the one-handed layout, is ~60% prose (incl. agent prompts) and ~40%
shell/code by characters). All weights are *(guess)*; vary them and compare
layouts.

Letters are case-folded: a capital costs the same Shift wherever its key is.
Each line is a typing unit between two Enters ('\\n'); n-grams don't cross
lines. Tab completion '⇥' is Tab; a paste '⎘' breaks the n-gram.

  python3 analysis/corpus.py          -> analysis/corpus/{1,2,3}grams.tsv
"""
import collections
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "keystats-data")
OUT = os.path.join(HERE, "corpus")

CATEGORY_WEIGHT = {"prose": 0.6, "code": 0.4}
SOURCE_WEIGHT = {
    # 2026 keylog: the current mix, but only ~3k characters, so kept small
    "prose-2025": 0.35, "prose-2026": 0.1, "notes": 0.35, "shell-prose": 0.2,
    "shell": 0.65, "code-2025": 0.25, "code-2026": 0.1,
}
CATEGORY = {"prose-2025": "prose", "prose-2026": "prose", "notes": "prose", "shell-prose": "prose",
            "shell": "code", "code-2025": "code", "code-2026": "code"}
BREAK = "⎘"
# Code lines (shell history and keylog), adjusted to how the user types now
# (user's judgement, 2026-11-21). Applied when reading; source files untouched.
# - `git` is typed as the `g` alias;
# - committing is left to agents: commit and amend commands are dropped, and
#   so is the `ZZ` that closed the commit-message editor (`ZZg ll` -> `g ll`);
# - other git commands and Vim (ex commands, `dd`, `vim file`) are typed less
#   than in the history: their lines count GIT_WEIGHT / VIM_WEIGHT.
# Each source is normalised afterwards, so this shifts the mix *inside* a
# source; the source's share of the total stays as in SOURCE_WEIGHT.
GIT = re.compile(r"(^|[;&|(]\s*)git(?=\s|$)")
COMMIT = re.compile(r"(^|[;&|(]\s*)g\s+(ci|commit|amq|amci)\b")   # amq, amci: amend
GIT_LINE = re.compile(r"(^|[;&|(⋯]\s*)g(\s|$)")
EDITOR_EXIT = re.compile(r"^\s*ZZ(?=\S)")
VIM_LINE = re.compile(r"^\s*(:|ZZ\s*$|dd\b|n?vim?(\s|$))")
# Vim normal-mode keys logged as "code" lines in the 2025 keylog
VIM_NORMAL = re.compile(r"^\s*\]?(yap|sip|v:bu|cw\w|ddp|dd|pu|ap)\s*$")
# Not typed: fzf key-binding widgets written into the history
NOT_TYPED = re.compile(r"__fzf_\w+__")
# Notes: non-breaking spaces mark text pasted from the web; identical lines
# (recurring tasks re-created by the app) count at most NOTES_MAX_REPEAT times
PASTED = "\xa0"
NOTES_MAX_REPEAT = 3
GIT_WEIGHT = 0.3
VIM_WEIGHT = 0.3
# `q` closing the git pager, then the next git command (`qg d`): two separate
# operations. N-grams across SOFT (`qg`, `qg `) count SOFT_WEIGHT.
PAGER_QUIT = re.compile(r"^(\s*q)(?=g(\s|$))")
SOFT = "⋯"
SOFT_WEIGHT = 0.2


def text_lines(path, commands=False):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            w, line = adjust_command(1.0, line) if commands else (1.0, line)
            if w > 0 and line.strip():
                yield w, line


def notes_lines(path):
    seen = collections.Counter()
    for w, line in text_lines(path):
        if PASTED in line:
            continue
        seen[line.strip()] += 1
        if seen[line.strip()] <= NOTES_MAX_REPEAT:
            yield w, line


TRIALS = os.path.join(HERE, "..", "data", "measurements", "trials.jsonl")
SESSION_PAD_S = 60   # rating screens, breaks at the edges of a session


def measurement_windows():
    """(start, end) epoch seconds of each measurement session: typing there
    is trials, not everyday typing."""
    spans = {}
    with open(TRIALS) as f:
        for l in f:
            t = json.loads(l)
            ts = [x for p in t["presses"] for x in (p[1], p[2]) if x]
            if ts:
                a, b = spans.get(t["session"], (min(ts), max(ts)))
                spans[t["session"]] = (min(a, min(ts)), max(b, max(ts)))
    return [(a / 1000 - SESSION_PAD_S, b / 1000 + SESSION_PAD_S) for a, b in spans.values()]


def keylog_lines(path, kind):
    windows = measurement_windows()
    with open(path, encoding="utf-8") as f:
        for l in f:
            run = json.loads(l)
            for ln in run["lines"]:
                t0, t1 = ln["t"]
                if any(t0 < b and t1 > a for a, b in windows):
                    continue
                if ln["kind"] == kind and ln["text"].strip():
                    w, t = adjust_command(1.0, ln["text"]) if kind == "code" else (1.0, ln["text"])
                    if w > 0:
                        yield w, t


def shell_lines(path, commands=False):
    with open(path, encoding="utf-8") as f:
        for l in f:
            w, t = l.rstrip("\n").split("\t", 1)
            w = float(w)
            if commands:
                w, t = adjust_command(w, t)
            if w > 0 and t.strip():
                yield w, t


def adjust_command(w, t):
    """git -> g, commit commands dropped (weight 0), git and Vim lines scaled."""
    if NOT_TYPED.search(t):
        return 0.0, t
    t = EDITOR_EXIT.sub("", GIT.sub(r"\1g", t))
    t = PAGER_QUIT.sub(r"\1" + SOFT, t)
    if COMMIT.search(t):
        return 0.0, t
    if GIT_LINE.search(t):
        w *= GIT_WEIGHT
    elif VIM_LINE.search(t) or VIM_NORMAL.search(t):
        w *= VIM_WEIGHT
    return w, t


def sources():
    return {
        "prose-2025": text_lines(os.path.join(DATA, "processed/2025/by-kind/prose.txt")),
        "prose-2026": keylog_lines(os.path.join(DATA, "processed/2026/clean.jsonl"), "prose"),
        "notes": notes_lines(os.path.join(DATA, "todo-notes-data/processed-janek3.txt")),
        "shell-prose": shell_lines(os.path.join(DATA, "shell-history/processed-history-prose")),
        "shell": shell_lines(os.path.join(DATA, "shell-history/processed-history-commands"),
                             commands=True),
        "code-2025": text_lines(os.path.join(DATA, "processed/2025/by-kind/code.txt"), commands=True),
        "code-2026": keylog_lines(os.path.join(DATA, "processed/2026/clean.jsonl"), "code"),
    }


def count(lines, nmax=3):
    grams = [collections.Counter() for _ in range(nmax + 1)]

    def add(seg, w, skip_first):
        for n in range(1, nmax + 1):
            # the leading Enter belongs to the previous line: not counted alone
            start = 1 if (n == 1 and skip_first) else 0
            for i in range(start, len(seg) - n + 1):
                grams[n][seg[i:i + n]] += w

    for w, text in lines:
        text = text.lower()   # a capital is on its letter's key, + Shift anywhere
        # the line starts after the previous line's Enter, so its first key
        # is counted as entered (Enter → first key)
        for k, seg in enumerate(("\n" + text.replace("\t", "⇥") + "\n").split(BREAK)):
            if SOFT not in seg:
                add(seg, w, k == 0)
                continue
            # n-grams across a soft break count SOFT_WEIGHT, the rest fully
            add(seg.replace(SOFT, ""), w * SOFT_WEIGHT, k == 0)
            for j, piece in enumerate(seg.split(SOFT)):
                add(piece, w * (1 - SOFT_WEIGHT), k == 0 and j == 0)
    return grams


def main():
    os.makedirs(OUT, exist_ok=True)
    total = [collections.Counter() for _ in range(4)]
    for name, lines in sources().items():
        g = count(lines)
        size = sum(g[1].values())
        w = SOURCE_WEIGHT[name] * CATEGORY_WEIGHT[CATEGORY[name]] / size
        print(f"{name:11s} {size:9.0f} chars  weight/char {w:.2e}")
        for n in (1, 2, 3):
            for k, v in g[n].items():
                total[n][k] += v * w
    for n in (1, 2, 3):
        s = sum(total[n].values())
        with open(os.path.join(OUT, f"{n}grams.tsv"), "w", encoding="utf-8") as f:
            for k, v in total[n].most_common():
                if v / s >= 1e-6:
                    f.write(f"{json.dumps(k, ensure_ascii=False)}\t{v / s:.4e}\n")
    print("written to", OUT)


if __name__ == "__main__":
    main()
