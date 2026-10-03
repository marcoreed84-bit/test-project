"""
Does Aurelius M5 beat random timing on 2026 specifically - the SAME
check, same methodology, same calendar window, that Vanguard was just run
through and failed (Vanguard: real %PF=1.751 vs random median=1.147,
p=0.043, barely above the random band and not surviving multiple-testing
correction). This test deliberately does NOT use the pre-2022 blind data -
answers the question using only the current/recent regime, like-for-like
with Vanguard's result.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from engine import P
import aurelius_random_timing_test as A

START = "2026-01-01"

if __name__ == "__main__":
    m5_full = E.load_m5_extended()
    h4 = E.load_h4()
    df = m5_full[m5_full["time"] >= START].reset_index(drop=True)
    print(f"2026 slice: n={len(df)} bars, {df['time'].min()} -> {df['time'].max()}")
    ctx = E.build_context(df, h4, P)

    real_trades = A.simulate(ctx)
    real_stats = A.stats(real_trades)
    real_pf = A.pct_pf(real_trades)
    print(f"REAL Aurelius M5 on 2026: n={real_stats['n']}  win%={100*real_stats['win_rate']:.1f}  %PF={real_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = A.calibrate_p_fire(ctx, P, rng, real_stats["n"])
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(600):
        tr = A.simulate_random_entry(ctx, P, rng, p_fire)
        pool.append(A.pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    pctile = 100 * (pool < real_pf).mean()
    p_val = (pool >= real_pf).mean()
    print(f"random-entry (same exits, SAME 2026 window) %PF: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    print(f"REAL %PF={real_pf:.3f} -> {pctile:.1f}th percentile, p={p_val:.4f}")
