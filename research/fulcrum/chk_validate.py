"""
Bar-for-bar validation of every indicator array this engine builds against
MT5's OWN reference columns in the real CSV export (chk_ema21 / chk_ema150 /
chk_atr14 / chk_macd, computed by the terminal itself on the same bars).

This is the only validation target that exists for Fulcrum right now: NO real
Fulcrum MT5 backtest report (.xlsx) has been uploaded, so nothing here claims
report-level agreement - only that the indicator math underneath the gate is
the terminal's own.

The chk_* columns are written to 2 decimals (meta_digits=2), so "match" means
|python - mt5| <= 0.005 + fp slack; the match rate at that tolerance is what
gets reported, not a pass/fail assertion.
"""
import numpy as np
import pandas as pd

import engine as E

TOL = 0.005 + 1e-9        # the CSV's own rounding granularity


def rate(mine, ref, valid):
    m = valid & np.isfinite(mine) & np.isfinite(ref) & (np.abs(ref) < 1e6)
    d = np.abs(mine[m] - ref[m])
    return dict(n=int(m.sum()), pct=100.0 * float((d <= TOL).mean()),
                maxdiff=float(d.max()), meandiff=float(d.mean()))


def report(tag, df, warm):
    c = df["close"].values.astype(float)
    h = df["high"].values.astype(float)
    l = df["low"].values.astype(float)
    valid = np.arange(len(df)) >= warm
    print(f"\n=== {tag}  (n={len(df)} bars, {df['time'].iloc[0]} .. {df['time'].iloc[-1]}) ===")

    for per, col in [(21, "chk_ema21"), (150, "chk_ema150")]:
        if col not in df:
            continue
        print(f"  EMA{per:<5d} vs {col:12s}: {rate(E.ema(c, per), df[col].values.astype(float), valid)}")

    # MT5's iATR on this broker is a plain SMA(14) of True Range, NOT Wilder -
    # the EAs' own v2.02/v1.36 finding. Both are checked so the claim is
    # evidenced here rather than taken on trust: chk_atr14 should match the SMA
    # form, and the EA deliberately uses the Wilder form instead
    # (ComputeWilderATR, Fulcrum_EA.mq5:991) for every gate and for the stop.
    ref_atr = df["chk_atr14"].values.astype(float)
    tr = np.empty(len(c))
    tr[0] = h[0] - l[0]
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])])
    atr_sma = pd.Series(tr).rolling(14).mean().values
    print(f"  ATR14 SMA-of-TR   vs chk_atr14 : {rate(atr_sma, ref_atr, valid)}")
    print(f"  ATR14 Wilder (EA) vs chk_atr14 : {rate(E.wilder_atr(h, l, c, 14), ref_atr, valid)}"
          "   <- expected NOT to match; the EA uses Wilder on purpose")

    if "chk_macd" in df:
        macd = E.ema(c, 12) - E.ema(c, 26)
        print(f"  MACD(12,26) main  vs chk_macd  : {rate(macd, df['chk_macd'].values.astype(float), valid)}")


if __name__ == "__main__":
    df5 = E.load_m5()
    report("GOLD M5 (native export)", df5, warm=2460)

    # M15 is derived from M5 by the same lossless 3-bar resample Aurelius_M15
    # uses (engine.resample_m15_from_m5). The export has no chk_* columns for
    # M15, so the check that matters is that the resample is exact: every M15
    # bar must be the O/H/L/C of its three M5 bars.
    df15 = E.resample_m15_from_m5(df5)
    d = df5.set_index("time")
    grp = d.resample("15min")
    ok_o = np.isclose(df15["open"].values, grp["open"].first().dropna().values).mean()
    ok_h = np.isclose(df15["high"].values, grp["high"].max().dropna().values).mean()
    ok_l = np.isclose(df15["low"].values, grp["low"].min().dropna().values).mean()
    ok_c = np.isclose(df15["close"].values, grp["close"].last().dropna().values).mean()
    print(f"\n=== GOLD M15 (resampled from M5, {len(df15)} bars) ===")
    print(f"  resample exactness O/H/L/C: {100*ok_o:.4f}/{100*ok_h:.4f}/"
          f"{100*ok_l:.4f}/{100*ok_c:.4f} %")
    # And the indicator math is the identical code path, re-run on those bars:
    # ATR/EMA are validated above on M5; here we confirm they are finite and
    # monotone-warmed on the M15 series so nothing silently NaNs the gate.
    c15 = df15["close"].values.astype(float)
    for per, meth in [(30, "ema"), (50, "ema"), (150, "ema"), (200, "smma"), (1200, "ema")]:
        a = E.ma(c15, per, meth)
        print(f"  MA{per:<5d} {meth:5s}: first finite at bar {int(np.argmax(np.isfinite(a)))}, "
              f"finite from there on = {bool(np.isfinite(a[int(np.argmax(np.isfinite(a))):]).all())}")
    atr15 = E.wilder_atr(df15["high"].values.astype(float), df15["low"].values.astype(float), c15, 14)
    print(f"  ATR14 Wilder : first finite at bar {int(np.argmax(np.isfinite(atr15)))}, "
          f"median {np.nanmedian(atr15):.3f}")
