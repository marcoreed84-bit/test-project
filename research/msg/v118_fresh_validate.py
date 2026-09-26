"""
Fresh real-vs-sim validation of MSG v1.18 defaults (2026-09-26 request: "run a
fresh real MT5 re-test to confirm v1.17/v1.18"). Real report: GOLD, M1,
2023.01.01-2026.09.25, v1.18 shipped defaults (MSG3-only, MSG1 off,
OneTradeAfterLoss off) - 499 real round trips over 3.75yr, PF=1.559.

Only the tail overlapping load_bars()'s own coverage (2025-11-19 onward) can
be walked trade-by-trade. Found and fixed a real bug in the process: Params'
default bid_off/ask_extra (-0.12/0.16) were a GOLD#->GOLD conversion left
over from before the 2026-09-25 CSV switch to real GOLD bars - applying it
now double-shifts prices. Entry-minute match went 10% (broken) -> 97%
(112/115) once zeroed - see sim.py's Params docstring for the full note.
"""
import sys
import pandas as pd
sys.path.insert(0, "/home/user/test-project/research/msg")
from report import load_deals, load_settings, round_trips, summary
from sim import load_bars, simulate, stats, Params

PATH = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/181a1802-20260926_-_ReportTester-382043238_-_MSG_-_Backtest_1_-_Defaults.xlsx"
GOLD = dict(bid_off=0.0, ask_extra=0.0)   # bars are already real GOLD post 2026-09-25 switch - no conversion needed

def params_from_settings(s, sym, start, end, **kw):
    ses = []
    if s.get("InpMsg1Enable") == "true":
        ses.append((int(s["InpMsg1StartHour"]), int(s["InpMsg1EndHour"])))
    if s.get("InpMsg2Enable") == "true":
        ses.append((int(s["InpMsg2StartHour"]), int(s["InpMsg2EndHour"])))
    if s.get("InpMsg3Enable") == "true":
        ses.append((int(s["InpMsg3StartHour"]), int(s["InpMsg3EndHour"])))
    if s.get("InpMsg4Enable") == "true":
        ses.append((int(s["InpMsg4StartHour"]), int(s["InpMsg4EndHour"])))
    return Params(
        zone_top=float(s.get("InpZoneTopPct", 50.0)), zone_bot=float(s.get("InpZoneBotPct", 78.6)),
        range_risk=float(s.get("InpRangeRiskPct", 30.8)), min_ext=float(s.get("InpMinExtensionPct", 10.0)),
        watch_h=float(s.get("InpMaxSetupWatchHours", 4.25)), max_hold_h=float(s.get("InpMaxHoldHours", 48)),
        max_spread=float(s.get("InpMaxSpreadPoints", 60)),
        fixed_fib_sl=s.get("InpFixedFibSL") == "true", fib_sl_pct=float(s.get("InpFibSLPct", 78.6)),
        skip_dead=s.get("InpSkipDeadZone") == "true",
        dz_min=float(s.get("InpDeadZoneMinPct", 0.18)), dz_max=float(s.get("InpDeadZoneMaxPct", 0.26)),
        start=start, end=end,
        sessions=tuple(ses), lock_mode="static", **sym, **kw)

def key(t):
    return t["entry_time"].replace(second=0, microsecond=0)

if __name__ == "__main__":
    s = load_settings(PATH)
    real_all = round_trips(load_deals(PATH))
    print(f"Real report (v1.18 defaults, GOLD M1): full period n={len(real_all)}, "
          f"{real_all[0]['entry_time']} -> {real_all[-1]['entry_time']}")
    full_rs = summary([t["pnl_usd"] for t in real_all])
    print(f"  FULL 3.75yr real headline (USD pnl basis): {full_rs}")

    bars = load_bars()
    bmin, bmax = bars["time"].min(), bars["time"].max()
    print(f"\nCurrent sim M1 bars available: {bmin} -> {bmax}")

    real_overlap = [t for t in real_all if bmin <= t["entry_time"] <= bmax]
    print(f"Real trades whose entry falls inside that overlap window: n={len(real_overlap)}")

    p = params_from_settings(s, GOLD, start=str(bmin.date()), end=str((bmax + pd.Timedelta(days=1)).date()))
    sim, _ = simulate(bars, p)
    print(f"\nSIM (v1.18 defaults) over the SAME overlap window: n={len(sim)}")

    rk = {key(t): t for t in real_overlap}
    sk = {key(t): t for t in sim}
    both = set(rk) & set(sk)
    rs, ss = summary([t["pnl_usd"] for t in real_overlap]), stats(sim)
    legs_match = sum(rk[x]["nlegs"] == sk[x]["nlegs"] for x in both)
    print(f"\nREAL (overlap) n={rs['n']:3d} net={rs['net']:8.2f} PF={rs['pf']:5.2f} win%={rs['win']:.1f}")
    print(f"SIM  (overlap) n={ss['n']:3d} net={ss['net']:8.2f} PF={ss['pf']:5.2f}")
    print(f"entry-minute match: {len(both)}/{rs['n']} ({100*len(both)/max(1,rs['n']):.0f}%), same-leg-count on matched: {legs_match}/{len(both)}")
