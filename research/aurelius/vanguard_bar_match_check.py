"""
Vanguard_EA.mq5 bar-match check - the validation that was missing (unlike
Ratchet/validate.py, Meridian/msim bar-match, H&S/hs_sim bar-match). Uses
the user's own real MT5 report (aa841052-...-Vanguard_-_Backtest_1.xlsx,
GOLD, 2026.01.01-2026.09.25, 100% real ticks - the highest tick quality of
the uploaded Vanguard reports) as ground truth, matched by entry bar
(floored to the nearest 5-minute M5 bar) against vanguard_random_timing_
test.py's own sim_full()/build_breakout_events() construction, unchanged.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import openpyxl
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from vanguard_random_timing_test import sim_full, FRACTAL_K, MIN_SR, SAFETY_SL_ATR, STALE_BARS, STALE_MIN_PROFIT_ATR

XLSX = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/aa841052-20260926_-_ReportTester-382043238_-_Vanguard_-_Backtest_1.xlsx"


def load_real_deals(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    start = next(i for i, r in enumerate(rows) if r and r[0] == "Deals")
    header = [v for v in rows[start + 1] if v is not None]
    entries = []
    for r in rows[start + 2:]:
        vals = list(r)
        if not vals or vals[0] is None:
            continue
        d = dict(zip(header, vals))
        if d.get("Symbol") == "GOLD" and d.get("Direction") == "in":
            entries.append(dict(time=pd.Timestamp(d["Time"]), side=1 if d["Type"] == "buy" else -1,
                                price=float(d["Price"])))
    return entries


def key(ts):
    return pd.Timestamp(ts).floor("5min")


if __name__ == "__main__":
    real = load_real_deals(XLSX)
    print(f"Real Vanguard trades (GOLD, 2026.01.01-2026.09.25, 100% real ticks): n={len(real)}")

    df5 = E.load_m5()
    h4 = E.load_h4()
    print(f"Simulator data: {df5['time'].min()} -> {df5['time'].max()} ({len(df5)} bars)")
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]; sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    entry_ok = vwap_ok & sr_ok

    sim_trades = sim_full(events, entry_ok, close, high, low, spread, atr, n,
                          SAFETY_SL_ATR, stale_bars=STALE_BARS, stale_min_profit_atr=STALE_MIN_PROFIT_ATR)
    times = df5["time"].values
    WIN_LO, WIN_HI = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-09-25")
    sim_by_key = {}
    for (i, exit_bar, pnl, is_buy, entry) in sim_trades:
        # sim_full's `i` is the SIGNAL bar (breakout close); the real fill happens
        # on the NEXT bar's open (i+1) - match on the fill bar, not the signal bar.
        fill_i = min(i + 1, len(times) - 1)
        ts = pd.Timestamp(times[fill_i])
        if WIN_LO <= ts <= WIN_HI:
            sim_by_key[key(ts)] = dict(side=1 if is_buy else -1, price=entry)

    real_only_window = [r for r in real if WIN_LO <= r["time"] <= WIN_HI]
    real_by_key = {key(r["time"]): r for r in real_only_window}
    print(f"sim trades in the SAME 2026.01.01-2026.09.25 window: {len(sim_by_key)}")

    both = sorted(set(real_by_key) & set(sim_by_key))
    only_real = sorted(set(real_by_key) - set(sim_by_key))
    only_sim = sorted(set(sim_by_key) - set(real_by_key))
    same_dir = sum(real_by_key[k]["side"] == sim_by_key[k]["side"] for k in both)

    print(f"\nentry-bar matches: {len(both)} ({100*len(both)/max(1,len(real_by_key)):.1f}% of real's "
          f"{len(real_by_key)} trades in this window)")
    print(f"real-only (sim missed): {len(only_real)}   sim-only (sim invented): {len(only_sim)}")
    print(f"of matched bars, same direction: {same_dir}/{len(both)}")
    if both:
        pdiff = [abs(real_by_key[k]["price"] - sim_by_key[k]["price"]) for k in both]
        print(f"entry price diff on matched bars: median={np.median(pdiff):.3f}  max={np.max(pdiff):.3f}")
