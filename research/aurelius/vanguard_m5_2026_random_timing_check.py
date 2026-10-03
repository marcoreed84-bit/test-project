"""
Why does Vanguard M5 look good on 2026 specifically? Checks the real
mechanism directly instead of asserting "overfitting" in the abstract:
does RANDOM-direction entry, using the exact same stop/exit machinery
(SafetyStopATR trailing stop, stale-bar exit), on this SAME 2026 window
Vanguard was tuned on, also show a profit?

If yes - and it does - that means 2026 itself was a market where almost
any directional bet with sane risk management made money, not that
Vanguard's trendline-breakout signal is specifically skilled. The real
system's edge over that baseline is then the honest test of whether its
signal adds anything beyond "being in this market, this year, with this
risk management" - and even on its own tuning window, before any
multiple-testing correction for the ~24 parameter combinations actually
searched to land on these settings, it's only marginally above that
baseline (p=0.043, uncorrected).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
import vanguard_random_timing_test as V

START = "2026-01-01"

if __name__ == "__main__":
    m5_full = E.load_m5_extended()
    h4 = E.load_h4()
    m5 = m5_full[m5_full["time"] >= START].reset_index(drop=True)
    print(f"2026 slice (Vanguard M5's own tuning window): n={len(m5)} bars, {m5['time'].min()} -> {m5['time'].max()}")

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
    real_pf = V.pct_pf(real_trades)
    pnls = np.array([t[2] for t in real_trades])
    print(f"REAL Vanguard M5 on 2026: n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  %PF={real_pf:.3f}")

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
    print(f"random-entry (same exits/risk, SAME 2026 window) %PF distribution: "
          f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pf).mean()
    p_val = (pool >= real_pf).mean()
    print(f"REAL %PF={real_pf:.3f} -> {pctile:.1f}th percentile of random on THIS SAME window, "
          f"p={p_val:.4f} (uncorrected for the ~24 combinations actually searched to find these settings)")
