"""
REAL out-of-sample confirmation for H&S's stacked combo, made possible by
the user's 2026-09-26 native M15 upload (GOLD_PERIOD_M15.csv, 2001-2026) -
see research/aurelius/vanguard_m15_oos_test.py's own docstring for the
full story of why this data is genuinely different from
resample_m15_from_m5(load_m5()) (2022-onward only) used to originally
validate H&S.

METHOD: run H&S's FROZEN, real shipped v1.08 stacked combo (break_tol=
0.35, pullback/retest entry, runner - unchanged from
hs_stacked_random_baseline_test.py) on ONLY the pre-2022-07-04 slice of
the real M15 data (~199,836 bars, ~21 years) - genuinely never touched by
H&S's own construction/tuning, which was entirely developed on 2022-2026
data. Then the same random-timing baseline, computed on that same
untouched slice.

RESULT (2026-09-26): %PF=1.717 (n=855) vs a random-timing median of 1.093
on this same untouched slice - sits at the 100th percentile (p=0.0000).
Real, independent, out-of-sample confirmation of H&S's edge on data
entirely separate from the window it was built and validated on -
the single strongest piece of evidence in this whole project for any
system, since every other "survives" result (Aurelius, Meridian, Ratchet)
is still an in-sample multiple-testing argument, not genuine unseen data.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from hs_next_round_test import find_breakouts_full, eval_pullback_and_runner, STOP_BUFFER
import hs_stacked_random_baseline_test as H

CUTOFF = "2022-07-04"

if __name__ == "__main__":
    m15_full = E.load_m15_native()
    m15 = m15_full[m15_full["time"] < CUTOFF].reset_index(drop=True)
    print(f"OOS slice: n={len(m15)} bars, {m15['time'].min()} -> {m15['time'].max()} "
          f"({(m15['time'].max()-m15['time'].min()).days/365.25:.1f} yrs) - genuinely untouched by any tuning")

    breakouts, h, l, c, atr = find_breakouts_full(m15, break_tol=0.35)
    n = len(c)
    real, missed = H.eval_pullback_and_runner_pct(breakouts, h, l, c, STOP_BUFFER,
                                                    H.RETEST_TOL, H.RETEST_WINDOW, H.TRAIL_MULT)
    real_arr = np.array([r["pnl_pct"] for r in real])
    real_pf = H.pct_pf(real)
    print(f"\nREAL H&S stacked combo (frozen v1.08) on untouched 2001-2022 M15:")
    print(f"  n={len(real)} (missed {missed})  win%={100*(real_arr>0).mean():.1f}  %PF={real_pf:.3f}")

    rng = np.random.default_rng(42)
    pool = H.random_timing_baseline(real, h, l, c, n, rng, n_runs=1500)
    pool = pool[~np.isnan(pool)]
    p_val = (pool >= real_pf).mean()
    pctile = 100 * (pool < real_pf).mean()
    print(f"  random-timing median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    print(f"\n  REAL sits at {pctile:.1f}th percentile of genuinely untouched-data random-timing runs "
          f"(one-sided p={p_val:.4f})")
    if p_val < 0.05:
        print("  -> SURVIVES on genuinely untouched historical data - the strongest evidence")
        print("     in this whole project for any system.")
