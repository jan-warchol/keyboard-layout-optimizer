"""Physical geometry of the right half of the Keyboardio Model 100.

Position ids: "r{row}c{col}" for the main block, "t1".."t4" for thumb keys
(t1 = innermost), "palm" for the palm key.

  row 0 = number row, 1 = top, 2 = home, 3 = bottom
  col 0 = inner column (Any / Enter / Butterfly keys; there is no r2c0)
  col 1 = index stretch (H column), 2 = index, 3 = middle, 4 = ring,
  col 5 = pinky, 6 = pinky stretch

`matrix` maps an id to (row, col) in Kaleidoscope's 4x16 matrix, which is
also the order of keys in Chrysalis keymap JSON (index = row * 16 + col).
"""

MATRIX = {}
for _r in range(4):
    for _c in range(1, 7):
        MATRIX[f"r{_r}c{_c}"] = (_r, _c + 9)
MATRIX["r0c0"] = (0, 9)
MATRIX["r1c0"] = (1, 9)
MATRIX["r3c0"] = (2, 9)  # bottom inner ("butterfly") key sits in matrix row 2
MATRIX["t1"] = (3, 8)
MATRIX["t2"] = (2, 8)
MATRIX["t3"] = (1, 8)
MATRIX["t4"] = (0, 8)
MATRIX["palm"] = (3, 9)

# Positions measured in the experiment (palm excluded: it moves the whole hand).
MEASURED = [p for p in MATRIX if p != "palm"]

# Keys of the measurement layer: position -> (label, HID code, Linux keycode).
# Mirrors the right half of layer 4 (the layer currently used for typing) so
# positions are familiar, with these differences:
#  - dual-use keys (Alt/y, Layer6/l, AltGr/g, ...) are plain taps, because
#    dual-use keys emit on release and would distort the timing;
#  - number row arrows are replaced by digits 1-5 (also used for ratings);
#  - keys without a function on layer 4 get letters: blocked thumb t1 = x,
#    palm = z (palm is also the pause key).
LAYER_KEYS = {
    "r0c0": ("Del", 76, 111), "r0c1": ("1", 30, 2), "r0c2": ("2", 31, 3),
    "r0c3": ("3", 32, 4), "r0c4": ("4", 33, 5), "r0c5": ("5", 34, 6), "r0c6": ("=", 46, 13),
    "r1c0": ("Ent", 40, 28), "r1c1": (".", 55, 52), "r1c2": ("u", 24, 22), "r1c3": ("i", 12, 23),
    "r1c4": ("o", 18, 24), "r1c5": ("b", 5, 48), "r1c6": ("-", 45, 12),
    "r2c1": ("y", 28, 21), "r2c2": ("n", 17, 49), "r2c3": ("r", 21, 19),
    "r2c4": ("l", 15, 38), "r2c5": ("h", 11, 35), "r2c6": (";", 51, 39),
    "r3c0": ("Bsp", 42, 14), "r3c1": ("p", 19, 25), "r3c2": ("m", 16, 50), "r3c3": ("k", 14, 37),
    "r3c4": ("j", 13, 36), "r3c5": ("g", 10, 34), "r3c6": ("/", 56, 53),
    "t1": ("x", 27, 45), "t2": ("Ctl", 228, 97), "t3": ("Sft", 229, 54), "t4": ("Spc", 44, 57),
    "palm": ("z", 29, 44),
}
LABEL = {pos: v[0] for pos, v in LAYER_KEYS.items()}

# Layer 4 (since the 2026-11-19 layout, all plain keys) sends the same keys as
# the measurement layer except these: position -> Linux keycode.
# r0c1 (LockTo #1) and palm (ShiftTo #5) send nothing there.
BASE_LAYER_ALT = {
    "r0c2": 105, "r0c3": 103, "r0c4": 108, "r0c5": 106,   # ← ↑ ↓ →
    "t1": 100,                                            # AltGr
}

# Terminal drawing of the right half. Each cell is 5 chars wide.
DIAGRAM_ROWS = [
    ["r0c0", None, "r0c1", "r0c2", "r0c3", "r0c4", "r0c5", "r0c6"],
    ["r1c0", None, "r1c1", "r1c2", "r1c3", "r1c4", "r1c5", "r1c6"],
    [None,   None, "r2c1", "r2c2", "r2c3", "r2c4", "r2c5", "r2c6"],
    ["r3c0", None, "r3c1", "r3c2", "r3c3", "r3c4", "r3c5", "r3c6"],
]
THUMB_ROW = ["t1", "t2", "t3", "t4", None, None, "palm"]
HOME_KEYS = {"r2c2", "r2c3", "r2c4", "r2c5"}
