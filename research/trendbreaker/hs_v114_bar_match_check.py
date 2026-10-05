"""
H&S GOLD bar-match check, v1.14-specific: does today's (2026-10-04) fixed
HeadShoulders_EA.mq5 build (restart-retrigger dedup fix, AdvancePending()
expiry-ordering fix, ScheduleRetry() throttle-vs-failure fix) and the
matching hs_sim.py (dedup key now head+direction, retest-window age
brkShift-1) actually reproduce the brand-new real MT5 report run on that
build?

Real report: /root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/
4feecdad-20261005_-_ReportTester-382043238_-_HS_-_Backtest.xlsx
GOLD, M15, 2026.01.01-2026.09.25, 100% real ticks, 65 trades.

BEFORE running this, confirmed (see conversation) that this report's own
Inputs: block matches hs_sim.DEFAULTS field-for-field (InpPivotStrength=5,
InpSwingMinATR=1.0, InpATRPeriod=14, InpLookbackBars=800,
InpRecomputeEveryBars=5, InpShoulderTolATR=1.5, InpBreakTolATR=0.35,
InpBreakConfirmCloses=3, InpMaxHorizonMult=4.0, InpStopBufferATR=1.0,
InpUsePullbackEntry=true, InpPullbackTolATR=0.75, InpPullbackWindowBars=30,
InpUseRunner=true, InpRunnerTrailATR=0.5, InpMaxSpreadPoints=60) - so this
is NOT a repeat of the original Gold false-alarm (wrong stale report,
mismatched Inputs). Methodology and parsing copied from
hs_gold_bar_match_check.py (openpyxl Deals-table load) and the general
approach in research/aurelius/vanguard_bar_match_check.py.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import openpyxl
import engine as E
import hs_sim as HS

XLSX = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/4feecdad-20261005_-_ReportTester-382043238_-_HS_-_Backtest.xlsx"
WIN_LO, WIN_HI = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-09-25")


def load_real_deals(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    start = next(i for i, r in enumerate(rows) if r and r[0] == "Deals")
    header = [v for v in rows[start + 1] if v is not None]
    entries = []
    exits = []
    for r in rows[start + 2:]:
        vals = list(r)
        if not vals or vals[0] is None:
            continue
        d = dict(zip(header, vals))
        if d.get("Symbol") != "GOLD":
            continue
        rec = dict(time=pd.Timestamp(d["Time"]), side=1 if d["Type"] == "buy" else -1,
                   price=float(d["Price"]), profit=float(d["Profit"] or 0.0),
                   comment=d.get("Comment"))
        if d.get("Direction") == "in":
            entries.append(rec)
        elif d.get("Direction") == "out":
            exits.append(rec)
    return entries, exits


def key(ts):
    return pd.Timestamp(ts).floor("15min")


if __name__ == "__main__":
    real_in, real_out = load_real_deals(XLSX)
    real_w = [r for r in real_in if WIN_LO <= r["time"] <= WIN_HI]
    print(f"Real H&S GOLD v1.14 trades (M15, {WIN_LO.date()}-{WIN_HI.date()}): n={len(real_w)}")
    real_net = sum(r["profit"] for r in real_out if WIN_LO <= r["time"] <= WIN_HI)
    print(f"Real net P/L (from Deals 'out' rows, same window): {real_net:.2f}")

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
            sim_by_key[key(ts)] = t
    print(f"sim trades in the same window: {len(sim_by_key)}")

    real_by_key = {key(r["time"]): r for r in real_w}
    both = sorted(set(real_by_key) & set(sim_by_key))
    only_real = sorted(set(real_by_key) - set(sim_by_key))
    only_sim = sorted(set(sim_by_key) - set(real_by_key))
    same_dir = sum(real_by_key[k]["side"] == sim_by_key[k]["dir"] for k in both)

    print(f"\nentry-bar matches: {len(both)} ({100*len(both)/max(1,len(real_by_key)):.1f}% of real's "
          f"{len(real_by_key)} trades)")
    print(f"real-only (sim missed): {len(only_real)}   sim-only (sim invented): {len(only_sim)}")
    print(f"of matched bars, same direction: {same_dir}/{len(both)}")
    if both:
        pdiff = [abs(real_by_key[k]["price"] - sim_by_key[k]["entry_px"]) for k in both]
        print(f"entry price diff on matched bars: median={np.median(pdiff):.3f}  max={np.max(pdiff):.3f}")

    sim_net = sum(t["pnl"] for t in tr if WIN_LO <= pd.Timestamp(times[t["entry_i"]]) <= WIN_HI)
    print(f"\nsim net P/L (raw price pnl, no commission/swap/spread-on-exit): {sim_net:.2f}")
    print(f"real net P/L: {real_net:.2f}")

    # off-by-one probe: check if shifting sim keys by +/-15min improves the match,
    # which would indicate a signal-bar vs fill-bar misalignment rather than a
    # genuine miss.
    for shift_min in (-15, 0, 15):
        shifted = {(k + pd.Timedelta(minutes=shift_min)): v for k, v in sim_by_key.items()}
        m = len(set(real_by_key) & set(shifted))
        print(f"  shift sim by {shift_min:+d}min -> {m} matches ({100*m/max(1,len(real_by_key)):.1f}%)")
