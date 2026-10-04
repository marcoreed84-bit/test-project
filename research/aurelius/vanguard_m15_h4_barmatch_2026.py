"""
Bar-match: Python simulator (+H4 filter) vs the REAL MT5 backtest of
Vanguard_M15_EA.mq5 v1.08 the user just ran (2026.01.01-2026.09.25,
InpUseH4TrendFilter=true, InpH4EMAPeriod=50, 51 real trades, PF=1.609765,
net 7398.82).
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

START = "2026-01-01"
END = "2026-09-26"
H4_EMA_PERIOD = 50


def ema(x, period):
    return pd.Series(x).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


if __name__ == "__main__":
    m15_full = E.load_m15_native()
    h4_full = E.load_h4()
    m15 = m15_full[(m15_full["time"] >= START) & (m15_full["time"] < END)].reset_index(drop=True)
    print(f"2026 slice: n={len(m15)} bars, {m15['time'].min()} -> {m15['time'].max()}")

    close = m15["close"].values.astype(float)
    high = m15["high"].values.astype(float)
    low = m15["low"].values.astype(float)
    spread = m15["spread"].values.astype(float)
    n = len(m15)

    atr = E.wilder_atr(high, low, close, 14)
    vwap = E.session_vwap(m15)
    sr_hi, sr_lo = build_sr_distance(m15, h4_full)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - close) / atr
        sr_dist_sell = np.abs(close - sr_lo) / atr

    h4_ema = ema(h4_full["close"].values, H4_EMA_PERIOD)
    h4_trend_up = h4_full["close"].values > h4_ema
    h4_time = h4_full["time"].values
    m15_time = m15["time"].values
    h4_idx_for_m15 = np.searchsorted(h4_time, m15_time, side="left") - 1
    h4_idx_for_m15 = np.clip(h4_idx_for_m15, 0, len(h4_full) - 1)
    m15_h4_trend_up = h4_trend_up[h4_idx_for_m15]
    valid_h4 = h4_idx_for_m15 >= 1

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=VM.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        if sr >= 0.0 and sr < VM.MIN_SR:
            continue
        h4_ok = m15_h4_trend_up[i] if d > 0 else (not m15_h4_trend_up[i])
        if valid_h4[i] and h4_ok:
            entry_ok[i] = True

    trades = VM.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                          VM.SAFETY_SL_ATR, stale_bars=VM.STALE_BARS,
                          stale_min_profit_atr=VM.STALE_MIN_PROFIT_ATR)
    pnls = np.array([t[2] for t in trades])
    print(f"PYTHON: n={len(trades)}  win%={100*(pnls>0).mean():.1f}  %PF={V.pct_pf(trades):.3f}")

    rows = []
    for (i, exit_i, pnl, is_buy, entry) in trades:
        rows.append(dict(sig_time=m15["time"].iloc[i], fill_time=m15["time"].iloc[min(i+1, n-1)],
                          dir="buy" if is_buy else "sell", entry=round(entry, 2)))
    py_df = pd.DataFrame(rows)

    real = pd.read_csv("/tmp/vanguard_m15_real_entries.csv", parse_dates=["Time"])
    real["Type"] = real["Type"].str.lower()
    real["matched"] = False
    py_df["matched"] = False
    for pi, prow in py_df.iterrows():
        cand = real[(~real["matched"]) & (real["Type"] == prow["dir"]) &
                    ((real["Time"] - prow["fill_time"]).abs() <= pd.Timedelta(minutes=20))]
        if len(cand):
            ri = cand.index[0]
            real.loc[ri, "matched"] = True
            py_df.loc[pi, "matched"] = True

    print(f"Python trades matched: {py_df['matched'].sum()} / {len(py_df)} ({100*py_df['matched'].mean():.1f}%)")
    print(f"Real trades matched:   {real['matched'].sum()} / {len(real)} ({100*real['matched'].mean():.1f}%)")
