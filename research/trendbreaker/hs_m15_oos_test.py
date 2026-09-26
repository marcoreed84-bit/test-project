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

CORRECTION (2026-09-26, later the same day - flagged as a bug fix, same
way the Ratchet/Ichimoku fixes were): two real problems in the result below.
  (a) DATA: load_m15_native() is NOT M15 before 2014-06-13 01:30 - it is one
      bar per DAY 2001-06 -> 2013-05, then HOURLY bars to 2014-06-13 (see
      pattern_rigor_common.py). The "~21 years" slice was really ~8.1 years
      of genuine M15 plus ~3,100 daily and ~4,000 hourly bars; the ~42 trades
      taken on those coarse bars carry huge %-moves and alone lifted %PF
      from 1.490 to 1.717.
  (b) LOOKAHEAD: find_breakouts_full() counted neckline closes before the
      right shoulder was knowable and used the final zigzag - fixed in
      hs_next_round_test.py (causal, EA-faithful detection is now the
      default; see hs_causal_detection_check.py).
  This file now runs on the real-M15 slice only (2014-06-13 -> 2022-07-03)
  with the fixed detector. CORRECTED RESULT: n=798, %PF=1.442 vs random-
  timing median 1.088 -> 99.9th percentile (p=0.001). Best-of-K: K=27 (H&S's
  own floor) p=0.030 SURVIVES, K=50 p=0.064 borderline, K=100 p=0.124 fails.
  Still genuine out-of-sample confirmation and H&S stays KEEP - but it is
  ~8 years of OOS at %PF ~1.44, not "21 years at 1.717 / 100th percentile".

ORIGINAL (superseded) RESULT (2026-09-26): %PF=1.717 (n=855) vs a random-timing median of 1.093
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
REAL_M15_START = "2014-06-13 01:30"   # first genuine M15 bar in load_m15_native()

if __name__ == "__main__":
    m15_full = E.load_m15_native()
    # real M15 bars only - see CORRECTION (a) in the docstring
    m15 = m15_full[(m15_full["time"] >= REAL_M15_START) & (m15_full["time"] < CUTOFF)].reset_index(drop=True)
    print(f"OOS slice: n={len(m15)} bars, {m15['time'].min()} -> {m15['time'].max()} "
          f"({(m15['time'].max()-m15['time'].min()).days/365.25:.1f} yrs) - genuinely untouched by any tuning")

    breakouts, h, l, c, atr = find_breakouts_full(m15, break_tol=0.35)
    n = len(c)
    real, missed = H.eval_pullback_and_runner_pct(breakouts, h, l, c, STOP_BUFFER,
                                                    H.RETEST_TOL, H.RETEST_WINDOW, H.TRAIL_MULT)
    real_arr = np.array([r["pnl_pct"] for r in real])
    real_pf = H.pct_pf(real)
    print(f"\nREAL H&S stacked combo (frozen v1.08) on untouched real M15 (2014-06 -> 2022-07):")
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
