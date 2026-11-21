#!/usr/bin/env python3
"""Statistics of the corpora for a quick look: per-source and combined
n-grams, each source's share of the combined n-grams, top words, shortcuts.

  python3 analysis/corpus_report.py OUT.json
"""
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import corpus  # noqa: E402

TOP = 150


def shortcuts():
    out = {}
    for year in ("2025", "2026"):
        c = collections.Counter()
        path = os.path.join(corpus.DATA, f"processed/{year}/keystream.tsv")
        with open(path, encoding="utf-8") as f:
            next(f)
            for line in f:
                parts = line.rstrip("\n").split("\t")
                key, mods = parts[2], parts[3]
                if mods in ("-", "shift", "altgr", "shift+altgr") or key in (
                        "leftctrl", "rightctrl", "leftshift", "rightshift", "leftalt",
                        "rightalt", "leftmeta", "rightmeta"):
                    continue
                c[f"{mods}+{key}"] += 1
        out[year] = c.most_common(60)
    return out


def main():
    srcs, words = {}, {}
    for name, lines in corpus.sources().items():
        lines = list(lines)
        g = corpus.count(lines)
        srcs[name] = g
        wc = collections.Counter()
        for w, text in lines:
            for tok in re.findall(r"[^\s⎘⇥]+", text):
                wc[tok.lower()] += w
        words[name] = wc
    weight = {n: corpus.SOURCE_WEIGHT[n] * corpus.CATEGORY_WEIGHT[corpus.CATEGORY[n]]
              / sum(srcs[n][1].values()) for n in srcs}
    report = {"sources": {}, "combined": {}, "weights": {
        n: {"category": corpus.CATEGORY[n], "share": corpus.SOURCE_WEIGHT[n]
            * corpus.CATEGORY_WEIGHT[corpus.CATEGORY[n]], "chars": sum(srcs[n][1].values())}
        for n in srcs}}
    for n in (1, 2, 3):
        comb = collections.Counter()
        parts = collections.defaultdict(dict)
        for name, g in srcs.items():
            for k, v in g[n].items():
                comb[k] += v * weight[name]
                parts[k][name] = v * weight[name]
        tot = sum(comb.values())
        report["combined"][n] = [
            [k, v / tot, {s: x / v for s, x in parts[k].items()}] for k, v in comb.most_common(TOP)]
        for name, g in srcs.items():
            t = sum(g[n].values())
            report["sources"].setdefault(name, {})[n] = [[k, v / t] for k, v in g[n].most_common(TOP)]
    for name, wc in words.items():
        t = sum(wc.values())
        report["sources"][name]["words"] = [[k, v / t] for k, v in wc.most_common(80)]
    report["shortcuts"] = shortcuts()
    with open(sys.argv[1], "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
