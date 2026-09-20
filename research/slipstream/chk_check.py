"""Validate THIS engine's indicator ports against the CSV's own MT5-computed
chk_* reference columns before trusting any Slipstream number downstream.
Same discipline as research/ichimoku/chk_validate.py, re-run here because
Slipstream reads MT5's native iATR() handle (Ichimoku_EA hand-rolled Wilder),
so which ATR form iATR actually returns is load-bearing for this EA."""
import importlib.util
import os
import sys

import numpy as np
import pandas as pd

_spec = importlib.util.spec_from_file_location(
    "engine_slipstream", os.path.join(os.path.dirname(os.path.abspath(__file__)), "engine.py"))
E = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E)

d, i0 = E.load_h4()
print(f"CSV rows={len(d)}  range {d['time'].iloc[0]} -> {d['time'].iloc[-1]}")
print(f"first tradable index (2013-01-01) = {i0}  -> {len(d)-i0} tradable bars")

c = d["close"].values.astype(float)
h = d["high"].values.astype(float)
l = d["low"].values.astype(float)
ok = d.index >= 400          # skip warmup + the DBL_MAX garbage in row 0..N

for n, col in [(3, "chk_ema3"), (21, "chk_ema21"), (150, "chk_ema150")]:
    mine = E.ema_mt5(c, n)
    ref = d[col].values.astype(float)
    m = ok & np.isfinite(ref) & (np.abs(ref) < 1e6)
    diff = np.abs(mine[m] - ref[m])
    print(f"EMA{n:4d}: n={m.sum()} maxdiff={diff.max():.6f} meandiff={diff.mean():.6f}")

ref = d["chk_atr14"].values.astype(float)
m = ok & np.isfinite(ref) & (np.abs(ref) < 1e6)
mine_sma = E.atr_mt5(h, l, c, 14)
mine_wil = E.atr_wilder(h, l, c, 14)
for name, mine in (("iATR port (SMA of TR)", mine_sma), ("Wilder (NOT used)", mine_wil)):
    dd = np.abs(mine[m] - ref[m])
    print(f"ATR14 {name:24s}: n={m.sum()} maxdiff={dd.max():.6f} meandiff={dd.mean():.6f}")

# SMA14 = the BB midline. No chk column exists; assert the port is a plain SMA.
mid = E.sma(c, 14)
manual = np.array([np.mean(c[i - 13:i + 1]) for i in range(2000, 2100)])
print(f"SMA14 (BB midline): maxdiff vs explicit mean over 100 bars = "
      f"{np.abs(mid[2000:2100] - manual).max():.12f}  [no chk_* column exists]")
print("Stochastic(14,3,3)/(21,5,5): NO chk_* reference column in the CSV - "
      "ported per MT5 Stochastic.mq5, NOT independently verified against MT5.")
