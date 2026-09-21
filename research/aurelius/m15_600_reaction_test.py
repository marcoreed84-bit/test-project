"""
New construction, not yet tested: trade the CONFIRMED resolution at the
600 EMA specifically (the slow trend MA from the user's chart example),
not the full 5-MA alignment stack. Two symmetric triggers:

  BREAKTHROUGH: price was on one side of the 600, tests it, then closes
  clearly through to the other side by a real margin (not just a touch).
  REJECTION: price tests the 600 from one side, then closes back away
  from it by a real margin (a genuine bounce, not just proximity).

Both are "wait for it to actually happen, then trade the resolved
direction" - the principle just confirmed as sound, applied to a single
significant level instead of a multi-MA stack. PATIENT exit (wide
targets, real max-hold measured in days) since that's the second
ingredient distinguishing what already works (Aurelius/Slipstream) from
every short-hold construction rejected today.

Real M15 data (resampled from validated M5), real spread, correct
single-position sequencing, walk-forward from the start.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m15_light_stack_test import realistic_single_position, block_report

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
    ema600 = E.ma(close, 600, "ema")

    LOOKBACK = 12          # bars to look back for "was on the other side"
    TOUCH_TOL = 0.30        # how close counts as "tested" the level, xATR
    CONFIRM = 0.30           # how far past/away counts as a real resolution, xATR

    n_bars = n
    break_up = np.zeros(n_bars, dtype=bool)
    break_dn = np.zeros(n_bars, dtype=bool)
    reject_up = np.zeros(n_bars, dtype=bool)   # rejected DOWN off the 600 (was below, bounced back down)
    reject_dn = np.zeros(n_bars, dtype=bool)   # rejected UP off the 600 (was above, bounced back up)

    for i in range(LOOKBACK, n_bars):
        if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(ema600[i]):
            continue
        tol = TOUCH_TOL * atr[i]
        conf = CONFIRM * atr[i]
        win = range(max(0, i - LOOKBACK + 1), i)   # excludes bar i itself
        was_below = any(high[j] <= ema600[j] + tol for j in win)
        was_above = any(low[j] >= ema600[j] - tol for j in win)
        touched = low[i] <= ema600[i] + tol and high[i] >= ema600[i] - tol
        # breakthrough: was below, now clearly above (or vice versa)
        if was_below and close[i] > ema600[i] + conf:
            break_up[i] = True
        if was_above and close[i] < ema600[i] - conf:
            break_dn[i] = True
        # rejection: touched from below, closed back below by a margin
        if touched and low[i] <= ema600[i] + tol and close[i] < ema600[i] - conf and was_below:
            reject_dn[i] = True
        if touched and high[i] >= ema600[i] - tol and close[i] > ema600[i] + conf and was_above:
            reject_up[i] = True

    def edge(sig):
        return sig & ~np.concatenate(([False], sig[:-1]))

    break_up, break_dn = edge(break_up), edge(break_dn)
    reject_up, reject_dn = edge(reject_up), edge(reject_dn)

    print(f"M15: n={n_bars} bars (~{n_bars/96:.0f} trading days)\n")
    print(f"breakthrough-up: {break_up.sum()}, breakthrough-down: {break_dn.sum()}")
    print(f"rejection-up (bounced UP off 600): {reject_up.sum()}, rejection-down (bounced DOWN off 600): {reject_dn.sum()}\n")

    def run(name, sig_buy, sig_sell):
        trig = [(i, 1.0) for i in np.where(sig_buy)[0]] + [(i, -1.0) for i in np.where(sig_sell)[0]]
        trig.sort(key=lambda t: t[0])
        print("=" * 70)
        print(f"{name}: {len(trig)} triggers -> {len(trig)/(n_bars/96):.3f}/day")
        if len(trig) < 20:
            print("  too few triggers"); return
        best = None
        # PATIENT exits: wide targets, real multi-day holds
        for maxhold, label in ((96, "1day"), (288, "3day"), (480, "5day")):
            print(f"  --- max hold {maxhold} bars ({label}) ---")
            for tp_atr, sl_atr in ((2.0, 1.5), (3.0, 2.0), (4.0, 2.5)):
                trades, skipped = realistic_single_position(trig, close, high, low, spread, atr, n_bars, tp_atr, sl_atr, maxhold)
                if not trades:
                    print(f"    tp={tp_atr} sl={sl_atr}: 0 trades"); continue
                pnls = np.array([t[2] for t in trades])
                entries = np.array([t[0] for t in trades])
                gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
                pf = gw / gl if gl > 0 else float("inf")
                cutoff = int(n_bars * 0.7)
                is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
                print(f"    tp={tp_atr} sl={sl_atr} (skipped {skipped}): n={len(trades)} net={pnls.sum():.2f} "
                      f"win%={100*(pnls>0).mean():.1f} pf={pf:.3f} IS={is_net:.2f} OOS={oos_net:.2f}")
                if best is None or pnls.sum() > best[0]:
                    best = (pnls.sum(), maxhold, tp_atr, sl_atr, trades)
        if best:
            net, maxhold, tp_atr, sl_atr, trades = best
            print(f"  walk-forward on best cell: maxhold={maxhold} tp={tp_atr} sl={sl_atr} net={net:.2f} n={len(trades)}")
            block_report(trades, n_bars, 5, time)

    run("BREAKTHROUGH (trade the confirmed break, with the new side)", break_up, break_dn)
    run("REJECTION (trade the confirmed bounce, back toward the origin side)", reject_up, reject_dn)
