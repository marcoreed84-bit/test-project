"""
User's ask: on M15, a LIGHTER alignment stack than Aurelius_M15's real
5-MA requirement (21/50/150/600/2400, where "21" is actually 30 - see
today's chart-mismatch finding) - just three fast MAs (21, 30, 50)
in order, for shorter trades. Genuinely new: a real, separate 21 EMA
doesn't currently exist as a signal anywhere in Aurelius_M15 (the slot
that used to be 21 was widened to 30 and validated that way), so this
tests whether adding it back alongside 30/50 as a LIGHTER 3-MA stack
(dropping the 150/600/2400 slow-trend layers) finds something for
shorter holds.

Real M15 data (lossless resample from the validated real M5 CSV, same
convention as Aurelius_M15's own P15), real spread, correct single-
position sequencing from the start, walk-forward alongside the
aggregate - the standard this session settled on after several
earlier candidates looked good only until checked properly.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E

POINT = E.POINT
N_RANDOM_SEEDS = 2000


def edge_trigger(sig_buy, sig_sell):
    tb = sig_buy & ~np.concatenate(([False], sig_buy[:-1]))
    ts = sig_sell & ~np.concatenate(([False], sig_sell[:-1]))
    trig = [(i, 1.0) for i in np.where(tb)[0]] + [(i, -1.0) for i in np.where(ts)[0]]
    trig.sort(key=lambda t: t[0])
    return trig


def realistic_single_position(triggers, close, high, low, spread, atr, n, tp_atr, sl_atr, maxhold):
    trades, last_exit, skipped = [], -1, 0
    for i, d in triggers:
        if i < last_exit:
            skipped += 1
            continue
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        is_buy = d > 0
        entry = raw + sc if is_buy else raw - sc
        tp = entry + tp_atr * atr[i] if is_buy else entry - tp_atr * atr[i]
        sl = entry - sl_atr * atr[i] if is_buy else entry + sl_atr * atr[i]
        eb, pnl = None, None
        for k in range(fill_i, min(fill_i + maxhold, n)):
            if is_buy:
                if high[k] >= tp: eb, pnl = k, tp - entry; break
                if low[k] <= sl: eb, pnl = k, sl - entry; break
            else:
                if low[k] <= tp: eb, pnl = k, entry - tp; break
                if high[k] >= sl: eb, pnl = k, entry - sl; break
        if eb is None:
            continue
        trades.append((i, eb, pnl))
        last_exit = eb
    return trades, skipped


def block_report(trades, n, n_blocks=5, time=None):
    if not trades:
        print("    no trades"); return
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    edges = np.linspace(0, n, n_blocks + 1).astype(int)
    pos = 0
    for b in range(n_blocks):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            print(f"    block {b+1}: 0 trades"); continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
        t0 = pd.to_datetime(time[lo]).date(); t1 = pd.to_datetime(time[min(hi, n-1)]).date()
        print(f"    block {b+1} [{t0}->{t1}]: n={nb} net={netb:.2f} win%={100*(pnls[m]>0).mean():.1f}")
    print(f"    -> positive in {pos}/{n_blocks} blocks")


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
    ema30 = E.ma(close, 30, "ema")   # the real value behind Aurelius_M15's "InpP21"
    ema50 = E.ma(close, 50, "ema")

    print(f"M15 (resampled from real M5): n={n} bars (~{n/96:.0f} trading days)\n")

    # LIGHT 3-MA alignment: close above/below all three, stacked in order -
    # a genuinely lighter requirement than the real 5-MA stack (drops
    # 150/600/2400 confirmation)
    sig_buy = (close > ema21) & (ema21 > ema30) & (ema30 > ema50)
    sig_sell = (close < ema21) & (ema21 < ema30) & (ema30 < ema50)
    triggers = edge_trigger(sig_buy, sig_sell)
    print(f"3-MA (21/30/50) alignment triggers: {len(triggers)} -> {len(triggers)/(n/96):.2f}/day\n")

    print("=" * 70)
    print("SHORT-HOLD grid (M15 bars: 4=1h, 8=2h, 16=4h, 32=8h)")
    best = None
    for maxhold, label in ((4, "1h"), (8, "2h"), (16, "4h"), (32, "8h")):
        print(f"\n--- max hold = {maxhold} bars ({label}) ---")
        for tp_atr, sl_atr in ((0.5, 0.5), (0.75, 0.75), (1.0, 0.75), (1.5, 1.0)):
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

    print("\n" + "=" * 70)
    if best is None:
        print("no trades resolved anywhere in the grid")
    else:
        net, maxhold, tp_atr, sl_atr, trades = best
        print(f"5-block walk-forward on best cell: maxhold={maxhold} tp={tp_atr} sl={sl_atr} net={net:.2f} n={len(trades)}")
        block_report(trades, n, 5, time)
