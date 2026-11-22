#!/usr/bin/env python3
"""Write an optimized layout into free layers of a Chrysalis export.

  python3 optimizer/export_layout.py LAYOUT.json IN.json OUT.json [--base 3] [--replace]

--replace: the layers already hold a layout; rewrite only their grid keys
and keep everything else on them (layer keys the user placed there).

Layers: BASE = base layer, BASE+1 = second letter layer, BASE+2 = Polish
one-shot layer (if the layout uses the one-shot key). Only the right-hand
grid (rows 0-3, columns 1-6) is written; empty grid keys are blocked, every
other key stays transparent, so Space, Enter, thumbs and the left half
fall through to the layers below. The layer keys themselves (entering the
layout, holding layer 2) are left to the user.

Key codes (Kaleidoscope): HID usage, + 2048 = with Shift (shifted-only US
symbols), + 1024 = with AltGr (Polish letters on a Polish programmer host
layout), OneShot layer n = 49161 + n.
"""
import json
import os
import string
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "measure"))
from model100 import MATRIX  # noqa: E402

SHIFT, ALTGR, OSL_FIRST, TRANSPARENT, BLOCKED = 2048, 1024, 49161, 65535, 0
LETTER = {c: 4 + i for i, c in enumerate(string.ascii_lowercase)}
PLAIN = {"-": 45, "=": 46, "[": 47, "]": 48, "\\": 49, ";": 51, "'": 52, "`": 53,
         ",": 54, ".": 55, "/": 56}
SHIFTED = {"!": 30, "@": 31, "#": 32, "$": 33, "%": 34, "^": 35, "&": 36, "*": 37,
           "(": 38, ")": 39, "_": 45, "+": 46, "{": 47, "}": 48, "|": 49, ":": 51,
           '"': 52, "~": 53, "<": 54, ">": 55, "?": 56}
DK = "ℙ"


def key_for(ch, polish_layer):
    if ch in LETTER:
        return {"code": LETTER[ch], "label": {"base": ch, "shifted": ch.upper()}}
    if ch in PLAIN:
        return {"code": PLAIN[ch], "label": {"base": ch}}
    if ch in SHIFTED:
        return {"code": SHIFT + SHIFTED[ch], "label": {"hint": {"full": "", "1u": ""}, "base": ch},
                "categories": ["with-modifiers", "shift"]}
    if ch == DK:
        return {"code": OSL_FIRST + polish_layer,
                "label": {"hint": "OneShot", "base": f"#{polish_layer}"},
                "target": polish_layer, "rangeStart": OSL_FIRST, "categories": ["layer", "oneshot"]}
    raise SystemExit(f"no key code for {ch!r}")


def blank(code):
    if code == TRANSPARENT:
        return {"code": code, "label": {"base": {"full": "Transparent", "1u": " "}},
                "categories": ["blanks"]}
    return {"code": code, "label": {"base": {"full": "Blocked", "1u": "XXX"}}, "categories": ["blanks"]}


def main():
    args = sys.argv[1:]
    base = 3
    if "--base" in args:
        i = args.index("--base")
        base = int(args[i + 1])
        del args[i:i + 2]
    replace = "--replace" in args
    if replace:
        args.remove("--replace")
    layout_f, src, dst = args
    lay = json.load(open(layout_f))
    d = json.load(open(src))
    km = d["keymaps"]
    polish = lay.get("polish") == "oneshot"
    layers = [base, base + 1] + ([base + 2] if polish else [])
    grid = [f"r{r}c{c}" for r in range(4) for c in range(1, 7)]
    for li in layers:
        if replace:
            for pos in grid:
                r, c = MATRIX[pos]
                km[li][r * 16 + c] = blank(TRANSPARENT)
            continue
        if any(k["code"] != TRANSPARENT for k in km[li]):
            sys.exit(f"layer {li} is not empty, refusing to overwrite (--replace keeps its non-grid keys)")
        km[li] = [blank(TRANSPARENT) for _ in range(64)]
    for li in (base, base + 1):
        for pos in grid:
            r, c = MATRIX[pos]
            km[li][r * 16 + c] = blank(BLOCKED)
    chars = {}
    for k in lay["keys"]:
        if k["shift"] == 0:
            chars[(k["pos"], k["layer"])] = k["char"]
    for (pos, layer), ch in chars.items():
        r, c = MATRIX[pos]
        km[base + layer][r * 16 + c] = key_for(ch, base + 2)
    if polish:
        # Polish letter on the physical key of its Latin letter, either layer
        where = {ch: pos for (pos, _layer), ch in chars.items()}
        for pl, lat in lay["polish_map"].items():
            r, c = MATRIX[where[lat]]
            km[base + 2][r * 16 + c] = {"code": ALTGR + LETTER[lat],
                                        "label": {"hint": {"full": "AltGr+", "1u": "AGr+"}, "base": lat},
                                        "categories": ["with-modifiers", "altgr"]}
    names = d["deviceConfiguration"]["layernames"]["names"]
    for li, n in zip(layers, ("opt", "opt2", "optPL")):
        names[li] = n
    cfg = d["deviceConfiguration"]
    if len(cfg["keymap.custom"].split()) != sum(len(l) for l in km):
        sys.exit("keymap.custom length mismatch")
    cfg["keymap.custom"] = " ".join(str(k["code"]) for l in km for k in l)
    json.dump(d, open(dst, "w"), indent=2, ensure_ascii=False)
    print(f"wrote {dst}: layers {layers}")


if __name__ == "__main__":
    main()
