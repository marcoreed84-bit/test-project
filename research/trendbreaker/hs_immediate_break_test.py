"""
NARROWER follow-up to hs_early_exit_break_test.py (2026-10-08, user's own
distinction): that test applied the neckline-re-break check for the WHOLE
life of the trade (arm on first touch, check again any time it touches
later) and found a real loss - net% roughly halved - because most of the
damage came from clipping winners during a NORMAL mid-trade pullback, long
after entry.

The user is describing something narrower: the retest happens, the trade
fills, and price "immediately" (next couple bars) comes back down through
the neckline - a fast failure right at the start of the trade, not a later
pullback. hs_sim_immediate_break.py restricts the identical check to only
arm within IMMEDIATE_MAX_BARS=3 bars of fill; once that window passes with
no touch, the check disarms permanently for that trade - a later pullback
is never touched by this rule at all. Same 0.30xATR threshold, not re-tuned.
Honest K=1 for this specific construction (separate from the K already
spent on the "anytime" version, which is being replaced, not stacked).
"""
import sys

sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import hs_sim_immediate_break as HS

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
POINT = 0.01
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")


def load_gold_m15():
    df = pd.read_csv(f"{DATA_DIR}/GOLD_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df[["time", "open", "high", "low", "close", "spread"]]


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl_pct"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  %PF={pf(pnl):6.3f}  net%={100*pnl.sum():7.2f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


if __name__ == "__main__":
    df = load_gold_m15()
    print(f"Real GOLD M15: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars)")
    cutoff_time = df["time"].iloc[int(len(df) * 0.70)]
    print(f"Walk-forward cutoff (70%): {cutoff_time}")
    print(f"IMMEDIATE_MAX_BARS = {HS.IMMEDIATE_MAX_BARS}\n")

    p_base = dict(HS.DEFAULTS, point=POINT)
    p_cand = dict(HS.DEFAULTS, point=POINT, use_early_exit=True)

    real_trades = HS.simulate(df, p_base)
    cand_trades = HS.simulate(df, p_cand)

    print(f"{'='*92}\nCANDIDATE: shipped H&S + IMMEDIATE-ONLY neckline-re-break exit "
          f"(first {HS.IMMEDIATE_MAX_BARS} bars after fill only)\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in cand_trades if df["time"].iloc[t["entry_i"]] < cutoff_time]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in cand_trades if df["time"].iloc[t["entry_i"]] >= cutoff_time])):
        report(label, trs)

    print(f"\n{'='*92}\nFor reference: shipped H&S (no early-exit rule)\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in real_trades if df["time"].iloc[t["entry_i"]] < cutoff_time]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in real_trades if df["time"].iloc[t["entry_i"]] >= cutoff_time])):
        report(label, trs)

    print(f"\n{'='*92}\nFor reference: the broader 'anytime' version already tested "
          f"(hs_early_exit_break_test.py) - REJECTED, net roughly halved\n{'='*92}")
    print("  see prior results: OOS net% 38.34 -> 19.26, %PF 1.428 -> 1.254, win% 47.4 -> 36.0")

    n_cand_ee = sum(1 for t in cand_trades if t["reason"] == "EARLY_EXIT_BROKE")
    print(f"\nImmediate-only rule actually fired (EARLY_EXIT_BROKE) on {n_cand_ee}/{len(cand_trades)} "
          f"of the candidate's trades (full history).")
