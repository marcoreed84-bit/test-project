"""
Does Vanguard M5's performance on the genuinely untouched pre-2022-07 data
depend on volatility regime? Real question raised: the 2026 window it was
tuned on is a specific, high-volatility/strongly-trending Gold regime (price
~$4000-4400 in this project's data) - if that regime persists, does a
system that fits it keep working even though it's flat on the FULL blind
history, which spans very different eras (2014-2018 low-vol chop, 2020
COVID spike, etc.)?

TEST: same real Vanguard M5 trades as vanguard_m5_oos_test.py's untouched
pre-2022-07 run, split by each trade's own ATR at entry vs its trailing
252-day (1yr, M5-bar-equivalent) percentile - i.e. was THIS bar itself a
high-vol-regime bar or a low-vol-regime bar, using only information
available at the time (trailing window, no lookahead). Reports %PF
separately for the top-third vs bottom-third ATR-percentile trades within
the SAME untouched dataset - if the edge really is regime-specific, it
should show up as a real split here, not just be asserted.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
import vanguard_random_timing_test as V

CUTOFF = "2022-07-04"

if __name__ == "__main__":
    m5_full = E.load_m5_extended()
    h4 = E.load_h4()
    m5 = m5_full[m5_full["time"] < CUTOFF].reset_index(drop=True)
    print(f"Untouched slice: n={len(m5)} bars, {m5['time'].min()} -> {m5['time'].max()}")

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

    # trailing ATR-percentile regime, causal (trailing 20160 M5 bars ~ 1yr of 24h trading at 5-min bars... but
    # Gold isn't 24h - use a wide trailing window of ACTUAL bars instead, ~1yr of real session bars)
    TRAIL_BARS = 20000  # roughly a year of real M5 session bars for this symbol
    atr_pctile = pd.Series(atr).rolling(TRAIL_BARS, min_periods=2000).rank(pct=True).values

    rows = []
    for (i, exit_bar, pnl, is_buy, entry) in real_trades:
        rp = atr_pctile[i]
        rows.append((rp, pnl))
    rows = [(rp, pnl) for rp, pnl in rows if not np.isnan(rp)]
    rp_arr = np.array([r[0] for r in rows])
    pnl_arr = np.array([r[1] for r in rows])
    print(f"trades with valid trailing-ATR percentile: {len(rows)} / {len(real_trades)}")

    def pf(a):
        a = np.asarray(a)
        if len(a) == 0:
            return float("nan")
        gw = a[a > 0].sum(); gl = -a[a <= 0].sum()
        return gw / gl if gl > 0 else float("inf")

    terciles = np.quantile(rp_arr, [1/3, 2/3])
    low_mask = rp_arr <= terciles[0]
    mid_mask = (rp_arr > terciles[0]) & (rp_arr <= terciles[1])
    hi_mask = rp_arr > terciles[1]
    for label, mask in (("LOW-vol-regime tercile", low_mask), ("MID-vol-regime tercile", mid_mask), ("HIGH-vol-regime tercile", hi_mask)):
        a = pnl_arr[mask]
        print(f"  {label}: n={mask.sum()}  win%={100*(a>0).mean():.1f}  %PF={pf(a):.3f}  net%={100*a.sum():.1f}")
