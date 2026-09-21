"""
Direct response to the user's stated worry: the shipped Vanguard EAs
(fixed 0.01 lots) show real MT5 results where 2026 alone (partial year)
carries ~60% of total net profit, with 2023-2024 comparatively tiny.
Investigated: is the edge only real in 2026? NO - every year is net
positive with PF>1 in the underlying Python construction (2023: PF
1.091, 2024: PF 1.205, 2025: PF 1.516, 2026: PF 2.004 - real, not
concentrated on one year in relative terms). But gold's own ATR grew
5.7x from 2023 ($1.18) to 2026 ($6.68) while price only grew 2.36x
(ATR as % of price: 0.061% -> 0.146%, real volatility expansion, not
just nominal price-level inflation) - and the EA trades a FIXED lot
size regardless, so dollar P&L per trade is heavily inflated by
gold's own growing volatility in recent years, not by the strategy
becoming intrinsically better at picking trends.

Direct fix: size each position inversely to its own entry ATR (risk a
roughly constant amount per trade, standard practice) instead of a
fixed lot. Tests whether this flattens the year-by-year distribution
while keeping every year genuinely profitable - not previously tried
on this construction (Meridian's own position-sizing test earlier this
session targeted a DIFFERENT goal - reducing drawdown - and was
rejected for that; this tests a different, more directly relevant
goal: year-to-year evenness).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered
from meridian_dd_confluence_test import drawdown_stats

N_RANDOM_SEEDS = 300


def sim_atr_sized(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr, mean_atr):
    """Same hold-to-reversal sim as sim_trendline_filtered, but each
    trade's raw price-difference pnl is rescaled by mean_atr/entry_atr
    - equivalent to sizing the position inversely to that trade's own
    entry ATR, holding average total risk constant across the whole
    backtest (matches how drawdown_stats expects a plain pnl series,
    so DD/walk-forward tooling all works unchanged)."""
    trades, skipped = sim_trendline_filtered(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr)
    scaled = []
    for i, ex, pnl, is_buy in trades:
        scale = mean_atr / atr[i]
        scaled.append((i, ex, pnl * scale, is_buy))
    return scaled, skipped


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

    trades, skipped = sim_atr_sized(events, entry_ok, close, high, low, spread, atr, n, 4.0, mean_atr)
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)

    print("=" * 70)
    print("ATR-INVERSE POSITION SIZING vs FIXED LOT (both +VWAP+S/R, k=100, sl=4.0xATR)")
    print()
    print(f"FIXED-LOT net={sum(t[2] for t in trades_fixed):.2f}")
    print(f"ATR-SIZED  net={net:.2f} pf={pf:.3f} win%={100*(pnls>0).mean():.1f} n={len(trades)}")
    if net > 0:
        print(f"  closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")

    print("\nyear-by-year (ATR-sized):")
    by_year = {}
    for i, ex, pnl, is_buy in trades:
        by_year.setdefault(years[i], []).append(pnl)
    for y in sorted(by_year):
        yp = np.array(by_year[y])
        ygw = yp[yp > 0].sum(); ygl = -yp[yp <= 0].sum()
        ypf = ygw / ygl if ygl > 0 else float("inf")
        print(f"  {y}: n={len(yp):4d} net={yp.sum():9.2f} pf={ypf:.3f} win%={100*(yp>0).mean():.1f}")

    sorted_p = np.sort(pnls)[::-1]
    print(f"\ntop20 sum={sorted_p[:20].sum():.2f} ({100*sorted_p[:20].sum()/net:.1f}% of net)  "
          f"net excl top20={net - sorted_p[:20].sum():.2f}")

    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
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
        trades_r, _ = sim_atr_sized(rev, entry_ok, close, high, low, spread, atr, n, 4.0, mean_atr)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < net).mean()
    print(f"random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")
