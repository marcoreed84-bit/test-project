"""
Random-timing null for the one genuinely promising result tonight: Scenario
A entry (21/50 cross confirmed above VWAP and 200-EMA) with a 50-EMA
close-back exit. Full history: n=816, PF=1.249, net%=+27.82%. Before this
goes anywhere, per this project's standing rule, it needs to beat a null of
random entries using the SAME exit mechanism, real spread, and a matched
trade count - not just look good on its own.
"""
import sys, os
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, GOLD_POINT
from meridian_exit_variants_test import classify_ema_exit, pct_pf

np.random.seed(20261015)

df = load_gold_m15()
real_res = classify_ema_exit(df, 50)
real_pf = pct_pf(real_res)
real_net = sum(r["pnl_pct"] for r in real_res)
n_trades = len(real_res)
print(f"REAL: n={n_trades}  PF={real_pf:.3f}  net%={100*real_net:.2f}")

close, high, low = df["close"].values, df["high"].values, df["low"].values
spread = df["spread"].values
m50 = ema(close, 50)
atr = wilder_atr(high, low, close, 14)
n = len(df)
valid_start = 210
valid_idx = np.array([i for i in range(valid_start, n - 1)
                       if not np.isnan(m50[i]) and not np.isnan(atr[i]) and atr[i] > 0])

N_DRAWS = 2000
null_pfs = []
null_nets = []
TIME_CAP = 200
for d in range(N_DRAWS):
    picks = np.random.choice(valid_idx, size=n_trades, replace=False)
    pnls = []
    for entry_i in picks:
        fill_i = entry_i + 1
        if fill_i >= n or np.isnan(atr[fill_i]) or atr[fill_i] <= 0:
            continue
        sc = spread[fill_i] * GOLD_POINT
        entry_px = close[fill_i] + sc
        hard_limit = min(fill_i + TIME_CAP, n - 1)
        exit_px = None
        for k in range(fill_i + 1, hard_limit + 1):
            if np.isnan(m50[k]):
                continue
            if close[k] < m50[k]:
                exit_px = close[k]
                break
        if exit_px is None:
            exit_px = close[hard_limit]
        pnls.append((exit_px - entry_px) / entry_px)
    arr = np.array(pnls)
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    null_pfs.append(pf)
    null_nets.append(arr.sum())
    if (d + 1) % 500 == 0:
        print(f"  {d+1}/{N_DRAWS} draws done", flush=True)

null_pfs = np.array(null_pfs)
null_nets = np.array(null_nets)
pctile_pf = (null_pfs < real_pf).mean() * 100
pctile_net = (null_nets < real_net).mean() * 100
p_value = 1 - pctile_net / 100

print(f"\nRANDOM-TIMING NULL ({N_DRAWS} draws), same 50-EMA exit, real spread, matched n={n_trades}")
print(f"  null PF:  median={np.median(null_pfs):.3f}  p95={np.percentile(null_pfs,95):.3f}  p99={np.percentile(null_pfs,99):.3f}")
print(f"  null net%: median={100*np.median(null_nets):.2f}  p95={100*np.percentile(null_nets,95):.2f}  p99={100*np.percentile(null_nets,99):.2f}")
print(f"  real PF {real_pf:.3f} sits at the {pctile_pf:.1f}th percentile of {N_DRAWS} draws (by PF)")
print(f"  real net% {100*real_net:.2f} sits at the {pctile_net:.1f}th percentile of {N_DRAWS} draws (by net%)")
print(f"  p-value (net%) = {p_value:.4f}")
