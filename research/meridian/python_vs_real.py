"""
Step 2: check the Python research's predictions against the real v1.02 fills,
on the SAME window, like-for-like.

The header's v1.02 case is Python-only, full history 2023-01..2026-08:
  meridian_ma_variant_test.py        150 EMA + S/R (v1.01 as shipped): net 3253.93, floatDD 14.9% of net
  meridian_slow_confirm_sweep_test.py 250 SMA + S/R (v1.02):           net 3432.72, PF 1.357, floatDD 11.1%,
                                                                     walk-forward 5/5, random-dir pct 100.0
The real reports cover only 2026-01-01..2026-09-21 on a 10,000 ZAR account, so
a real-vs-header before/after delta is NOT like-for-like. Instead this re-runs
the exact research construction (engine.build_context + the same raw-event /
confirm / VWAP / S/R masking as meridian_slow_confirm_sweep_test.build_and_run,
through m5_stack_variants_fixed_test.sim_filtered_entries) and keeps only
trades entered inside the real window - engine's GOLD_M5.csv ends 2026-08-14,
so the real trades are cut at the same date - for the two configs that were
actually run for real:

  Backtest_2 = v1.02: 250 SMA confirm + VWAP + S/R 0.5, stop 2.5
  Backtest_1 = stale binary: 150 EMA confirm + VWAP, NO S/R, stop 2.5
               (see validate.py - 99.6% entry-bar match on that config)
"""
import os
import sys

import numpy as np
import pandas as pd

AUR = "/home/user/test-project/research/aurelius"
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import report as R  # noqa: E402

CUT = pd.Timestamp("2026-08-14 23:55")
W0 = pd.Timestamp("2026-01-01")


def python_model(df5, h4, ctx, period, method, use_sr, E, sim_filtered_entries):
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap, srb, srs = ctx["vwap"], ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]
    m21, m50, ms = E.ma(close, 21, "ema"), E.ma(close, 50, "ema"), E.ma(close, period, method)
    above = m21 > m50
    ap = np.concatenate(([False], above[:-1]))
    ev = sorted([(i, 1.0) for i in np.where(above & ~ap)[0]] + [(i, -1.0) for i in np.where((~above) & ap)[0]],
                key=lambda e: e[0])
    ok = np.zeros(n, dtype=bool)
    for i, d in ev:
        cs = close[i] > ms[i] if d > 0 else close[i] < ms[i]
        cv = close[i] > vwap[i] if d > 0 else close[i] < vwap[i]
        if np.isnan(ms[i]) or not (cs and cv):
            continue
        sr = srb[i] if d > 0 else srs[i]
        ok[i] = not (use_sr and sr >= 0.0 and sr < 0.50)
    tr = sim_filtered_entries(ev, ok, close, high, low, spread, atr, n, 2.5)
    t = df5["time"].values
    return [(pd.Timestamp(t[i]), pnl) for i, _, pnl, _ in tr]


def summ(p):
    p = np.array(p)
    gp, gl = p[p > 0].sum(), -p[p < 0].sum()
    return f"n={len(p):4d} net=${p.sum():8.2f} PF={gp/gl:.3f} win={100*(p>0).mean():.1f}%"


if __name__ == "__main__":
    cwd = os.getcwd()
    os.chdir(AUR)
    sys.path.insert(0, AUR)
    import engine as E                                                   # noqa: E402
    from m5_stack_variants_fixed_test import sim_filtered_entries        # noqa: E402
    df5, h4 = E.load_m5(), E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    os.chdir(cwd)
    out = {}
    for lbl, (per, meth, sr), path in [("v1.02 (250 SMA + S/R)", (250, "sma", True), R.MERIDIAN_BT2),
                                        ("BT1 binary (150 EMA, no S/R)", (150, "ema", False), R.MERIDIAN_BT1)]:
        py = python_model(df5, h4, ctx, per, meth, sr, E, sim_filtered_entries)
        full = [p for _, p in py]
        win = [p for t, p in py if W0 <= t <= CUT]
        real = [x["pnl_usd"] for x in R.load(path) if pd.Timestamp(x["entry_time"]) <= CUT]
        out[lbl] = (win, real)
        print(f"== {lbl}")
        print(f"   PYTHON full history 2023-01..2026-08 : {summ(full)}")
        print(f"   PYTHON 2026-01-01..2026-08-14        : {summ(win)}")
        print(f"   REAL   2026-01-01..2026-08-14        : {summ(real)}")
    (pw2, rr2), (pw1, rr1) = out["v1.02 (250 SMA + S/R)"], out["BT1 binary (150 EMA, no S/R)"]
    print("\nsame-window delta BT1-binary -> v1.02:")
    print(f"   PYTHON predicted: net {sum(pw1):.2f} -> {sum(pw2):.2f} ({100*(sum(pw2)/sum(pw1)-1):+.1f}%), "
          f"trades {len(pw1)} -> {len(pw2)}")
    print(f"   REAL            : net {sum(rr1):.2f} -> {sum(rr2):.2f} ({100*(sum(rr2)/sum(rr1)-1):+.1f}%), "
          f"trades {len(rr1)} -> {len(rr2)}")
