"""
Re-tries the trendline + effort-vs-result confluence idea with the base
population flipped (2026-09-25): the first attempt conditioned on the 27
real trendline touches (too few to split any further - n=3 with the
confluence signature, meaningless either direction). This conditions on
the 813 real EFFORT-FAILURE bars instead (effort_vs_result_test.py's own
already-validated population, real signal on H4: 42.1% reversal vs 37.4%
baseline) and asks whether being NEAR a validated trendline at the time
(the rarer condition here) elevates that reversal rate further - same
underlying idea, much better powered.

"Near a validated line" = within NEAR_ATR x ATR of ANY currently-VALID
line's own value at that bar (either direction, not just the matching
side - a nearby line of either polarity represents real structure the
market might respect).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import (
    sma_atr, find_swings, bos_ok, build_line,
    PIVOT_STRENGTH, ATR_PERIOD, TOUCHES_TO_VALIDATE, LOOKBACK_BARS,
)
from effort_vs_result_test import (
    classify_effort, VOL_AVG_BARS, RESULT_BARS, RESULT_MIN_ATR,
    REACT_BARS, REVERSAL_MIN_ATR,
)

np.random.seed(42)
NEAR_ATR = 1.0


def run(df, label):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    vol = df["tick_volume"].values.astype(float)
    atr = sma_atr(h, l, o, ATR_PERIOD)
    vavg = pd.Series(vol).rolling(VOL_AVG_BARS, min_periods=10).mean().values
    print(f"\n{label}: {df['time'].min()} -> {df['time'].max()}, n={n} bars")

    up, dn = classify_effort(o, h, l, c, vol, atr, vavg)

    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    lines = []
    for dir_, want in ((1, 1), (-1, -1)):
        anchors = [zIdx[m] for m in range(len(zIdx))
                   if zType[m] == want and bos_ok(m, zIdx, zType, zPx, o, h, l, c, n, False)]
        for ai in range(len(anchors)):
            for bi in range(ai + 1, len(anchors)):
                a, b = anchors[ai], anchors[bi]
                if b - a < PIVOT_STRENGTH or b - a > LOOKBACK_BARS:
                    continue
                L = build_line(o, h, l, c, atr, n, a, b, dir_, False)
                if L is not None and L["touches"] >= TOUCHES_TO_VALIDATE:
                    lines.append(L)
    print(f"  VALID lines: {len(lines)}")

    # precompute, for each bar, the min distance (in ATR) to any VALID line
    # that is "alive" at that bar (built by ib, not yet run off past ~ the
    # data end - keep simple: any line whose anchors cover it, i.e. ib <= bar,
    # projected forward with its own slope, no expiry - matches how a real
    # chart trendline just keeps projecting until visually removed)
    min_dist_atr = np.full(n, np.inf)
    for L in lines:
        ia, p1, slope = L["ia"], L["p1"], L["slope"]
        for q in range(L["ib"], n):
            if atr[q] <= 0 or np.isnan(atr[q]):
                continue
            lv = p1 + slope * (q - ia)
            d = abs(c[q] - lv) / atr[q]
            if d < min_dist_atr[q]:
                min_dist_atr[q] = d

    records = []
    for i in range(VOL_AVG_BARS, n - RESULT_BARS - REACT_BARS):
        for d, flag in ((1, up[i]), (-1, dn[i])):
            if not flag or np.isnan(atr[i]) or atr[i] <= 0:
                continue
            move = (c[i + RESULT_BARS] - c[i]) * d
            success = move >= RESULT_MIN_ATR * atr[i]
            if success:
                continue   # only FAILURE bars - the population that showed real signal
            reac_start = i + RESULT_BARS
            reac_end = min(n - 1, reac_start + REACT_BARS)
            net_after = (c[reac_end] - c[reac_start]) * d
            reversed_ = net_after <= -REVERSAL_MIN_ATR * atr[i]
            near = min_dist_atr[i] <= NEAR_ATR
            records.append(dict(reversed=reversed_, near=bool(near), i=i))

    n_ = len(records)
    print(f"  {n_} EFFORT-FAILURE bars total")
    near_r = [r for r in records if r["near"]]
    far_r = [r for r in records if not r["near"]]

    def report(subset, lbl):
        if len(subset) < 8:
            print(f"    {lbl}: only {len(subset)} - too few"); return None
        rev = sum(r["reversed"] for r in subset)
        rt = 100 * rev / len(subset)
        print(f"    {lbl}: n={len(subset)}  reversal rate={rt:.1f}%")
        return rt, len(subset)

    r_near = report(near_r, "NEAR a valid line (<=1.0 ATR)")
    r_far = report(far_r, "NOT near a valid line")

    if r_near and r_far and len(near_r) > 8 and len(far_r) > 8:
        from scipy import stats
        rn = sum(r["reversed"] for r in near_r)
        rf = sum(r["reversed"] for r in far_r)
        table = [[rn, len(near_r) - rn], [rf, len(far_r) - rf]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        print(f"\n  Fisher exact (NEAR reversal rate > FAR): odds={odds:.2f} p={p:.4f}")

        order = sorted(range(len(near_r)), key=lambda k: near_r[k]["i"])
        cutoff = int(len(near_r) * 0.7)
        print("\n  WALK-FORWARD on the NEAR group (chronological 70/30):")
        report([near_r[k] for k in order[:cutoff]], "  IN-SAMPLE")
        report([near_r[k] for k in order[cutoff:]], "  OUT-OF-SAMPLE")


if __name__ == "__main__":
    h4 = E.load_h4()
    run(h4, "H4 (real GOLD# export)")
