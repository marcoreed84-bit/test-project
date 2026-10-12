"""
User's idea (2026-10-12, Silver chart screenshot): for a sell like the
circled example - price opens, pushes above VWAP, reverses and the 21/50
EMAs cross bearish - (1) stop just above where the 21/50 EMAs crossed
(not a fixed ATR multiple), (2) trail the exit against the 50-MA at a
slight distance, allowing a rare brief push through without exiting
(checked on CLOSE, not the wick).

RESTRICTED TO 2014-06-12 -> 2025-12-31 (clean data only). The 2026
portion of this project's own SILVER_M15_native.csv was just found to
have a severe, likely data-quality-driven spike in extreme single-bar
ranges (328 bars >2% range in 9 months vs 29 in all of 2025, 10 in 2024)
- building a new candidate on top of that would repeat the exact mistake
tonight's Fulcrum investigation already cost real confidence on. Core
Aurelius M15 engine bar-matched 7-for-7 exact on real trades through
Jan 23 2026 (before the suspect data starts) - trustworthy on this
window.

Stop side: sim_cross_trail.py (cp of sim.py) adds an opt-in
stop_at_cross candidate. Exit side: uses sim.py's EXISTING extra_exit
hook (no fork needed) - fires if close has moved back above (sell) or
below (buy) the 50-MA by more than a small buffer, checked every bar,
which is exactly "trail the 50-MA, allow a brief push through, exit on
a real close beyond it."
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
import sim_cross_trail as S
from aurelius_m15_silver_test import load_m15_silver, resample_h4_from_m15

CLEAN_END = pd.Timestamp("2025-12-31")
TRAIL_BUFFER_ATR = 0.15   # "slight distance" above/below the 50-MA


def make_trail50_exit(ctx, buffer_atr):
    m50 = ctx["m50"]
    atr = ctx["atr"]

    def fn(ctx_, i, is_buy, entry_i, entry_px):
        a = atr[i]
        if np.isnan(m50[i]) or np.isnan(a) or a <= 0:
            return False
        buf = buffer_atr * a
        c = ctx_["close"][i]
        return (c < m50[i] - buf) if is_buy else (c > m50[i] + buf)
    return fn


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  avg={pnl.mean():7.3f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


if __name__ == "__main__":
    df15 = load_m15_silver()
    df15 = df15[df15["time"] <= CLEAN_END].reset_index(drop=True)
    h4 = resample_h4_from_m15(df15)
    print(f"SILVER M15, clean window only: {df15['time'].iloc[0]} .. {df15['time'].iloc[-1]} ({len(df15)} bars)\n")

    PS = dict(E.P15, point=0.001)
    ctx = E.build_context(df15, h4, PS)
    n_bars = ctx["n"]
    cutoff_i = int(n_bars * 0.70)

    base_trades = S.simulate(ctx, params=PS)
    print(f"{'='*92}\nBASELINE (shipped Aurelius M15 defaults, unchanged)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in base_trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in base_trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", base_trades)

    p_cand = dict(PS, stop_at_cross=True)
    trail_exit = make_trail50_exit(ctx, TRAIL_BUFFER_ATR)
    cand_trades = S.simulate(ctx, params=p_cand, extra_exit=trail_exit, extra_exit_reason="TRAIL50")
    print(f"\n{'='*92}\nCANDIDATE: stop at 21/50 cross + trail 50-MA exit (buffer={TRAIL_BUFFER_ATR} ATR)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in cand_trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in cand_trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", cand_trades)

    print(f"\n  Honest K=1 (single pre-specified construction, buffer not swept).")
