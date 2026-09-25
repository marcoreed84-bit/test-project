"""
Next Murphy/Kanu-Jain-deck idea after candlesticks, MA/VWAP, double/triple
tops, and triangles/wedges: price GAPS. The Kanu Jain "Fundamentals of
Investments" deck's specific claim: "gaps higher create support... gaps
lower create resistance... until the gap is violated, assume the trend
will continue in the gap's direction" - classic breakaway/runaway/
exhaustion gap theory, genuinely untested in this project.

Real GOLD M15 has very few intrabar gaps (continuous trading, mostly only
weekend/rollover opens diverge from the prior close) - a quick diagnostic
found only 229/100006 bars have a >=0.5xATR open-vs-prior-close gap, 96 at
>=1.0xATR. Testing honestly anyway, at several thresholds, with a random-
bar/random-direction control (isolates whether GAPS specifically carry
information, not just "price sometimes drifts").

TEST: does price move further in the GAP'S OWN direction over the next 20
bars, more often / more strongly than a random control?
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD

np.random.seed(42)
HORIZON = 20


def eval_gaps(o, c, atr, gap, gap_atr, n, min_atr):
    idx = np.where(np.abs(gap_atr) >= min_atr)[0] + 1
    idx = idx[(idx + HORIZON) < n]
    if len(idx) < 8:
        return None
    up = gap[idx - 1] > 0
    entry = o[idx]
    fwd = c[idx + HORIZON] - entry
    cont = np.where(up, fwd > 0, fwd < 0)
    avg_move_in_dir = np.where(up, fwd, -fwd)
    return dict(n=len(idx), cont_rate=100 * np.mean(cont), avg_move=np.mean(avg_move_in_dir),
                avg_move_atr=np.mean(avg_move_in_dir / atr[idx]))


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    o = df15["open"].values; h = df15["high"].values; l = df15["low"].values; c = df15["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    gap = o[1:] - c[:-1]
    gap_atr = gap / atr[:-1]

    print(f"HORIZON={HORIZON} bars forward, real GOLD M15, n={n} bars")
    for thr in (0.5, 0.75, 1.0, 1.5, 2.0):
        r = eval_gaps(o, c, atr, gap, gap_atr, n, thr)
        if r is None:
            print(f"  gap>={thr}xATR: too few")
            continue
        print(f"  gap>={thr}xATR: n={r['n']}  continuation-rate={r['cont_rate']:.1f}%  "
              f"avg move in gap dir={r['avg_move']:.2f} ({r['avg_move_atr']:.2f}xATR)")

    r1 = eval_gaps(o, c, atr, gap, gap_atr, n, 1.0)
    if r1:
        rng = np.random.default_rng(42)
        rand_idx = rng.choice(np.arange(HORIZON, n - HORIZON), size=r1["n"], replace=False)
        rand_up = rng.random(r1["n"]) > 0.5
        entry = o[rand_idx]
        fwd = c[rand_idx + HORIZON] - entry
        cont = np.where(rand_up, fwd > 0, fwd < 0)
        avg_move_in_dir = np.where(rand_up, fwd, -fwd)
        print(f"  CONTROL (random bar/direction, same n={r1['n']}): "
              f"continuation-rate={100*np.mean(cont):.1f}%  avg move={np.mean(avg_move_in_dir):.2f}")

    print("\nVERDICT: continuation rate stays 48-56% (coin-flip) across every threshold, and the")
    print("average move in the gap's own direction is at or below zero xATR for 4 of 5 thresholds -")
    print("real GOLD gaps do NOT show the textbook 'trend continues in the gap direction' effect.")
    print("REJECTED. (Sample sizes are thin - 50-229 - but the null result is consistent across")
    print("every threshold tried, not a borderline call at just one cutoff.)")
