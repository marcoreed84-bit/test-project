"""
User's ask: is the trendline breakout construction M5, and has a
higher timeframe been tried. It's M5 (same dataset as everything else
this session). Given Meridian's own real experience - a naive M15 port
of an M5-tuned construction failed badly (floatDD 44% vs M5's 11%) and
never matched M5 even after a real tuning pass - this does NOT assume
the M5-optimal k=100 fractal window scales by simply dividing by 3.
Instead it sweeps the fractal window FRESH on M15's own bar structure,
same rigor used to find k=100 on M5 in the first place.

M15 built via engine.resample_m15_from_m5() (lossless, exact 3-bar
aggregation). VWAP/ATR/S-R distance recomputed on M15 bars directly,
matching meridian_m15_test.py's established pattern for this project.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered
from meridian_dd_confluence_test import drawdown_stats
from meridian_m15_test import build_sr_distance

POINT = E.POINT
N_RANDOM_SEEDS = 300
MIN_SR = 0.50


def run(close, high, low, atr, spread, vwap, sr_dist_buy, sr_dist_sell, n, fractal_k, safety_sl):
    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=fractal_k)
    events = build_breakout_events(close, desc_line, asc_line, n)
    if not events:
        return None

    cond_vwap = close > vwap
    ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    trades, skipped = sim_trendline_filtered(events, ok, close, high, low, spread, atr, n, safety_sl)
    if not trades:
        return dict(n=0)
    pnls = np.array([t[2] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    return dict(n=len(trades), net=net, pf=pf, win=100 * (pnls > 0).mean(),
                closed_dd=closed_dd, float_dd=float_dd, n_events=len(events))


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    df15 = E.resample_m15_from_m5(df5)
    n = len(df15)
    close = df15["close"].values.astype(float)
    high = df15["high"].values.astype(float)
    low = df15["low"].values.astype(float)
    spread = df15["spread"].values.astype(float)
    print(f"M15 (resampled from real M5): n={n} bars (~{n/96:.0f} trading days)\n")

    atr = E.wilder_atr(high, low, close, 14)
    vwap = E.session_vwap(df15)
    sr_hi, sr_lo = build_sr_distance(df15, h4)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - close) / atr
        sr_dist_sell = np.abs(close - sr_lo) / atr

    print("for reference, M5 (k=100, sl=4.0xATR, +VWAP+S/R): net=2989.87 pf=1.570 "
          "floatDD%=15.4 99.7th pct\n")

    print("=" * 70)
    print("sweeping fractal window fresh on M15 (33 M15 bars ~= 100 M5 bars in wall-clock time, "
          "but NOT assumed to be optimal - swept broadly):")
    results = []
    for k in (15, 25, 33, 45, 60, 80):
        for sl in (2.0, 3.0, 4.0):
            r = run(close, high, low, atr, spread, vwap, sr_dist_buy, sr_dist_sell, n, k, sl)
            if not r or r["n"] == 0:
                continue
            results.append((k, sl, r))
            print(f"  k={k:3d} sl={sl}xATR: n={r['n']:4d} ({r['n_events']} raw events) "
                  f"net={r['net']:9.2f} pf={r['pf']:.3f} win%={r['win']:.1f} "
                  f"floatDD%={100*r['float_dd']/r['net']:.1f}" if r['net']>0 else
                  f"  k={k:3d} sl={sl}xATR: n={r['n']:4d} net={r['net']:9.2f} (<=0)")

    print("\n" + "=" * 70)
    valid = [(k, sl, r) for k, sl, r in results if r["net"] > 0]
    if valid:
        best_k, best_sl, best_r = max(valid, key=lambda x: x[2]["net"])
        print(f"BEST M15: k={best_k} sl={best_sl}xATR net={best_r['net']:.2f} pf={best_r['pf']:.3f} "
              f"floatDD%={100*best_r['float_dd']/best_r['net']:.1f} n={best_r['n']}")
    else:
        print("no positive-net M15 config found in this sweep")
