"""
Fixes a real bug just introduced in atr_position_sizing_test.py: it fed
ATR-scaled trades (pnl already multiplied by mean_atr/entry_atr) into
meridian_dd_confluence_test.drawdown_stats() unmodified. That function
computes the FLOATING (open-position) mark-to-market from RAW,
UNSCALED price differences (close[...] - entry), then adds it onto
last_eq, which IS the scaled cumulative realized equity. Mixing scaled
realized equity with unscaled floating swings overstates floating DD
for every trade taken during a high-ATR period (small scale factor,
small realized pnl, but the floating segment during the trade was
computed as if it were a full 1x-sized position) - exactly backwards
from what the sizing scheme actually does. Needs its own scale-aware
version.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered

POINT = E.POINT


def drawdown_stats_scaled(trades, scales, close, spread, n):
    """Same construction as drawdown_stats, but the floating segment
    for each open trade is scaled by that trade's OWN position-size
    factor, matching how its closed pnl was scaled - keeps realized
    and floating equity on the same footing throughout."""
    pnls = np.array([t[2] for t in trades])
    closed_equity = np.cumsum(pnls)
    closed_dd = (np.maximum.accumulate(closed_equity) - closed_equity).max() if len(closed_equity) else 0.0

    eq_prior = np.concatenate(([0.0], closed_equity[:-1]))
    mtm = np.full(n, np.nan)
    last_eq, prev_exit = 0.0, -1
    for idx, (i, exit_bar, pnl, is_buy) in enumerate(trades):
        scale = scales[idx]
        fill_i = i + 1
        if prev_exit + 1 <= fill_i - 1:
            mtm[prev_exit + 1:fill_i] = last_eq
        entry = close[i] + spread[fill_i] * POINT if is_buy else close[i] - spread[fill_i] * POINT
        seg = close[fill_i:exit_bar + 1]
        floating_raw = (seg - entry) if is_buy else (entry - seg)
        mtm[fill_i:exit_bar + 1] = last_eq + floating_raw * scale
        last_eq = eq_prior[idx] + pnl
        prev_exit = exit_bar
    mtm[prev_exit + 1:] = last_eq
    if trades:
        mtm[:trades[0][0] + 1] = 0.0
    valid = ~np.isnan(mtm)
    mtm_v = mtm[valid]
    float_dd = (np.maximum.accumulate(mtm_v) - mtm_v).max() if len(mtm_v) else 0.0
    final_net = closed_equity[-1] if len(closed_equity) else 0.0
    return closed_dd, float_dd, final_net


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

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

    scales = [mean_atr / atr[i] for i, ex, pnl, isbuy in trades_fixed]
    trades_scaled = [(i, ex, pnl * s, isbuy) for (i, ex, pnl, isbuy), s in zip(trades_fixed, scales)]

    closed_dd_f, float_dd_f, net_f = drawdown_stats_scaled(
        [(i, ex, pnl, isbuy) for i, ex, pnl, isbuy in trades_fixed],
        [1.0] * len(trades_fixed), close, spread, n)
    closed_dd_s, float_dd_s, net_s = drawdown_stats_scaled(trades_scaled, scales, close, spread, n)

    print("CORRECTED (scale-aware) drawdown comparison:")
    print(f"  FIXED-LOT : net={net_f:.2f} closedDD={closed_dd_f:.2f} ({100*closed_dd_f/net_f:.1f}%) "
          f"floatDD={float_dd_f:.2f} ({100*float_dd_f/net_f:.1f}%)")
    print(f"  ATR-SIZED : net={net_s:.2f} closedDD={closed_dd_s:.2f} ({100*closed_dd_s/net_s:.1f}%) "
          f"floatDD={float_dd_s:.2f} ({100*float_dd_s/net_s:.1f}%)")
    print()
    print("  (previous buggy number for ATR-SIZED floatDD was 41.6% - unscaled floating mixed")
    print("   with scaled realized equity. This is the corrected, apples-to-apples comparison.)")
