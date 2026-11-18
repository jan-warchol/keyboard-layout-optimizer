"""Extract right-hand-only bigram timings from the 2025 two-handed keystream.

Assumes layer 0 of the Model 100 layout was active in Sep-Oct 2025. Only keys
whose keycode maps to a single right-hand position (no dual-use keys, no keys
duplicated on other layers) are used.

Position notation: (row, col) on the right half. row 0 = number row,
1 = top, 2 = home, 3 = bottom. col 0 = inner column (Enter/Bksp keys),
1 = index stretch (H column), 2 = index, 3 = middle, 4 = ring, 5 = pinky,
6 = pinky stretch.
"""
import csv, sys, statistics, collections, datetime

POS = {
    'dot': (1, 1), 'u': (1, 2), 'i': (1, 3), 'o': (1, 4),
    'y': (2, 1), 'n': (2, 2), 'r': (2, 3), 'l': (2, 4), 'h': (2, 5),
    'backspace': (3, 0), 'p': (3, 1), 'm': (3, 2), 'k': (3, 3), 'j': (3, 4), 'g': (3, 5),
}
FINGER = {0: 'I', 1: 'I', 2: 'I', 3: 'M', 4: 'R', 5: 'P', 6: 'P'}
MAX_GAP = 600  # ms; longer gaps are pauses, not transitions

def main(path, out):
    times = collections.defaultdict(list)
    prev = None
    with open(path) as f:
        for row in csv.DictReader(f, delimiter='\t'):
            if row['dev'] != 'keyboardio':
                prev = None; continue
            month = datetime.datetime.fromtimestamp(float(row['t'])).strftime('%Y-%m')
            k = row['key']
            ok = month in ('2025-09', '2025-10') and row['mods'] == '-' and k in POS
            if ok and prev is not None and row['gap_ms']:
                g = int(float(row['gap_ms']))
                if g <= MAX_GAP:
                    times[(prev, k)].append(g)
            prev = k if ok else None
    with open(out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['a', 'b', 'pos_a', 'pos_b', 'fingers', 'n', 'median_ms', 'p25_ms', 'p75_ms'])
        for (a, b), ts in sorted(times.items(), key=lambda x: -len(x[1])):
            if len(ts) < 8: continue
            q = statistics.quantiles(ts, n=4)
            pa, pb = POS[a], POS[b]
            w.writerow([a, b, f'r{pa[0]}c{pa[1]}', f'r{pb[0]}c{pb[1]}',
                        FINGER[pa[1]] + FINGER[pb[1]], len(ts),
                        int(statistics.median(ts)), int(q[0]), int(q[2])])

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
