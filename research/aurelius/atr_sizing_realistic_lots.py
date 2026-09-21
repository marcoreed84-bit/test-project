"""
Real-world check on the ATR-inverse sizing idea: a broker enforces a
lot-size FLOOR (this account's SYMBOL_VOLUME_MIN=0.01, step=0.01 -
same values Vanguard_EA.mq5's LotSize() already reads from the
symbol). The idealized Python scaling (continuous, no floor) can
shrink a position to whatever fraction ATR implies; a REAL account
cannot go below 0.01 lots. If the "fair" size at high ATR is already
below 0.01, the position gets stuck at the floor and the evening-out
effect partially breaks down for exactly the highest-volatility
(2026) trades - the ones it's most meant to shrink.

Calibrated so the MEAN trade gets 0.02 lots (double today's fixed
0.01), giving headroom to shrink toward the 0.01 floor in high-ATR
periods and grow above it in low-ATR periods - realistic for how the
EA would actually compute InpLots dynamically.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered
from atr_sizing_dd_fix import drawdown_stats_scaled

LOT_MIN = 0.01
LOT_STEP = 0.01


def realistic_lots(mean_atr, atr_val, base_lots=0.02):
    ideal = base_lots * (mean_atr / atr_val)
    rounded = round(ideal / LOT_STEP) * LOT_STEP
    return max(rounded, LOT_MIN)


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

    for base_lots in (0.01, 0.02, 0.03):
        lots = [realistic_lots(mean_atr, atr[i], base_lots) for i, ex, pnl, isbuy in trades_fixed]
        floored_pct = 100 * np.mean(np.array(lots) <= LOT_MIN + 1e-9)
        scale = np.array(lots) / 0.01   # relative to the fixed-lot baseline actually run on MT5
        trades_scaled = [(i, ex, pnl * s, isbuy) for (i, ex, pnl, isbuy), s in zip(trades_fixed, scale)]
        closed_dd, float_dd, net = drawdown_stats_scaled(trades_scaled, scale, close, spread, n)

        print(f"=== base_lots={base_lots} (mean lot -> at floor {floored_pct:.0f}% of trades) ===")
        by_year = {}
        for (i, ex, pnl, isbuy), s in zip(trades_fixed, scale):
            by_year.setdefault(years[i], []).append(pnl * s)
        for y in sorted(by_year):
            yp = np.array(by_year[y])
            print(f"  {y}: n={len(yp):4d} net={yp.sum():9.2f}")
        print(f"  TOTAL net={net:.2f} closedDD%={100*closed_dd/net:.1f} floatDD%={100*float_dd/net:.1f}")
        print()
