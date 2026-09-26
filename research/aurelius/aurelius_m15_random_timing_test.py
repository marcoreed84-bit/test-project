"""
Same random-timing baseline + multiple-testing correction as
aurelius_random_timing_test.py (M5), applied to the M15 variant
(engine.py's P15 params, Aurelius_M15_EA.mq5 v1.56's real shipped
defaults - different pullback MA, stricter S/R distance, an extra
slope x S/R block filter not in the M5 file). Reuses simulate_random_entry
generically (it already takes params as an argument) - no new simulator
needed, just a different params dict and M15 data (resampled 1:1 from
real M5, GOLD has no native M15 export).

User's own observation, confirmed here: Aurelius M15's real MT5 track
record (2026-onward) already looked better than M5 (PF 2.324 vs 1.937).
This checks whether that holds up as a genuine, specific edge or is just
GOLD's drift again.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from sim import simulate
import aurelius_random_timing_test as A

N_RANDOM = 600

if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    df15 = E.resample_m15_from_m5(df5)
    print(f"M15 data: n={len(df15)} bars, {df15['time'].min()} -> {df15['time'].max()}\n")
    ctx15 = E.build_context(df15, h4, E.P15)
    n = ctx15["n"]

    real_trades = simulate(ctx15, params=E.P15)
    real_pct_pf = A.pct_pf(real_trades)
    print(f"REAL Aurelius M15 v1.56 defaults: n={len(real_trades)}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = A.calibrate_p_fire(ctx15, E.P15, rng, len(real_trades))
    print(f"\nCalibrated p_fire={p_fire:.5f}")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines...")
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(N_RANDOM):
        tr = A.simulate_random_entry(ctx15, E.P15, rng, p_fire)
        pool.append(A.pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.3f})")

    print("\nMultiple-testing correction (best-of-K):")
    rng2 = np.random.default_rng(7)
    for K in (1, 30, 50, 100):
        best = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (best >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p95={np.percentile(best,95):.3f}  "
              f"p={p_k:.3f}  [{verdict}]")
