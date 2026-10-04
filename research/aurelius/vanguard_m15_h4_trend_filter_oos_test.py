"""
Two things in one script:

1) A corrected re-run of vanguard_m15_oos_test.py's baseline. That script
   loads load_m15_native() and filters only by the upper CUTOFF
   (2022-07-04), with NO lower bound - but engine.py's own load_m15_native()
   docstring says this file has daily bars before 2013-05, then hourly
   bars until 2014-06-13, and genuine M15 only starts there (same
   contamination CLAUDE.md documents for GOLD_M15_native.csv). ~9,800 of
   the 199,836 rows the original script used (4.9%) predate that. The
   original result (n=1487, %PF=1.086, 50.7th pctile, p=0.49) was already
   decisively non-significant, so this is unlikely to flip the verdict,
   but it's being redone on the correctly-trimmed 2014-06-13->2022-07-04
   window before trusting it further or building on top of it.

2) The SAME H4 trend-alignment filter that fixed Vanguard M5
   (vanguard_m5_h4_trend_filter_oos_test.py) and partially fixed Meridian's
   entry, tested here on Vanguard M15 - does it transfer to the 15-minute
   version too, or is this specific to M5? Uses the corrected side="left"
   causal H4 alignment from the start (the M5 version's lookahead bug is
   not repeated here).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from meridian_m15_test import build_sr_distance
import vanguard_m15_random_timing_test as VM
import vanguard_random_timing_test as V

START = "2014-06-13 01:30:00"   # genuine M15 history begins here - engine.py's own load_m15_native() docstring
CUTOFF = "2022-07-04"
H4_EMA_PERIOD = 50


def ema(x, period):
    return pd.Series(x).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


if __name__ == "__main__":
    m15_full = E.load_m15_native()
    h4_full = E.load_h4()
    m15 = m15_full[(m15_full["time"] >= START) & (m15_full["time"] < CUTOFF)].reset_index(drop=True)
    h4 = h4_full[h4_full["time"] < CUTOFF].reset_index(drop=True)
    print(f"Corrected OOS slice: n={len(m15)} bars, {m15['time'].min()} -> {m15['time'].max()} "
          f"({(m15['time'].max()-m15['time'].min()).days/365.25:.1f} yrs) - genuine M15 only, "
          f"contamination trimmed per engine.py's load_m15_native() docstring")

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

    # H4 trend state, causal. CORRECTED (2026-10-04, same Opus-audit finding as the M5 version):
    # side="left"-1 still leaked the still-forming H4 bar for any M15 bar not exactly on an H4
    # boundary. side="right" on (time + one M15 bar) then -2 steps back to the bar actually closed.
    h4_ema = ema(h4["close"].values, H4_EMA_PERIOD)
    h4_trend_up = h4["close"].values > h4_ema
    h4_time = h4["time"].values
    m15_time = m15["time"].values
    h4_idx_for_m15 = np.searchsorted(h4_time, m15_time + np.timedelta64(15, "m"), side="right") - 2
    h4_idx_for_m15 = np.clip(h4_idx_for_m15, 0, len(h4) - 1)
    m15_h4_trend_up = h4_trend_up[h4_idx_for_m15]
    valid_h4 = h4_idx_for_m15 >= 1

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=VM.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap

    entry_ok_base = np.zeros(n, dtype=bool)
    entry_ok_h4 = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        if sr >= 0.0 and sr < VM.MIN_SR:
            continue
        entry_ok_base[i] = True
        h4_ok = m15_h4_trend_up[i] if d > 0 else (not m15_h4_trend_up[i])
        if valid_h4[i] and h4_ok:
            entry_ok_h4[i] = True

    for label, entry_ok in (("BASELINE (corrected window, no H4 filter)", entry_ok_base),
                             ("+ H4 trend-alignment filter", entry_ok_h4)):
        real_trades = VM.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                                   VM.SAFETY_SL_ATR, stale_bars=VM.STALE_BARS,
                                   stale_min_profit_atr=VM.STALE_MIN_PROFIT_ATR)
        real_pf = V.pct_pf(real_trades)
        pnls = np.array([t[2] for t in real_trades])
        print(f"\n{label}: n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  %PF={real_pf:.3f}")

        if len(real_trades) < 20:
            print("  too few trades to run a meaningful random-timing null")
            continue
        rng = np.random.default_rng(1)
        p_fire = V.calibrate_p_fire(events, close, high, low, spread, atr, n, rng, len(real_trades))
        rng = np.random.default_rng(42)
        pool = []
        for _ in range(600):
            tr = V.sim_random_entry(events, close, high, low, spread, atr, n, rng, p_fire,
                                     VM.SAFETY_SL_ATR, VM.STALE_BARS, VM.STALE_MIN_PROFIT_ATR)
            pool.append(V.pct_pf(tr))
        pool = np.array(pool)
        pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
        pctile = 100 * (pool < real_pf).mean()
        p_val = (pool >= real_pf).mean()
        print(f"  random-timing null: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
        print(f"  REAL %PF={real_pf:.3f} -> {pctile:.1f}th percentile, p={p_val:.4f}")
