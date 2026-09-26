"""
Same random-timing baseline + multiple-testing correction as
vanguard_random_timing_test.py (M5), applied to Vanguard_M15_EA.mq5's real
shipped construction (FRACTAL_K=33, SafetyStopATR=3.0, MinSRDistATR=0.50,
StaleBars=75 - independently landed on ~18.75h same as M5's 225 M5-bars,
per that file's own header note) - reuses vanguard_m15_joint_sweep_test.py's
own construction (sim_full from the M5 joint-sweep file, build_sr_distance
from meridian_m15_test.py) rather than re-deriving it.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from meridian_m15_test import build_sr_distance
import vanguard_random_timing_test as V
sim_full = V.sim_full   # the 5-tuple (..., entry) version, needed for %PF normalization

FRACTAL_K = 33
MIN_SR = 0.50
SAFETY_SL_ATR = 3.0
STALE_BARS = 75
STALE_MIN_PROFIT_ATR = 0.0
N_RANDOM = 300


def sim_random_entry_m15(real_events, close, high, low, spread, atr, n, rng, p_fire):
    return V.sim_random_entry(real_events, close, high, low, spread, atr, n, rng, p_fire,
                               SAFETY_SL_ATR, STALE_BARS, STALE_MIN_PROFIT_ATR)


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    df15 = E.resample_m15_from_m5(df5)
    n = len(df15)
    close = df15["close"].values.astype(float)
    high = df15["high"].values.astype(float)
    low = df15["low"].values.astype(float)
    spread = df15["spread"].values.astype(float)
    print(f"M15 data: n={n} bars, {df15['time'].min()} -> {df15['time'].max()}\n")

    atr = E.wilder_atr(high, low, close, 14)
    vwap = E.session_vwap(df15)
    sr_hi, sr_lo = build_sr_distance(df15, h4)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - close) / atr
        sr_dist_sell = np.abs(close - sr_lo) / atr

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    real_trades = sim_full(events, entry_ok, close, high, low, spread, atr, n,
                            SAFETY_SL_ATR, stale_bars=STALE_BARS, stale_min_profit_atr=STALE_MIN_PROFIT_ATR)
    real_pct_pf = V.pct_pf(real_trades)
    pnls = np.array([t[2] for t in real_trades])
    print(f"REAL Vanguard M15 shipped defaults: n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  "
          f"net={pnls.sum():.2f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = V.calibrate_p_fire(events, close, high, low, spread, atr, n, rng, len(real_trades))
    print(f"\nCalibrated p_fire={p_fire:.6f}")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines...")
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(N_RANDOM):
        tr = sim_random_entry_m15(events, close, high, low, spread, atr, n, rng, p_fire)
        pool.append(V.pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.3f})")

    print("\nMultiple-testing correction (best-of-K):")
    rng2 = np.random.default_rng(7)
    for K in (1, 24, 50, 100):
        best = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (best >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p95={np.percentile(best,95):.3f}  "
              f"p={p_k:.3f}  [{verdict}]")
