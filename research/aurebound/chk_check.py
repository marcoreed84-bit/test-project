"""Validate this replica's MT5 indicator ports against GOLD_H4.csv's own
chk_* reference columns (real MT5 indicator output, exported by
ExportBarData.mq5 from the terminal).

What IS chk-validatable for AuRebound:
  * ATR(14)  -> chk_atr14      (the EA's iATR(InpATRPeriod=14) handle)
What is NOT:
  * Stochastic(21,5,5)         - no chk_stoch column exists in the CSV
  * Bollinger(20, 2.0)         - not an MT5 handle at all; AuRebound computes
                                 it itself from Sma()/StdDev() on a_close,
                                 so it is fully specified by the .mq5 source.
                                 Cross-checked here against an independent
                                 pandas rolling population-stddev anyway.
"""
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location(
    "aurebound_engine", os.path.join(HERE, "engine.py"))
aeng = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aeng)

d, _ = aeng.load_h4(start=None)
p = aeng.params()
h = d["high"].values.astype(float)
l = d["low"].values.astype(float)
c = d["close"].values.astype(float)

# ---- ATR(14) vs chk_atr14 -------------------------------------------------
atr = aeng.atr_mt5(h, l, c, 14)
ref = d["chk_atr14"].values.astype(float)
m = ~np.isnan(atr) & np.isfinite(ref) & (np.abs(ref) < 1e6) & (np.arange(len(c)) > 200)
err = np.abs(atr[m] - ref[m])
print(f"ATR(14)  vs chk_atr14 : n={m.sum()} maxerr={err.max():.6f} "
      f"meanerr={err.mean():.8f}  (chk_atr14 is rounded to 2dp in the CSV)")
print(f"         within 0.005 : {(err <= 0.005).mean()*100:.3f}%   "
      f"within 0.01: {(err <= 0.01).mean()*100:.3f}%")

# ---- Bollinger(20, 2.0): replica vs independent pandas re-derivation ------
mid = aeng.sma(c, 20)
sd = aeng.popstd(c, 20)
import pandas as pd
mid2 = pd.Series(c).rolling(20).mean().values
sd2 = pd.Series(c).rolling(20).std(ddof=0).values
mm = ~np.isnan(mid) & ~np.isnan(mid2)
print(f"BB mid   independent  : maxerr={np.abs(mid[mm]-mid2[mm]).max():.3e}")
print(f"BB stdev independent  : maxerr={np.abs(sd[mm]-sd2[mm]).max():.3e}"
      f"   (population stddev, matching mq5 StdDev()'s /period)")

# ---- Stochastic: spec-only, sanity bounds ---------------------------------
main, sig = aeng.stoch_mt5(h, l, c, 21, 5, 5)
v = ~np.isnan(sig)
print(f"Stoch %D (21,5,5)     : NO chk_* column -> spec-ported, not MT5-verified. "
      f"range=[{np.nanmin(sig):.2f},{np.nanmax(sig):.2f}] valid_from_idx={np.argmax(v)}")
