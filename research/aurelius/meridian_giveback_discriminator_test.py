"""
Follow-up to meridian_giveback_exit_test.py. That test showed cutting
EVERY trade that gives back to near-breakeven loses money overall
(-$2037 on the real 887-trade group) because 41.1% of them go on to
recover to a real win (avg $23.21) and 58.9% go on to a real loss (avg
-$7.02) - big enough asymmetry that blanket-cutting removes more from the
winners than it saves from the losers, and there's no way to tell the two
groups apart AT the giveback moment with a blanket rule.

User's actual ask: can something ABOUT the pullback itself (how big the
peak was before it happened, how fast it happened, how far past breakeven
it went) distinguish the 41% that recover from the 59% that don't? If
yes, a rule that only cuts the discriminated losers could beat holding
everything. Tests three real, cheap-to-compute features on the SAME 887
real giveback trades, bucketed, real win%/avg-pnl per bucket:
  1. peak size before the giveback (bigger peak = more "real" move first?)
  2. speed of the giveback (bars from peak to near-breakeven - fast snap-
     back vs slow bleed)
  3. how far past breakeven it went (still slightly positive vs already
     negative at the giveback bar)
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "../meridian")
import numpy as np
import msim
from meridian_giveback_exit_test import analyze, MIN_PEAK, GIVEBACK_THRESH

np.random.seed(42)


def bucket_report(items, key_fn, edges, label):
    print(f"\n  --- {label} ---")
    for lo, hi in zip(edges[:-1], edges[1:]):
        sub = [it for it in items if lo <= key_fn(it) < hi]
        if len(sub) < 20:
            print(f"    [{lo:.2f}, {hi:.2f}): n={len(sub)} - too few"); continue
        pnl = np.array([it["real_pnl"] for it in sub])
        win_pct = 100 * (pnl > 0).mean()
        print(f"    [{lo:>7.2f}, {hi:>7.2f}): n={len(sub):>4}  win%={win_pct:5.1f}  "
              f"avg_pnl=${pnl.mean():6.2f}  net=${pnl.sum():8.2f}")


if __name__ == "__main__":
    mctx = msim.build_ctx()
    win_start = mctx["t64"].min(); win_end = mctx["t64"].max()
    trades, _ = msim.simulate(mctx, start=win_start, end=win_end)
    h, l, c = mctx["h"], mctx["l"], mctx["c"]

    tagged = analyze(trades, h, l, c)
    gave_back = [t for t in tagged if t["peak"] >= MIN_PEAK and t["giveback_bar"] is not None]
    print(f"n giveback trades: {len(gave_back)}  (overall win%={100*np.mean([t['real_pnl']>0 for t in gave_back]):.1f})")

    for t in gave_back:
        t["speed_bars"] = t["giveback_bar"] - t["peak_bar"]
        t["speed_hours"] = t["speed_bars"] * 5 / 60.0

    bucket_report(gave_back, lambda t: t["peak"],
                  [MIN_PEAK, 7.0, 10.0, 15.0, 200.0],
                  "bucketed by PEAK SIZE before the giveback ($)")

    speeds = np.array([t["speed_hours"] for t in gave_back])
    print(f"\n  speed distribution: min={speeds.min():.2f}h p25={np.percentile(speeds,25):.2f}h "
          f"median={np.median(speeds):.2f}h p75={np.percentile(speeds,75):.2f}h max={speeds.max():.2f}h")
    bucket_report(gave_back, lambda t: t["speed_hours"],
                  [0.0, 0.1, 0.3, 1.0, 100.0],
                  "bucketed by SPEED of giveback (hours from peak to near-breakeven)")

