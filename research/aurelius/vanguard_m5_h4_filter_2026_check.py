"""
Does the H4 trend-alignment filter that just passed on genuinely untouched
pre-2022-07 data (vanguard_m5_h4_trend_filter_oos_test.py: p=0.0000, survives
a lookahead-bug fix) also hold up on Vanguard's OWN 2026 tuning window, or
does it only work on old data while hurting the regime the EA is actually
running in right now? Same filter, same methodology, applied to the 2026
slice vanguard_m5_2026_random_timing_check.py already used.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
import vanguard_random_timing_test as V

START = "2026-01-01"
H4_EMA_PERIOD = 50


def ema(x, period):
    return pd.Series(x).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


if __name__ == "__main__":
    m5_full = E.load_m5_extended()
    h4_full = E.load_h4()
    m5 = m5_full[m5_full["time"] >= START].reset_index(drop=True)
    h4 = h4_full[h4_full["time"] >= pd.Timestamp(START) - pd.Timedelta(days=30)].reset_index(drop=True)
    print(f"2026 slice: n={len(m5)} M5 bars, {m5['time'].min()} -> {m5['time'].max()}")

    ctx = E.build_context(m5, h4, E.P)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]

    h4_ema = ema(h4["close"].values, H4_EMA_PERIOD)
    h4_trend_up = h4["close"].values > h4_ema
    h4_time = h4["time"].values
    m5_time = m5["time"].values
    # CORRECTED 2026-10-04 (Opus-audit finding) - see vanguard_m5_h4_trend_filter_oos_test.py's header
    h4_idx_for_m5 = np.searchsorted(h4_time, m5_time + np.timedelta64(5, "m"), side="right") - 2
    h4_idx_for_m5 = np.clip(h4_idx_for_m5, 0, len(h4) - 1)
    m5_h4_trend_up = h4_trend_up[h4_idx_for_m5]
    valid_h4 = h4_idx_for_m5 >= 1

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=V.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap

    entry_ok_base = np.zeros(n, dtype=bool)
    entry_ok_h4 = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        if sr >= 0.0 and sr < V.MIN_SR:
            continue
        entry_ok_base[i] = True
        h4_ok = m5_h4_trend_up[i] if d > 0 else (not m5_h4_trend_up[i])
        if valid_h4[i] and h4_ok:
            entry_ok_h4[i] = True

    for label, entry_ok in (("BASELINE (no H4 filter)", entry_ok_base),
                             ("+ H4 trend-alignment filter", entry_ok_h4)):
        real_trades = V.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                                  V.SAFETY_SL_ATR, stale_bars=V.STALE_BARS,
                                  stale_min_profit_atr=V.STALE_MIN_PROFIT_ATR)
        real_pf = V.pct_pf(real_trades)
        pnls = np.array([t[2] for t in real_trades])
        print(f"\n{label}: n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  %PF={real_pf:.3f}  net(price-pts)={pnls.sum():.1f}")
