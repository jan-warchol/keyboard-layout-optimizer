#!/usr/bin/env python3
"""Polish words typeable on layer 4, with 0 or 1 swapped letter.

Letters on the palm layer (layer 5) and Polish letters are typed with the
layer-4 key at the same position (measure.SWAPS), e.g. "mogę" -> "mogr".
Sources: the Wiktionary Polish frequency list (wikitext, download with
  curl -L "https://en.wiktionary.org/w/index.php?title=Wiktionary:Frequency_lists/Polish_wordlist&action=raw" -o FILE
) and the user's task database dump keystats/processed-janek-3.txt.

  python3 analysis/word_pool.py WIKTIONARY_FILE [N]   # print the N most frequent per group
"""
import collections
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "measure"))
from measure import LABEL, LETTER_POS, SWAPS, finger  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
TASKS = os.path.join(ROOT, "keystats", "processed-janek-3.txt")


def typed(word):
    """(letters typed on layer 4, number of swapped letters) or (None, None)."""
    out = [SWAPS.get(ch, ch) for ch in word]
    if not all(ch in LETTER_POS for ch in out):
        return None, None
    return "".join(out), sum(a != b for a, b in zip(word, out))


def pool(wikt_file):
    """word -> [typed, swaps, wiktionary count, task-dump count]"""
    raw = open(wikt_file).read()
    wikt = {w: int(n) for w, n in re.findall(r"\[\[([^#\]]+)#Polish\|[^\]]*\]\]</span> (\d+)", raw)}
    tasks = collections.Counter(re.findall(r"[a-ząęłóśćńżź]+", open(TASKS).read().lower()))
    res = {}
    for col, counts in ((2, wikt), (3, tasks)):
        for w, n in counts.items():
            if not 3 <= len(w) <= 7:
                continue
            t, s = typed(w)
            if t is None or s > 1 or any(a == b for a, b in zip(t, t[1:])):
                continue
            res.setdefault(w, [t, s, 0, 0])[col] += n
    return res


def main():
    res = pool(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 40
    rank = lambda w: -(res[w][2] / 1e4 + res[w][3])
    for s in (0, 1):
        ws = sorted((w for w, v in res.items() if v[1] == s), key=rank)
        print(f"{s} swaps: {len(ws)} words")
        print("  " + " ".join(w + (f"→{res[w][0]}" if s else "") for w in ws[:n]))
    tr = {(a, b) for v in res.values() for a, b in zip(v[0], v[0][1:])}
    print(f"letter-to-letter transitions covered: {len(tr)}")
    fc = collections.Counter(finger(LETTER_POS[c]) for v in res.values() for c in v[0])
    print("presses per finger: " + ", ".join(f"{f} {n / sum(fc.values()):.0%}" for f, n in fc.most_common()))


if __name__ == "__main__":
    main()
