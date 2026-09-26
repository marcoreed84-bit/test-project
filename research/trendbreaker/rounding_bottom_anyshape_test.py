"""
Same "does the specific shape add selectivity" control that got Wolfe Wave
rejected, applied to RoundingBottom_EA's real construction (v1.03: window=
60, stride=5, rim-anchored stop, H4, buy-only). find_rounding() requires
THREE shape-quality conditions before a window counts as a real "rounding
bottom" candidate: (1) R2_MIN=0.50 quadratic fit quality, (2) correct
curvature sign (a>0 - genuinely U-shaped, not a straight decline), (3) the
window's own low sits roughly CENTERED (CENTER_TOL=0.25, i.e. within the
middle 50% of the window), not at either edge (which would just be a trend,
not a rounding shape).

This test drops all three and treats EVERY 60-bar/stride-5 window as a
"candidate" - same rim (window's own start price) and same extreme_px
(window's own lowest close), same breakout/stop/target mechanism, just with
no requirement that the window actually LOOK like a rounding bottom at all.
Windows are accepted greedily in chronological order, non-overlapping (the
same de-duplication PURPOSE as find_rounding()'s NMS-by-R2, just with no
quality score to rank by since there isn't one here).

If this "any window" control performs as well as the real, shape-filtered
version, the quadratic-fit/curvature/centering requirements aren't adding
real selectivity - same conclusion Wolfe Wave's analogous control reached.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD
from hs_next_round_test import report
from rounding_cup_handle_test import find_rounding
import rounding_bottom_random_baseline_test as RB

np.random.seed(42)
STRIDE = 5


def find_any_window(c, n, window):
    """Every window/stride slot, greedily de-duplicated in chronological
    order (no quality score to rank by, unlike find_rounding()'s R2)."""
    out = []
    last_end = -1
    for end in range(window, n, STRIDE):
        start = end - window
        if start <= last_end:
            continue
        seg = c[start:end + 1]
        out.append(dict(start=start, end=end, extreme_px=seg.min(), rim=seg[0]))
        last_end = end
    return out


if __name__ == "__main__":
    h4 = E.load_h4()
    o = h4["open"].values; h = h4["high"].values; l = h4["low"].values; c = h4["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    print(f"H4 data: n={n} bars, {h4['time'].min()} -> {h4['time'].max()}\n")

    real_cands = find_rounding(c, atr, n, RB.WINDOW, top=False)
    real_trades = RB.build_real_trades(real_cands, h, l, c, atr, n)
    real = RB.eval_book(real_trades, h, l, c)
    real_pct_pf = RB.pct_pf(real)
    report(real, f"REAL shape-filtered RoundingBottom ({len(real_cands)} candidates)")
    print(f"  %%PF={real_pct_pf:.3f}  n={len(real)}\n")

    any_cands = find_any_window(c, n, RB.WINDOW)
    any_trades = RB.build_real_trades(any_cands, h, l, c, atr, n)
    any_res = RB.eval_book(any_trades, h, l, c)
    any_pct_pf = RB.pct_pf(any_res)
    report(any_res, f"ANY-window control, no shape filter ({len(any_cands)} candidates)")
    print(f"  %%PF={any_pct_pf:.3f}  n={len(any_res)}\n")

    print("=" * 90)
    print(f"Real shape-filtered:  n={len(real)}   %PF={real_pct_pf:.3f}")
    print(f"Any-window control:   n={len(any_res)}   %PF={any_pct_pf:.3f}")
    if any_pct_pf >= real_pct_pf * 0.9:
        print("-> ANY-window control performs comparably (or better) - the quadratic-fit/curvature/")
        print("   centering shape filters are NOT adding real selectivity over a generic 60-bar dip-buy.")
    else:
        print("-> The shape filters clearly help - real result meaningfully beats the unconstrained control.")

    print("\nRunning the random-timing baseline against the ANY-window control too, for a full comparison...")
    rng = np.random.default_rng(42)
    rand_pfs = RB.random_timing_baseline(any_res, h, l, c, atr, n, rng, n_runs=1000)
    rand_pfs = rand_pfs[~np.isnan(rand_pfs)]
    pctile = 100 * (rand_pfs < any_pct_pf).mean()
    print(f"  ANY-window %%PF={any_pct_pf:.3f} sits at the {pctile:.1f}th percentile of its own "
          f"random-timing band (median={np.median(rand_pfs):.3f}, p95={np.percentile(rand_pfs,95):.3f})")
