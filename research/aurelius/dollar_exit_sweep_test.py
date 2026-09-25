"""
Follow-up to ten_dollar_exit_compare_test.py - user asked directly "have you
tried targets less than 10, 9usd, 8usd?" ($10 was picked because the user
said it, not because it was tested against nearby values). Sweeps the same
symmetric flat-$ TP/SL bracket, on the SAME real entry signals (Aurelius:
sim.py EA-faithful simulator; Meridian: msim.py EA-faithful simulator),
across a range of distances to see whether win%/PF actually improves,
degrades, or is flat as the target shrinks - real spread is already baked
into each trade's entry_px (one round-trip charge, same convention as the
$10 test), so a smaller target facing the SAME fixed spread cost should, if
anything, look WORSE per trade, not better - that's the real risk of
"take a smaller win" that this sweep checks honestly rather than assumes.
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "../meridian")
import numpy as np
import pandas as pd
import engine as E
from sim import simulate as aurelius_simulate

import msim

np.random.seed(42)

DISTANCES = (5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 15.0, 20.0)
MAXHOLD = 2880


def apply_fixed_bracket(entries, high, low, n, tp_usd, sl_usd, maxhold):
    trades, last_exit, open_n = [], -1, 0
    for entry_i, d, entry_px in entries:
        if entry_i < last_exit:
            continue
        tp = entry_px + tp_usd if d > 0 else entry_px - tp_usd
        sl = entry_px - sl_usd if d > 0 else entry_px + sl_usd
        eb, pnl = None, None
        for k in range(entry_i, min(entry_i + maxhold, n)):
            if d > 0:
                if low[k] <= sl: eb, pnl = k, -sl_usd; break
                if high[k] >= tp: eb, pnl = k, tp_usd; break
            else:
                if high[k] >= sl: eb, pnl = k, -sl_usd; break
                if low[k] <= tp: eb, pnl = k, tp_usd; break
        if eb is None:
            open_n += 1
            continue
        trades.append((entry_i, eb, pnl))
        last_exit = eb
    return trades, open_n


def row(trades, dist):
    if len(trades) < 8:
        return f"    ${dist:>4.0f}: only {len(trades)} resolved - too few"
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    win_pct = 100 * (pnls > 0).mean()
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    cutoff = entries.min() + (entries.max() - entries.min()) * 0.7
    is_p = pnls[entries < cutoff]; oos_p = pnls[entries >= cutoff]
    is_w = 100 * (is_p > 0).mean() if len(is_p) >= 8 else float("nan")
    oos_w = 100 * (oos_p > 0).mean() if len(oos_p) >= 8 else float("nan")
    return (f"    ${dist:>4.0f}: n={len(trades):>4} win%={win_pct:5.1f}  pf={pf:.3f}  "
            f"net=${pnls.sum():7.0f}  IS win%={is_w:5.1f}(n={len(is_p)})  OOS win%={oos_w:5.1f}(n={len(oos_p)})")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    a_trades_real = aurelius_simulate(ctx, params=E.P)
    a_entries = [(t["entry_i"], t["dir"], t["entry_px"]) for t in a_trades_real]
    a_n = ctx["n"]

    mctx = msim.build_ctx()
    win_start = mctx["t64"].min(); win_end = mctx["t64"].max()
    m_trades_real, _ = msim.simulate(mctx, start=win_start, end=win_end)
    m_entries = [(t["entry_i"], t["dir"], t["entry"]) for t in m_trades_real]
    m_n = len(mctx["c"])

    print("=" * 90)
    print("AURELIUS real entries, symmetric $TP/$SL sweep (breakeven win% for a fair coin is 50.0)")
    print("=" * 90)
    for dist in DISTANCES:
        trades, open_n = apply_fixed_bracket(a_entries, ctx["high"], ctx["low"], a_n, dist, dist, MAXHOLD)
        print(row(trades, dist))

    print()
    print("=" * 90)
    print("MERIDIAN real entries, symmetric $TP/$SL sweep")
    print("=" * 90)
    for dist in DISTANCES:
        trades, open_n = apply_fixed_bracket(m_entries, mctx["h"], mctx["l"], m_n, dist, dist, MAXHOLD)
        print(row(trades, dist))
