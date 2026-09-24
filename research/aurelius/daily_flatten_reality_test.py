"""
Quantifies the real behavioral gap found in Aurelius_EA.mq5/Aurelius_M15_EA.mq5's
InpCloseBeforeBreak mechanism (2026-09-24): real MT5 backtest data (the
2026-09-22 full-history GOLD reports) shows a position surviving multiple
ordinary, non-holiday daily "settlement break" windows (e.g. a real M15 trade
held Tue 2024-10-15 15:15 -> Fri 2024-10-18 22:00, 3 days 6 hours, no holiday
involved) despite InpCloseBeforeBreak=true being the shipped default. The
real EA's NearSessionClose()/MinutesToSessionClose() depends on
SymbolInfoSessionTrade() reporting a genuine intraday session boundary for
GOLD on this broker Mon-Thu - it evidently does not.

SEPARATE, ALSO NEW finding this script exists to quantify: engine.py's own
build_context() has, this whole session, modeled the OPPOSITE of that real
behavior - `near_daily_close = mins_to_midnight <= 5` (engine.py line ~438)
fires unconditionally every day, an explicit time-of-day calc with no
SymbolInfoSessionTrade dependency. So every Python-only screen run against
this file's baseline all session (the InpMinSlopeATR sweep, the ablation
study, the divergence screens, etc.) has been simulating a DAILY FLATTEN
THAT THE REAL EA DOES NOT ACTUALLY PERFORM. This script measures how much
that assumption is worth in Python-model terms, by comparing engine.py's
existing baseline (daily flatten ON, its current behavior) against a
"reality" variant (daily flatten OFF, matching what real GOLD MT5 testing
actually shows) - Friday's flatten is untouched in both, since that one IS
real-confirmed working (WeekendStillOpen, a genuinely tick-level, deadline-
based mechanism, unlike the Mon-Thu case).

This is NOT a proposal to change engine.py's default going forward (that is
a separate decision) - it is a diagnostic run to size the gap honestly,
requested directly after the real 3-day-hold finding above. GOLD# M5 data
(2023-01-03..2026-08-14) and the lossless M15 resample, same convention as
every other script in this folder.
"""
import numpy as np
import engine as E
import sim as S


def run(ctx, params, label):
    trades = S.simulate(ctx, params=params)
    st = S.stats(trades)
    rk = S.risk_stats(trades, ctx)
    n_session_close = sum(1 for t in trades if t["reason"] == "SESSION_CLOSE")
    pf = f"{st['pf']:.4f}" if st.get("n") and st["pf"] != float("inf") else "n/a"
    print(f"  {label}")
    print(f"    n={st.get('n',0):4d} net=${st.get('net',0):10.2f} pf={pf:>7s} "
          f"closedDD=${rk['closed_dd']:8.2f} floatDD=${rk['float_dd']:8.2f} "
          f"session_close_exits={n_session_close}")
    return st, rk


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()

    print("\n=== M5 (Aurelius_EA.mq5) ===")
    ctx5 = E.build_context(df5, h4, params=E.P)
    run(ctx5, E.P, "baseline (Python model: daily flatten fires every day)")
    ctx5_real = dict(ctx5)
    ctx5_real["near_daily_close"] = np.zeros(ctx5["n"], dtype=bool)
    run(ctx5_real, E.P, "reality (daily flatten never fires, Friday flatten unchanged)")

    print("\n=== M15 (Aurelius_M15_EA.mq5) ===")
    df15 = E.resample_m15_from_m5(df5)
    ctx15 = E.build_context(df15, h4, params=E.P15)
    run(ctx15, E.P15, "baseline (Python model: daily flatten fires every day)")
    ctx15_real = dict(ctx15)
    ctx15_real["near_daily_close"] = np.zeros(ctx15["n"], dtype=bool)
    run(ctx15_real, E.P15, "reality (daily flatten never fires, Friday flatten unchanged)")
