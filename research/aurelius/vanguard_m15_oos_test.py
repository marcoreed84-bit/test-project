"""
REAL out-of-sample test for Vanguard M15, made possible by the user's
2026-09-26 upload of a native M15 export (GOLD_PERIOD_M15.csv) spanning
2001-2026 - genuinely different from resample_m15_from_m5(load_m5()) used
everywhere else in this repo, which was only as deep as the M5 export
(2022-07 onward). The 2001-2022 portion of this file (~199,836 bars, ~21
years) was NEVER touched by any M15 parameter search this session -
Vanguard M15's FractalK=33/SafetyStopATR=3.0/StaleBars=75/MinSR=0.50 grid
was entirely tuned on 2022-2026 data. This is the real thing the whole
"freeze it and wait for new data" conversation was working toward, except
it already exists in the past instead of needing months to accumulate.

METHOD: run Vanguard M15's FROZEN, ALREADY-SHIPPED construction (no
re-tuning - literally reusing vanguard_m15_random_timing_test.py's own
FRACTAL_K/MIN_SR/SAFETY_SL_ATR/STALE_BARS constants unchanged) on ONLY the
pre-2022-07-04 slice of this real data, then run the same random-timing
baseline on that SAME untouched slice. No multiple-testing correction
needed here in the usual sense - this data was never part of the 24-way
search, so a single-hypothesis comparison is already fair.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from meridian_m15_test import build_sr_distance
import vanguard_m15_random_timing_test as VM
import vanguard_random_timing_test as V

CUTOFF = "2022-07-04"   # start of the M5-derived data every other M15 test in this repo used


if __name__ == "__main__":
    m15_full = E.load_m15_native()
    h4 = E.load_h4()
    m15 = m15_full[m15_full["time"] < CUTOFF].reset_index(drop=True)
    print(f"OOS slice: n={len(m15)} bars, {m15['time'].min()} -> {m15['time'].max()} "
          f"({(m15['time'].max()-m15['time'].min()).days/365.25:.1f} yrs) - genuinely untouched by any tuning")

    close = m15["close"].values.astype(float)
    high = m15["high"].values.astype(float)
    low = m15["low"].values.astype(float)
    spread = m15["spread"].values.astype(float)
    n = len(m15)

    atr = E.wilder_atr(high, low, close, 14)
    vwap = E.session_vwap(m15)
    sr_hi, sr_lo = build_sr_distance(m15, h4)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - close) / atr
        sr_dist_sell = np.abs(close - sr_lo) / atr

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=VM.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < VM.MIN_SR)

    real_trades = VM.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                               VM.SAFETY_SL_ATR, stale_bars=VM.STALE_BARS,
                               stale_min_profit_atr=VM.STALE_MIN_PROFIT_ATR)
    real_pct_pf = V.pct_pf(real_trades)
    pnls = np.array([t[2] for t in real_trades])
    print(f"\nREAL Vanguard M15 (frozen settings) on genuinely untouched 2001-2022 data:")
    print(f"  n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  net={pnls.sum():.2f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = V.calibrate_p_fire(events, close, high, low, spread, atr, n, rng, len(real_trades))
    print(f"\nCalibrated p_fire={p_fire:.6f}")

    print(f"Running 600 random-entry/coin-flip-direction baselines on this SAME untouched slice...")
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(600):
        tr = V.sim_random_entry(events, close, high, low, spread, atr, n, rng, p_fire,
                                 VM.SAFETY_SL_ATR, VM.STALE_BARS, VM.STALE_MIN_PROFIT_ATR)
        pool.append(V.pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile of untouched-data "
          f"random-timing runs (one-sided p={p_val:.4f})")
    if p_val < 0.05:
        print("  -> SURVIVES on genuinely untouched historical data - real, out-of-sample evidence")
        print("     Vanguard M15's edge is real, not just a lucky pick from the 24-way search.")
    else:
        print("  -> Does not clear even a single-hypothesis bar on untouched data either -")
        print("     consistent with the earlier 'can't rule out luck' verdict, now with real OOS evidence.")
