"""
Tests whether Aurelius's shipped MID alignment gate (21>50>150>600 + price
vs 2400) is too strict, per direct observation: a real trend day where
price stayed above the MAs all day produced no trade, likely because the
slower 150>600 leg hadn't caught up yet. Compares the shipped MID gate
against the two looser modes already built into engine.py (FAST drops the
150>600 requirement; PRICE drops both 50>150 and 150>600), using the real,
already-validated simulator - same entries/exits/spread logic, only the
align_mode changes. Full history first, then IS/OOS on whichever mode(s)
look different from baseline, since "takes more trades" alone says
nothing about whether those extra trades are actually good ones.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import pandas as pd
from engine import load_m5, load_h4, build_context, P
import sim

df = load_m5()
h4 = load_h4()
n = len(df)
cutoff_i = int(n * 0.70)
cutoff_date = df["time"].iloc[cutoff_i].date()
print(f"GOLD M5: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({n} bars)")
print(f"IS/OOS split at {cutoff_date}\n")

df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
h4_is = h4[h4["time"] < pd.Timestamp(cutoff_date)].reset_index(drop=True)
h4_oos = h4

def run(df_, h4_, align_mode, label):
    p = dict(P)
    p["align_mode"] = align_mode
    ctx = build_context(df_, h4_, params=p)
    trades = sim.simulate(ctx, params=p)
    st = sim.stats(trades)
    rk = sim.risk_stats(trades, ctx)
    print(f"  {label} [{align_mode}]:  n={st['n']:4d}  net={st['net']:9.2f}  PF={st['pf']:5.3f}  "
          f"win%={100*st['win_rate']:5.1f}  closed_dd={rk['closed_dd']:7.2f}  float_dd={rk['float_dd']:7.2f}")
    return trades, st, rk

print("="*100)
print("FULL HISTORY")
print("="*100)
for mode in ("MID", "FAST", "PRICE"):
    p = dict(P)
    p["align_mode"] = mode
    ctx_full = build_context(df, h4, params=p)
    trades = sim.simulate(ctx_full, params=p)
    st = sim.stats(trades)
    rk = sim.risk_stats(trades, ctx_full)
    print(f"  {mode:6s}:  n={st['n']:4d}  net={st['net']:9.2f}  PF={st['pf']:5.3f}  "
          f"win%={100*st['win_rate']:5.1f}  closed_dd={rk['closed_dd']:7.2f}  float_dd={rk['float_dd']:7.2f}")

print("\n" + "="*100)
print("IN-SAMPLE")
print("="*100)
for mode in ("MID", "FAST", "PRICE"):
    run(df_is, h4_is, mode, "IS")

print("\n" + "="*100)
print("OUT-OF-SAMPLE")
print("="*100)
for mode in ("MID", "FAST", "PRICE"):
    run(df_oos, h4_oos, mode, "OOS")
