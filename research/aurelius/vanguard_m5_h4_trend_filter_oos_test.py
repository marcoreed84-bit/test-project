"""
Attempt to FIX Vanguard M5, not just explain why it fails - add a
higher-timeframe (H4) trend-alignment filter to the entry, on top of the
existing trendline+VWAP+S/R logic, and test on the SAME genuinely
untouched pre-2022-07 data vanguard_m5_oos_test.py already used (the one
that showed PF=1.019, p=0.12 - not distinguishable from random).

RATIONALE: the three exit fixes tried for Meridian all failed because the
entry itself carries no real signal - a better exit can't fix that. This
is the entry-side equivalent for Vanguard: require the M5 trendline
breakout to also agree with the H4 trend direction (H4 close above/below
its own 50-period EMA), not just the local M5 pattern. If the local
breakout only works when the bigger picture agrees, this should show up
as a real improvement on blind data. If it doesn't help, that's honest
evidence the entry signal itself has no real information, confirming
Vanguard the same way the exit experiments confirmed Meridian.

K=1 here - one pre-specified filter, not a swept grid, same no-overfitting-
risk discipline as the clean K=1 tests run earlier tonight.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
import vanguard_random_timing_test as V

CUTOFF = "2022-07-04"
H4_EMA_PERIOD = 50


def ema(x, period):
    return pd.Series(x).ewm(alpha=2.0 / (period + 1.0), adjust=False).mean().values


if __name__ == "__main__":
    m5_full = E.load_m5_extended()
    h4_full = E.load_h4()
    m5 = m5_full[m5_full["time"] < CUTOFF].reset_index(drop=True)
    h4 = h4_full[h4_full["time"] < CUTOFF].reset_index(drop=True)
    print(f"OOS slice: n={len(m5)} M5 bars, {m5['time'].min()} -> {m5['time'].max()} - genuinely untouched")

    ctx = E.build_context(m5, h4, E.P)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]

    # H4 trend state: close vs its own 50-period EMA, causal (uses only
    # H4 bars up to and including the completed H4 bar before each M5 bar)
    h4_ema = ema(h4["close"].values, H4_EMA_PERIOD)
    h4_trend_up = h4["close"].values > h4_ema
    h4_time = h4["time"].values
    m5_time = m5["time"].values
    # for each M5 bar, find the most recent COMPLETED H4 bar (strictly before this M5 bar's time).
    # CORRECTED (found by an Opus audit of a real-MT5 bar-match mismatch, 2026-10-04): side="left"-1
    # above was STILL WRONG for any M5 bar not exactly on an H4 boundary - e.g. at 09:30 it picked
    # the 08:00 H4 bar, which doesn't close until 12:00 (still forming), leaking its already-known
    # final close up to ~4h into the future. The real EA's iClose(PERIOD_H4,1) never has this problem
    # (MT5's own HTF alignment always returns the last truly-closed bar). side="right" on (m5_time +
    # one M5 bar) then -2 steps back two bars from the "last h4_time <= T" index, which is always the
    # FORMING bar, to the one before it - the actually-completed one - verified against real MT5
    # fills: this one-line fix took Vanguard M5's bar-match from 57/65 (88%) to 64/65 (98.5%).
    h4_idx_for_m5 = np.searchsorted(h4_time, m5_time + np.timedelta64(5, "m"), side="right") - 2
    h4_idx_for_m5 = np.clip(h4_idx_for_m5, 0, len(h4) - 1)
    m5_h4_trend_up = h4_trend_up[h4_idx_for_m5]
    valid_h4 = h4_idx_for_m5 >= 1  # need at least one real completed H4 bar behind us

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=V.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap

    entry_ok_base = np.zeros(n, dtype=bool)   # original Vanguard (no H4 filter) - for comparison
    entry_ok_h4 = np.zeros(n, dtype=bool)     # + H4 trend alignment
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

    for label, entry_ok in (("BASELINE (no H4 filter, same as vanguard_m5_oos_test.py)", entry_ok_base),
                             ("+ H4 trend-alignment filter", entry_ok_h4)):
        real_trades = V.sim_full(events, entry_ok, close, high, low, spread, atr, n,
                                  V.SAFETY_SL_ATR, stale_bars=V.STALE_BARS,
                                  stale_min_profit_atr=V.STALE_MIN_PROFIT_ATR)
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
                                     V.SAFETY_SL_ATR, V.STALE_BARS, V.STALE_MIN_PROFIT_ATR)
            pool.append(V.pct_pf(tr))
        pool = np.array(pool)
        pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
        pctile = 100 * (pool < real_pf).mean()
        p_val = (pool >= real_pf).mean()
        print(f"  random-timing null: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
        print(f"  REAL %PF={real_pf:.3f} -> {pctile:.1f}th percentile, p={p_val:.4f}")
