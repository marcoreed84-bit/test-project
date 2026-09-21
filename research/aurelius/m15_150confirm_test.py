"""
Direct follow-up to m15_light_stack_test.py: adds a 150-EMA confirmation
requirement on top of the 21/30/50 alignment - only take the trigger when
price is ALSO clearly on the trend side of the slower 150 EMA at that
moment, per the user's specific chart example (a real M15 chart showing
the 3-MA stack aligned below the 150 EMA, with a real, large winning move
after). Same real M15 data (resampled from real M5), same rigor.
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

    print(f"M15: n={n} bars (~{n/96:.0f} trading days)\n")

    sig_buy = (close > ema21) & (ema21 > ema30) & (ema30 > ema50) & (close > ema150)
    sig_sell = (close < ema21) & (ema21 < ema30) & (ema30 < ema50) & (close < ema150)
    triggers = edge_trigger(sig_buy, sig_sell)
    print(f"3-MA (21/30/50) + 150-confirmed triggers: {len(triggers)} -> {len(triggers)/(n/96):.2f}/day\n")

    best = None
    for maxhold, label in ((16, "4h"), (32, "8h"), (64, "16h"), (96, "24h")):
        print(f"--- max hold = {maxhold} bars ({label}) ---")
        for tp_atr, sl_atr in ((0.5, 0.5), (0.75, 0.75), (1.0, 0.75), (1.5, 1.0), (2.0, 1.5)):
            trades, skipped = realistic_single_position(triggers, close, high, low, spread, atr, n,
                                                          tp_atr, sl_atr, maxhold)
            if not trades:
                print(f"    tp={tp_atr} sl={sl_atr}: 0 trades"); continue
            pnls = np.array([t[2] for t in trades])
            entries = np.array([t[0] for t in trades])
            gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
            pf = gw / gl if gl > 0 else float("inf")
            cutoff = int(n * 0.7)
            is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
            print(f"    tp={tp_atr} sl={sl_atr} (skipped {skipped}): n={len(trades)} "
                  f"net={pnls.sum():.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
                  f"IS={is_net:.2f} OOS={oos_net:.2f}")
            if best is None or pnls.sum() > best[0]:
                best = (pnls.sum(), maxhold, tp_atr, sl_atr, trades)
        print()

    if best:
        net, maxhold, tp_atr, sl_atr, trades = best
        print(f"5-block walk-forward on best cell: maxhold={maxhold} tp={tp_atr} sl={sl_atr} net={net:.2f} n={len(trades)}")
        block_report(trades, n, 5, time)
