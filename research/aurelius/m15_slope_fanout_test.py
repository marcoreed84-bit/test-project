"""
User asked me to identify what distinguishes a real winning
trend-continuation instance from a failed one, since the plain 21/30/50
+150-confirmed alignment (m15_150confirm_test.py) stayed flat. Two
standard, well-established candidates, tested properly rather than
asserted:

  SLOPE: the 150 EMA should be genuinely SLOPING in the trade direction
  (an established, moving trend), not flat/lazy - a flat 150 with price
  just barely on one side of it is a weak signal by definition.

  FAN-OUT: the MAs should be clearly SEPARATED (21 vs 150 distance in
  ATR units), not compressed together - compression is the classic
  signature of chop/consolidation, the opposite of a clean trend.

Both applied ON TOP of the existing 21/30/50+150-confirmed trigger from
m15_150confirm_test.py. Same real M15 data, same rigor (single-position
sequencing, real spread, walk-forward from the start).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m15_light_stack_test import edge_trigger, realistic_single_position, block_report

if __name__ == "__main__":
    df5 = E.load_m5()
    df = E.resample_m15_from_m5(df5)
    n = len(df)
    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    spread = df["spread"].values.astype(float)
    time = df["time"].values

    atr = E.wilder_atr(high, low, close, 14)
    ema21 = E.ma(close, 21, "ema")
    ema30 = E.ma(close, 30, "ema")
    ema50 = E.ma(close, 50, "ema")
    ema150 = E.ma(close, 150, "ema")

    SLOPE_BARS = 20
    slope150 = np.full(n, np.nan)
    slope150[SLOPE_BARS:] = (ema150[SLOPE_BARS:] - ema150[:-SLOPE_BARS]) / np.where(atr[SLOPE_BARS:] > 0, atr[SLOPE_BARS:], np.nan)
    fanout = (ema21 - ema150) / np.where(atr > 0, atr, np.nan)   # signed - positive when 21 above 150

    base_buy = (close > ema21) & (ema21 > ema30) & (ema30 > ema50) & (close > ema150)
    base_sell = (close < ema21) & (ema21 < ema30) & (ema30 < ema50) & (close < ema150)

    print(f"M15: n={n} bars (~{n/96:.0f} trading days)\n")

    def run(name, sig_buy, sig_sell, holds=((32, "8h"), (64, "16h")), ratios=((0.75, 0.75), (1.0, 0.75), (1.5, 1.0))):
        triggers = edge_trigger(sig_buy, sig_sell)
        print("=" * 70)
        print(f"{name}: {len(triggers)} triggers -> {len(triggers)/(n/96):.2f}/day")
        if len(triggers) < 20:
            print("  too few triggers"); return
        best = None
        for maxhold, label in holds:
            print(f"  --- max hold {maxhold} bars ({label}) ---")
            for tp_atr, sl_atr in ratios:
                trades, skipped = realistic_single_position(triggers, close, high, low, spread, atr, n, tp_atr, sl_atr, maxhold)
                if not trades:
                    print(f"    tp={tp_atr} sl={sl_atr}: 0 trades"); continue
                pnls = np.array([t[2] for t in trades])
                entries = np.array([t[0] for t in trades])
                gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
                pf = gw / gl if gl > 0 else float("inf")
                cutoff = int(n * 0.7)
                is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
                print(f"    tp={tp_atr} sl={sl_atr} (skipped {skipped}): n={len(trades)} net={pnls.sum():.2f} "
                      f"win%={100*(pnls>0).mean():.1f} pf={pf:.3f} IS={is_net:.2f} OOS={oos_net:.2f}")
                if best is None or pnls.sum() > best[0]:
                    best = (pnls.sum(), maxhold, tp_atr, sl_atr, trades)
        if best:
            net, maxhold, tp_atr, sl_atr, trades = best
            print(f"  walk-forward on best cell: maxhold={maxhold} tp={tp_atr} sl={sl_atr} net={net:.2f} n={len(trades)}")
            block_report(trades, n, 5, time)

    for slope_min in (0.5, 1.0, 1.5):
        sig_buy = base_buy & (slope150 >= slope_min)
        sig_sell = base_sell & (slope150 <= -slope_min)
        run(f"SLOPE >= {slope_min}xATR/{SLOPE_BARS}bars", sig_buy, sig_sell)

    for fan_min in (1.0, 2.0, 3.0):
        sig_buy = base_buy & (fanout >= fan_min)
        sig_sell = base_sell & (fanout <= -fan_min)
        run(f"FAN-OUT >= {fan_min}xATR (21-vs-150 distance)", sig_buy, sig_sell)
