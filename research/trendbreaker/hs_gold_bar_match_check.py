"""
H&S on GOLD bar-match check, same standard just applied to Vanguard and
Silver: does the EA-faithful hs_sim.py (NOT the buggy neckline-fill code
that broke the original Gold verdict) actually reproduce the user's real
MT5 trades? Ground truth: b745bb00-...-HS_-_Backtest_1.xlsx (GOLD, M15,
2023.01.01-2026.09.25, 99% history quality, 599 real trades) - the
cleanest/largest real Gold H&S report uploaded.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import openpyxl
import engine as E
import hs_sim as HS

XLSX = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/b745bb00-20260925_-_ReportTester-382043238_-_HS_-_Backtest_1.xlsx"
WIN_LO, WIN_HI = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-09-25")


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
    return pd.Timestamp(ts).floor("15min")


if __name__ == "__main__":
    real = load_real_deals(XLSX)
    real_w = [r for r in real if WIN_LO <= r["time"] <= WIN_HI]
    print(f"Real H&S GOLD trades (M15, {WIN_LO.date()}-{WIN_HI.date()}, 99% quality): n={len(real_w)}")

    m15 = E.load_m15_native()
    df = m15[(m15["time"] >= WIN_LO) & (m15["time"] <= WIN_HI)][["time", "open", "high", "low", "close", "spread"]].reset_index(drop=True)
    print(f"Simulator data: {df['time'].min()} -> {df['time'].max()} ({len(df)} bars)")

    p = dict(HS.DEFAULTS, point=0.01)
    tr = HS.simulate(df, p)
    times = df["time"].values
    sim_by_key = {}
    for t in tr:
        ts = pd.Timestamp(times[t["entry_i"]])
        if WIN_LO <= ts <= WIN_HI:
            sim_by_key[key(ts)] = dict(side=t["dir"], price=t["entry_px"])
    print(f"sim trades in the same window: {len(sim_by_key)}")

    real_by_key = {key(r["time"]): r for r in real_w}
    both = sorted(set(real_by_key) & set(sim_by_key))
    only_real = sorted(set(real_by_key) - set(sim_by_key))
    only_sim = sorted(set(sim_by_key) - set(real_by_key))
    same_dir = sum(real_by_key[k]["side"] == sim_by_key[k]["side"] for k in both)

    print(f"\nentry-bar matches: {len(both)} ({100*len(both)/max(1,len(real_by_key)):.1f}% of real's "
          f"{len(real_by_key)} trades)")
    print(f"real-only (sim missed): {len(only_real)}   sim-only (sim invented): {len(only_sim)}")
    print(f"of matched bars, same direction: {same_dir}/{len(both)}")
    if both:
        pdiff = [abs(real_by_key[k]["price"] - sim_by_key[k]["price"]) for k in both]
        print(f"entry price diff on matched bars: median={np.median(pdiff):.3f}  max={np.max(pdiff):.3f}")
