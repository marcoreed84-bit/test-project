"""
M15 companion to vanguard_m5_joint_sweep_test.py - independent joint
sl x stale_bars sweep on M15's own construction (k=33), NOT assumed to
land on the same conclusion as M5 (M5's joint sweep found stacking a
tighter stop added nothing beyond stale-exit alone - checking that
holds, or doesn't, on M15 separately, per explicit instruction: each
timeframe gets whatever combination actually works for it).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from meridian_m15_test import build_sr_distance
from meridian_dd_confluence_test import drawdown_stats
from vanguard_m5_joint_sweep_test import sim_full, report

FRACTAL_K = 33
MIN_SR = 0.50

if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    df15 = E.resample_m15_from_m5(df5)
    n = len(df15)
    close = df15["close"].values.astype(float)
    high = df15["high"].values.astype(float)
    low = df15["low"].values.astype(float)
    spread = df15["spread"].values.astype(float)

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

    shipped = sim_full(events, entry_ok, close, high, low, spread, atr, n, 3.0)
    shipped_top20 = set(t[0] for t in sorted(shipped, key=lambda t: -t[2])[:20])
    print("SHIPPED M15 (sl=3.0, no stale-exit):")
    report("shipped baseline", shipped, close, spread, atr, n, shipped_top20)

    print("\nJOINT sweep (sl x stale_bars) on M15's own construction:")
    for sl in (2.5, 3.0, 3.5, 4.0):
        for sb in (50, 75, 100, 125, 150, None):
            trades = sim_full(events, entry_ok, close, high, low, spread, atr, n, sl, stale_bars=sb)
            if not trades: continue
            report(f"sl={sl} stale={sb}", trades, close, spread, atr, n, shipped_top20)
