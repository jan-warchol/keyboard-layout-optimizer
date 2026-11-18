"""Add the measurement layer to a Chrysalis layout export.

Writes layer 1 (unused in the current layout): every right-half key sends a
unique plain key, mostly copied from layer 4 (see model100.LAYER_KEYS), left top-inner key is
LockTo #0 (same exit as layer 7). Entry: on layer 2 (held palm), the outer
home key r2c6 becomes LockTo #1 (next to the existing LockTo #7).

Usage: python3 measure/make_measurement_layer.py IN.json OUT.json
"""
import json
import sys

from model100 import MATRIX, LAYER_KEYS

LAYER = 1
LOCKTO = 17408


def key(code, label, **extra):
    return {"code": code, "label": label, **extra}


def main(src, dst):
    d = json.load(open(src))
    km = d["keymaps"]
    for pos, (label, hid, _linux) in LAYER_KEYS.items():
        r, c = MATRIX[pos]
        km[LAYER][r * 16 + c] = key(hid, {"base": label})
    km[LAYER][0 * 16 + 6] = key(LOCKTO, {"hint": "LockTo", "base": "#0"},
                               target=0, rangeStart=LOCKTO, categories=["layer", "locktolayer"])
    r, c = MATRIX["r2c6"]
    if km[2][r * 16 + c]["code"] != 65535:
        sys.exit(f"layer 2 {r},{c} is not transparent, refusing to overwrite")
    km[2][r * 16 + c] = key(LOCKTO + LAYER, {"hint": "LockTo", "base": f"#{LAYER}"},
                           target=LAYER, rangeStart=LOCKTO, categories=["layer", "locktolayer"])
    # Keep the raw EEPROM dump consistent with the edited keymaps.
    cfg = d.get("deviceConfiguration", {})
    if "keymap.custom" in cfg:
        old = cfg["keymap.custom"].split()
        if len(old) != sum(len(l) for l in km):
            sys.exit("keymap.custom length mismatch, refusing to guess")
        cfg["keymap.custom"] = " ".join(str(k["code"]) for l in km for k in l)
    json.dump(d, open(dst, "w"), indent=2, ensure_ascii=False)
    print(f"wrote {dst}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
