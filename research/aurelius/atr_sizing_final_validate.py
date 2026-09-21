"""
Full validation of the atr_sizing_realistic_lots.py base_lots=0.01
config (broker-realistic: 0.01 lot floor/step, mean lot size unchanged
from what's already MT5-validated - only reallocates size toward
calmer, lower-ATR periods). Found to improve BOTH total net (3679 vs
2989) AND floating DD (13.0% vs 15.4%) AND evens the year-by-year
distribution (4x range vs 29x) - all at once, which is the same "too
good, verify before trusting" bar this session applies everywhere.
Checking walk-forward, random-direction control, and trade
concentration before recommending it for real implementation.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered
from atr_sizing_dd_fix import drawdown_stats_scaled
from atr_sizing_realistic_lots import realistic_lots, LOT_MIN

N_RANDOM_SEEDS = 300

if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    time = df5["time"].values
    years = np.array([str(t)[:4] for t in time])

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=100)
    events = build_breakout_events(close, desc_line, asc_line, n)

    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < 0.50)
    entry_ok = vwap_ok & sr_ok

    trades_fixed, _ = sim_trendline_filtered(events, entry_ok, close, high, low, spread, atr, n)
    mean_atr = np.mean([atr[i] for i, ex, pnl, isbuy in trades_fixed])

    def scaled_trades(tr):
        scale = np.array([realistic_lots(mean_atr, atr[i], 0.01) / 0.01 for i, ex, pnl, isbuy in tr])
        out = [(i, ex, pnl * s, isbuy) for (i, ex, pnl, isbuy), s in zip(tr, scale)]
        return out, scale

    trades, scale = scaled_trades(trades_fixed)
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats_scaled(trades, scale, close, spread, n)

    print(f"n={len(trades)} net={net:.2f} pf={pf:.3f} win%={100*(pnls>0).mean():.1f}")
    print(f"closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")

    sorted_p = np.sort(pnls)[::-1]
    print(f"top20 sum={sorted_p[:20].sum():.2f} ({100*sorted_p[:20].sum()/net:.1f}% of net)  "
          f"net excl top20={net-sorted_p[:20].sum():.2f}")

    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    for b in range(5):
        lo, hi = edges[b], edges[b+1]
        m = (entries >= lo) & (entries < hi)
        if m.sum() == 0: continue
        if pnls[m].sum() > 0: pos += 1
    print(f"walk-forward: {pos}/5 blocks positive")

    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(events))
        rev = [(i, d) for (i, _), d in zip(events, rdirs)]
        rev.sort(key=lambda e: e[0])
        trades_r, _ = sim_trendline_filtered(rev, entry_ok, close, high, low, spread, atr, n)
        trades_r_scaled, _ = scaled_trades(trades_r)
        random_nets.append(sum(t[2] for t in trades_r_scaled) if trades_r_scaled else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < net).mean()
    print(f"random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")

    # lot-size distribution sanity check
    lots_used = sorted(set(round(realistic_lots(mean_atr, atr[i], 0.01), 3) for i, ex, pnl, isbuy in trades_fixed))
    print(f"\nactual lot sizes this scheme would use: {lots_used}")
