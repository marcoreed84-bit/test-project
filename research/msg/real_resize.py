"""
Sizing-only candidates are CASCADE-FREE: a 0.01/0.02-lot position occupies
the single slot for exactly as long as the 0.03-lot one (partials never
close the position; the SL moves at TP1/TP2 happen identically), so the
downstream trade sequence cannot change.  That makes it legitimate - unlike
v1.13's skip filter - to evaluate them directly on REAL MT5 trade lists.

Re-derivation of a real 0.03-lot round-trip at smaller size, per the EA's
own ClosePartial()/LotStep() arithmetic:
  0.01 lots: TP1 partial = LotStep(0.0033) = 0 -> skipped; TP2 partial would
             leave < min volume -> skipped.  P/L = final leg only, 1 unit.
  0.02 lots: TP1 partial = LotStep(0.0067) = 0.01 -> taken; TP2 partial would
             leave 0 -> skipped.  P/L = TP1 leg (if any) + final leg, 1 unit each.
"""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "/home/user/test-project/research/msg")
from report import load_deals, round_trips, entry_orders  # noqa

UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
LISTS = [
    ("REAL T1 EA, own 108 trades", "2160b5b6-20260922_-_ReportTester-382043238_-_MSG_-_Backtest_1_Original_1Min.xlsx"),
    ("recon v1.11 Backtest_11 GOLD", "0dbf3455-20260922_-_ReportTester-382043238_-_MSG_-_Backtest_11.xlsx"),
    ("recon v1.12 Backtest_1 GOLD", "28855db1-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_1.xlsx"),
    ("recon v1.12 Fib-SL GOLD", "7a798589-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_1_Fib_true.xlsx"),
    ("recon v1.13 Backtest_2 GOLD", "9d84e911-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_2.xlsx"),
]


def leg_usd(t, leg, units):
    return (leg["price"] - t["entry"]) * t["side"] * units


def resized(t, lots):
    if lots >= 0.03 - 1e-9:
        return t["pnl_usd"]
    legs = t["legs"]
    final = leg_usd(t, legs[-1], 1)
    if lots < 0.015:
        return final
    if len(legs) == 1:          # no TP1 partial ever taken: both units exit together
        return 2 * final
    return leg_usd(t, legs[0], 1) + final


def load(f):
    trips = round_trips(load_deals(UP + f))
    orders = {o["time"]: o for o in entry_orders(UP + f)}
    for t in trips:
        o = orders[t["entry_time"]]
        t["risk_pct"] = abs(o["px"] - o["sl"]) / o["px"] * 100.0
    return trips


def st(p):
    p = np.asarray(p)
    gp, gl = p[p > 0].sum(), -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = (np.maximum.accumulate(np.concatenate([[0], eq]))[1:] - eq).max()
    return p.sum(), gp / gl, dd


if __name__ == "__main__":
    for label, f in LISTS:
        trips = load(f)
        b = st([t["pnl_usd"] for t in trips])
        print(f"== {label}: n={len(trips)} net ${b[0]:.2f} PF {b[1]:.3f} maxDD ${b[2]:.2f}")
        for lots in (0.01, 0.02):
            cells = []
            for th in (0.18, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30):
                c = st([resized(t, lots) if t["risk_pct"] < th else t["pnl_usd"] for t in trips])
                cells.append(f"<{th:.2f}: {c[0]-b[0]:+7.2f} PF {c[1]:.2f} DD {c[2]:.0f}")
            print(f"   {lots:.2f} lots  " + " | ".join(cells))
