"""
User's new-EA idea (2026-09-25): rather than riding a trade until trend
structure breaks (Aurelius/Meridian's real, shipped exits), close it as
soon as price has moved a flat $10 in either direction - bank the $10 win,
or take the $10 loss, no ATR scaling, no alignment/cross logic on exit.

Before writing a new EA, test the idea honestly: take EACH system's own
REAL, already-validated entry signal (Aurelius: sim.py's EA-faithful
simulator, matches 471/473 real MT5 entries; Meridian: msim.py's
EA-faithful simulator, its own real-matched replica) and swap ONLY the
exit for a flat $10 TP / $10 SL bracket, keeping the real entry gates,
real spread, real single-position sequencing untouched. Reports both
entry sources on their own real data/window so each stays faithful to its
own validated setup, then puts them side by side.

maxhold caps how long an unresolved bracket is followed (2880 M5 bars =
10 trading days) - trades that hit neither side by then are marked "open"
and excluded from win/loss stats, not silently counted as scratches.
"""
import sys
sys.path.insert(0, ".")
sys.path.insert(0, "../meridian")
import numpy as np
import pandas as pd
import engine as E
from sim import simulate as aurelius_simulate

import msim
import bars as B

np.random.seed(42)

TP_USD = 10.0
SL_USD = 10.0
MAXHOLD = 2880   # M5 bars, ~10 trading days


def apply_fixed_bracket(entries, high, low, n, tp_usd, sl_usd, maxhold):
    """entries: list of (entry_i, dir, entry_px), already spread-adjusted,
    single-position (each system's own simulator already enforces that on
    entry side) - re-walked here only for the NEW exit, so no re-sequencing
    needed beyond skipping an entry that starts before the previous one's
    bracket resolved (can happen since the original exit timing differed)."""
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


def report(trades, n_total_entries, open_n, label):
    if len(trades) < 8:
        print(f"  {label}: only {len(trades)} resolved trades - too few to conclude anything")
        return
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    wins = (pnls > 0).sum()
    win_pct = 100 * wins / len(trades)
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    print(f"  {label}: entries={n_total_entries} resolved={len(trades)} open(never hit either side)={open_n}")
    print(f"    win%={win_pct:.1f}  net=${pnls.sum():.0f}  pf={pf:.3f}  "
          f"(at $10 flat win/loss, win% alone determines profitability - "
          f"breakeven is 50%, this system needs > 50% to profit after this swap)")
    n = int(pnls.shape[0])
    span = int(entries.max() - entries.min()) if n > 1 else 1
    cutoff = entries.min() + span * 0.7
    is_p = pnls[entries < cutoff]; oos_p = pnls[entries >= cutoff]
    if len(is_p) >= 8 and len(oos_p) >= 8:
        print(f"    walk-forward: IS win%={100*(is_p>0).mean():.1f} n={len(is_p)}  "
              f"OOS win%={100*(oos_p>0).mean():.1f} n={len(oos_p)}")


if __name__ == "__main__":
    print("=" * 78)
    print(f"Flat ${TP_USD:.0f} TP / ${SL_USD:.0f} SL bracket, real entries, real spread")
    print("=" * 78)

    # --- Aurelius's own real entry gate, own data/window ---
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    a_trades_real = aurelius_simulate(ctx, params=E.P)
    a_entries = [(t["entry_i"], t["dir"], t["entry_px"]) for t in a_trades_real]
    a_n = ctx["n"]
    a_bracket, a_open = apply_fixed_bracket(a_entries, ctx["high"], ctx["low"], a_n, TP_USD, SL_USD, MAXHOLD)
    print(f"\nAurelius real entry gate (pullback-rejection, aligned stack), "
          f"{df5['time'].min().date()} -> {df5['time'].max().date()}:")
    report(a_bracket, len(a_entries), a_open, "AURELIUS entries + $10 bracket")

    # --- Meridian's own real entry gate (21/50 cross + confirm + VWAP + S/R), own data/window ---
    mctx = msim.build_ctx()
    win_start = mctx["t64"].min()
    win_end = mctx["t64"].max()
    m_trades_real, m_diag = msim.simulate(mctx, start=win_start, end=win_end)
    m_entries = [(t["entry_i"], t["dir"], t["entry"]) for t in m_trades_real]
    m_n = len(mctx["c"])
    m_bracket, m_open = apply_fixed_bracket(m_entries, mctx["h"], mctx["l"], m_n, TP_USD, SL_USD, MAXHOLD)
    print(f"\nMeridian real entry gate (21/50 cross + 250 confirm + VWAP + S/R), "
          f"{pd.Timestamp(win_start).date()} -> {pd.Timestamp(win_end).date()}:")
    report(m_bracket, len(m_entries), m_open, "MERIDIAN entries + $10 bracket")

    print("\nNote: this is a SYMMETRIC bracket (equal $10 TP and SL) - a fair coin-flip")
    print("costs nothing after this swap only if win% actually clears 50%, which is a much")
    print("higher bar than either EA's real trend-following exit, where avg_win >> avg_loss")
    print("lets win% sit well under 50% and still be profitable.")
