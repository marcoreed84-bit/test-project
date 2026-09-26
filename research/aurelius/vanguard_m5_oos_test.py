"""
REAL out-of-sample test for Vanguard M5, same idea as
vanguard_m15_oos_test.py: the user's incremental M5-history uploads
(engine.load_m5_extended(), currently 2018.01.02 onward as of this file's
first run - more chunks land in research/aurelius/../m5_chunks/ over time
with no code change needed) give genuinely untouched M5 history. Vanguard
M5's FractalK=100/SafetyStopATR=4.0/StaleBars=225/MinSR=0.50 grid was
tuned entirely on 2022-2026 data - the pre-2022-07-04 slice was never
part of that search.

METHOD: run Vanguard M5's FROZEN, already-shipped construction (reusing
vanguard_m5_joint_sweep_test.py's own FRACTAL_K/MIN_SR and
vanguard_random_timing_test.py's SAFETY_SL_ATR/STALE_BARS constants,
unchanged) on ONLY the pre-2022-07-04 slice, then the same random-timing
baseline on that same untouched slice.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
import vanguard_random_timing_test as V

CUTOFF = "2022-07-04"

if __name__ == "__main__":
    m5_full = E.load_m5_extended()
    h4 = E.load_h4()
    m5 = m5_full[m5_full["time"] < CUTOFF].reset_index(drop=True)
    print(f"OOS slice: n={len(m5)} bars, {m5['time'].min()} -> {m5['time'].max()} "
          f"({(m5['time'].max()-m5['time'].min()).days/365.25:.1f} yrs) - genuinely untouched by any tuning")

    ctx = E.build_context(m5, h4, E.P)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=V.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < V.MIN_SR)

    real_trades = V.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                              V.SAFETY_SL_ATR, stale_bars=V.STALE_BARS,
                              stale_min_profit_atr=V.STALE_MIN_PROFIT_ATR)
    real_pct_pf = V.pct_pf(real_trades)
    pnls = np.array([t[2] for t in real_trades])
    print(f"\nREAL Vanguard M5 (frozen v1.06 settings) on genuinely untouched pre-2022-07 data:")
    print(f"  n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  net={pnls.sum():.2f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = V.calibrate_p_fire(events, close, high, low, spread, atr, n, rng, len(real_trades))
    print(f"\nCalibrated p_fire={p_fire:.6f}")

    print(f"Running 600 random-entry/coin-flip-direction baselines on this SAME untouched slice...")
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(600):
        tr = V.sim_random_entry(events, close, high, low, spread, atr, n, rng, p_fire,
                                 V.SAFETY_SL_ATR, V.STALE_BARS, V.STALE_MIN_PROFIT_ATR)
        pool.append(V.pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile of untouched-data "
          f"random-timing runs (one-sided p={p_val:.4f})")
