"""
User's question: Aurelius's own "H4" (InpP2400=2400, MODE_EMA) is actually
just a 2400-period EMA computed directly on M5 close - no separate H4
dataset, no cross-timeframe bar-index mapping, so none of the lookahead
risk that broke the real H4 filter tests today. Its period (2400) was
independently validated on AURELIUS's own data by a prior Opus sweep, not
discovered by looking at Vanguard's blind window - so testing it on
Vanguard does NOT require burning/splitting the blind window the way the
low-vol regime idea did (that threshold WAS discovered on Vanguard's own
data). This can be tested directly on the FULL genuinely untouched
2014-06-13->2022-07-04 window without circularity.

CONSTRUCTION: require M5 close to be on the trade-direction side of its
own 2400-period EMA (buy needs close > ema2400, sell the mirror), added on
top of Vanguard's existing trendline+VWAP+S/R logic. K=1 - one
pre-specified, externally-validated parameter, not swept.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
import vanguard_random_timing_test as V

CUTOFF = "2022-07-04"
START = "2014-06-13"
SLOW_EMA_PERIOD = 2400   # Aurelius's own InpP2400, MODE_EMA - independently validated there


def ema(x, period):
    return pd.Series(x).ewm(span=period, adjust=False).mean().values


if __name__ == "__main__":
    m5_full = E.load_m5_extended()
    h4 = E.load_h4()
    m5 = m5_full[(m5_full["time"] >= START) & (m5_full["time"] < CUTOFF)].reset_index(drop=True)
    print(f"Untouched window: {m5['time'].min()} -> {m5['time'].max()} (n={len(m5)})")

    ctx = E.build_context(m5, h4, E.P)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]

    slow_ema = ema(close, SLOW_EMA_PERIOD)
    trend_up = close > slow_ema

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=V.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap

    entry_ok_base = np.zeros(n, dtype=bool)
    entry_ok_slowma = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        if sr >= 0.0 and sr < V.MIN_SR:
            continue
        entry_ok_base[i] = True
        ma_ok = trend_up[i] if d > 0 else (not trend_up[i])
        if i >= SLOW_EMA_PERIOD and ma_ok:  # need real warm-up, same fail-closed convention as elsewhere
            entry_ok_slowma[i] = True

    for label, entry_ok in (("BASELINE (no slow-MA filter)", entry_ok_base),
                             ("+ 2400-EMA (M5-only, Aurelius's own) filter", entry_ok_slowma)):
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
