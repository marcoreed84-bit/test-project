"""
Bar-match: does the Python simulator (+H4 filter) match the REAL MT5
backtest of Vanguard_EA.mq5 v1.07 the user just ran (2026.01.01-2026.09.25,
InpUseH4TrendFilter=true, InpH4EMAPeriod=50, 65 real trades, PF=1.674729,
net 9917.95)? Per CLAUDE.md: a simulator that hasn't been checked against
real fills is a hypothesis, not a verdict - this is that check for the
freshly-added H4 filter specifically (never bar-matched before, since it
never existed in the EA before today).
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
    print(f"2026 slice: n={len(m5)} bars, {m5['time'].min()} -> {m5['time'].max()}")

    ctx = E.build_context(m5, h4_full, E.P)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]

    h4_ema = ema(h4_full["close"].values, H4_EMA_PERIOD)
    h4_trend_up = h4_full["close"].values > h4_ema
    h4_time = h4_full["time"].values
    m5_time = m5["time"].values
    h4_idx_for_m5 = np.searchsorted(h4_time, m5_time, side="left") - 1
    h4_idx_for_m5 = np.clip(h4_idx_for_m5, 0, len(h4_full) - 1)
    m5_h4_trend_up = h4_trend_up[h4_idx_for_m5]
    valid_h4 = h4_idx_for_m5 >= 1

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=V.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        if sr >= 0.0 and sr < V.MIN_SR:
            continue
        h4_ok = m5_h4_trend_up[i] if d > 0 else (not m5_h4_trend_up[i])
        if valid_h4[i] and h4_ok:
            entry_ok[i] = True

    trades = V.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                         V.SAFETY_SL_ATR, stale_bars=V.STALE_BARS,
                         stale_min_profit_atr=V.STALE_MIN_PROFIT_ATR)
    pnls = np.array([t[2] for t in trades])
    real_pf = V.pct_pf(trades)
    print(f"PYTHON: n={len(trades)}  win%={100*(pnls>0).mean():.1f}  %PF={real_pf:.3f}  net(price-pts)={pnls.sum():.1f}")

    rows = []
    for (i, exit_i, pnl, is_buy, entry) in trades:
        rows.append(dict(sig_time=m5["time"].iloc[i], fill_time=m5["time"].iloc[min(i+1, n-1)],
                          dir="buy" if is_buy else "sell", entry=round(entry, 2), pnl=round(pnl, 2)))
    py_df = pd.DataFrame(rows)
    py_df.to_csv("/tmp/vanguard_m5_python_trades_2026.csv", index=False)
    print(f"\nFirst 10 Python trades:")
    print(py_df.head(10).to_string())
    print(f"\nLast 10 Python trades:")
    print(py_df.tail(10).to_string())
