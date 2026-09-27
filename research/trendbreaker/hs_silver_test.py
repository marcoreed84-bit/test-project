"""
Does H&S's frozen v1.08 stacked combo (the strongest-evidenced system in
this project, gold-only until now) transfer to SILVER with the SAME
parameters, unchanged? User asked whether any confirmed-working EA
generalizes to a different instrument - this is a real test, not a guess.

Data: user's 2026-09-27 SILVER M15 export. Same contamination pattern
already found in gold's data: daily bars before 2013-05, hourly until
2014-06-12, real M15 only from 2014-06-12 onward (trimmed before loading -
see SILVER_M15_native.csv). SILVER was NEVER touched by ANY parameter
search this project has ever run - the entire trimmed dataset (2014-06-12
-> 2026-09-25, ~12.3yrs) is genuinely out-of-sample, same status gold's
own pre-2022-07 OOS slice has, just with zero in-sample portion at all
for silver.

METHOD: identical to hs_m15_oos_test.py - find_breakouts_full(break_tol=
0.35) (now causal/EA-faithful by default), eval_pullback_and_runner_pct,
random-timing baseline, best-of-K bootstrap. No parameter changes -
testing raw transferability of the frozen construction, not a
silver-tuned version.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
from hs_next_round_test import find_breakouts_full, eval_pullback_and_runner, STOP_BUFFER
import hs_stacked_random_baseline_test as H

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"


def load_m15_silver():
    df = pd.read_csv(f"{DATA_DIR}/SILVER_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True)


if __name__ == "__main__":
    m15 = load_m15_silver()
    print(f"SILVER M15: n={len(m15)} bars, {m15['time'].min()} -> {m15['time'].max()} "
          f"({(m15['time'].max()-m15['time'].min()).days/365.25:.1f} yrs) - "
          f"never touched by any parameter search")

    breakouts, h, l, c, atr = find_breakouts_full(m15, break_tol=0.35)
    n = len(c)
    real, missed = H.eval_pullback_and_runner_pct(breakouts, h, l, c, STOP_BUFFER,
                                                    H.RETEST_TOL, H.RETEST_WINDOW, H.TRAIL_MULT)
    real_arr = np.array([r["pnl_pct"] for r in real])
    real_pf = H.pct_pf(real)
    print(f"\nREAL H&S stacked combo (frozen v1.08, UNCHANGED params) on SILVER M15:")
    print(f"  n={len(real)} (missed {missed})  win%={100*(real_arr>0).mean():.1f}  %PF={real_pf:.3f}")

    rng = np.random.default_rng(42)
    pool = H.random_timing_baseline(real, h, l, c, n, rng, n_runs=1500)
    pool = pool[~np.isnan(pool)]
    p_val = (pool >= real_pf).mean()
    pctile = 100 * (pool < real_pf).mean()
    print(f"  random-timing median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    print(f"\n  REAL sits at {pctile:.1f}th percentile of SILVER random-timing runs "
          f"(one-sided p={p_val:.4f})")

    print("\nMultiple-testing correction (best-of-K; K=27 is H&S's own estimated floor,")
    print("same as used on gold - this is testing raw transfer, not a silver-specific search):")
    rng2 = np.random.default_rng(7)
    for K in (1, 27, 50, 100):
        best = pool[rng2.integers(0, len(pool), size=(2000, K))].max(axis=1)
        p_k = (best >= real_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p={p_k:.4f}  [{verdict}]")
