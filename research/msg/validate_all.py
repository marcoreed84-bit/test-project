"""
Step 2 (broad): validate sim.py against EVERY real MT5 M1 report of this
reconstruction that has a known code version, not just one run - so the
simulator cannot simply be tuned to a single report.

Each real report is simulated with the inputs read from its OWN Settings
block, the exit mechanism of the code version it ran (lock_mode), and the
symbol it ran on:
  account 382043238  -> symbol GOLD  (bid -0.12 / ask +0.16 vs the GOLD# CSV,
                                      measured from its own order tickets)
  account 1301959345 -> symbol GOLD# (the CSV's own symbol: sells fill at the
                                      CSV open to the cent, buys at +0.04)
"""
import sys
from dataclasses import replace

sys.path.insert(0, "/home/user/test-project/research/msg")
from report import load_deals, load_settings, round_trips, summary  # noqa: E402
from sim import load_bars, simulate, stats, Params                  # noqa: E402

UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
GOLD = dict(bid_off=-0.12, ask_extra=0.16)
GOLDH = dict(bid_off=0.0, ask_extra=0.04)

# (file, label, code-version exit mechanism, symbol)
REPORTS = [
    ("e0ac6f18-20260922_-_ReportTester-1301959345_-_MSG_1min_-_Backtest_Ours.xlsx", "v1.07 zone61.8 GOLD#", "none", GOLDH),
    ("6e638370-20260922_-_ReportTester-1301959345_-_MSG_1Min_-_Backtest_50.0_-_ours.xlsx", "v1.07 GOLD#", "none", GOLDH),
    ("19f677f4-20260922_-_ReportTester-1301959345_-_MSG_-_Backtest_5_1_Min.xlsx", "v1.08 (48 cached) GOLD#", "none", GOLDH),
    ("268cc3c3-20260922_-_ReportTester-1301959345_-_MSG_-_Backtest_6_1Min_ours-_6_Hours.xlsx", "v1.08 6h GOLD#", "none", GOLDH),
    ("a675561f-20260922_-_ReportTester-1301959345_-_MSG_-_Backtest_7_1_Min.xlsx", "MSG1+MSG3 GOLD#", "none", GOLDH),
    ("65e30458-20260922_-_ReportTester-1301959345_-_MSG_-_Backtest_8_1min_48Hours.xlsx", "v1.09 ratchet 48h GOLD#", "ratchet", GOLDH),
    ("e1bb1f04-20260922_-_ReportTester-1301959345_-_MSG_-_Backtest_9_1min_6Hours.xlsx", "v1.09 ratchet 6h GOLD#", "ratchet", GOLDH),
    ("0dbf3455-20260922_-_ReportTester-382043238_-_MSG_-_Backtest_11.xlsx", "v1.11 static GOLD", "static", GOLD),
    ("28855db1-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_1.xlsx", "v1.12 static GOLD", "static", GOLD),
    ("7a798589-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_1_Fib_true.xlsx", "v1.12 FIB SL GOLD", "static", GOLD),
    ("9d84e911-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_2.xlsx", "v1.13 deadzone GOLD", "static", GOLD),
]


def params_from_settings(s, lock_mode, sym, **kw):
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
        sessions=tuple(ses), lock_mode=lock_mode, **sym, **kw)


def key(t):
    return t["entry_time"].replace(second=0, microsecond=0)


def run(bars, **kw):
    rows = []
    for f, label, lock, sym in REPORTS:
        s = load_settings(UP + f)
        real = round_trips(load_deals(UP + f))
        p = params_from_settings(s, lock, sym, **kw)
        sim, _ = simulate(bars, p)
        rk = {key(t): t for t in real}
        sk = {key(t): t for t in sim}
        both = set(rk) & set(sk)
        rs, ss = summary([t["pnl_usd"] for t in real]), stats(sim)
        legs = sum(rk[x]["nlegs"] == sk[x]["nlegs"] for x in both)
        rows.append((label, rs, ss, len(both), legs))
        print(f"{label:26s} REAL n={rs['n']:3d} net={rs['net']:8.2f} PF={rs['pf']:5.2f} | "
              f"SIM n={ss['n']:3d} net={ss['net']:8.2f} PF={ss['pf']:5.2f} | "
              f"entry-min match {len(both):3d}/{rs['n']:3d} ({100*len(both)/rs['n']:.0f}%), same legs {legs}")
    return rows


if __name__ == "__main__":
    bars = load_bars()
    print("--- no slippage")
    run(bars)
    print("--- measured mean slippage (entry 0.083, stop exits 0.223)")
    run(bars, slip_entry=0.083, slip_sl=0.223)
