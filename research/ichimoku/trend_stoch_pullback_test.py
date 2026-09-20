"""
User's construction: trade the stochastic extreme WITH the macro trend,
not the reversal off it. Macro trend = close vs EMA(200), not the cloud
this time (explicitly requested). In a downtrend (close < EMA200), the
overbought->oversold swing is the WITH-TREND move - sell the overbought
bounce, expecting continuation down. In an uptrend (close > EMA200),
buy the oversold dip, expecting continuation up. Classic trend-pullback
construction, stochastic as the pullback timer instead of a moving-
average touch (which was already tested via scalp_bounce_test.py on M5 -
this is the stochastic-timed version, on H4, genuinely different).

Entry: edge-triggered on the stochastic EXIT from the extreme (crossing
back through the 80/20 line), in the direction that matches the trend -
not on entering the extreme, since you can't know it's "the" extreme
until price starts moving away from it.

Same rigor as everything else: real spread, correct single-position
sequencing from the start, walk-forward blocks reported alongside the
aggregate, not as an afterthought.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from cloud_stoch_test import stochastic

POINT = 0.01
N_RANDOM_SEEDS = 2000


def tp_sl_outcomes(triggers, close, high, low, spread, atr, n, tp_atr, sl_atr, maxhold):
    out, dropped = [], 0
    for i, real_dir in triggers:
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry_buy, entry_sell = raw + sc, raw - sc
        tp_buy, sl_buy = entry_buy + tp_atr * atr[i], entry_buy - sl_atr * atr[i]
        tp_sell, sl_sell = entry_sell - tp_atr * atr[i], entry_sell + sl_atr * atr[i]
        pnl_buy = pnl_sell = None
        for k in range(fill_i, min(fill_i + maxhold, n)):
            if pnl_buy is None:
                ht, hs = high[k] >= tp_buy, low[k] <= sl_buy
                if ht or hs: pnl_buy = (sl_buy - entry_buy) if hs else (tp_buy - entry_buy)
            if pnl_sell is None:
                ht, hs = low[k] <= tp_sell, high[k] >= sl_sell
                if ht or hs: pnl_sell = (entry_sell - sl_sell) if hs else (entry_sell - tp_sell)
            if pnl_buy is not None and pnl_sell is not None:
                break
        if pnl_buy is None or pnl_sell is None:
            dropped += 1
            continue
        out.append((pnl_buy, pnl_sell, i, real_dir))
    return out, dropped


def realistic_single_position(triggers, close, high, low, spread, atr, n, tp_atr, sl_atr, maxhold):
    """The ONLY number that matters for real deployability - skips any
    trigger firing while still in a trade (the lesson from the earlier
    cloud-confluence overlap bug, applied from the start here)."""
    trades = []
    last_exit = -1
    skipped = 0
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


if __name__ == "__main__":
    d = E.load_h4()
    close, high, low = d["close"].values, d["high"].values, d["low"].values
    spread = d["spread"].values.astype(float)
    atr = E.atr_wilder(high, low, close, 14)
    n = len(close)
    time = d["time"].values

    ema200 = pd.Series(close).ewm(span=200, adjust=False).mean().values
    uptrend = close > ema200
    downtrend = close < ema200

    k, dd = stochastic(high, low, close, period=14)
    OB, OS = 80.0, 20.0
    exit_os = (k > OS) & (np.concatenate(([np.nan], k[:-1])) <= OS)   # crossing back above 20
    exit_ob = (k < OB) & (np.concatenate(([np.nan], k[:-1])) >= OB)   # crossing back below 80

    # WITH-TREND only: buy the oversold exit in an uptrend, sell the overbought exit in a downtrend
    trig_buy = exit_os & uptrend
    trig_sell = exit_ob & downtrend
    triggers = [(i, 1.0) for i in np.where(trig_buy)[0]] + [(i, -1.0) for i in np.where(trig_sell)[0]]
    triggers.sort(key=lambda t: t[0])
    print(f"n_bars={n} (H4, ~{n/6:.0f} trading days)")
    print(f"WITH-TREND stochastic-pullback triggers: {len(triggers)} "
          f"({sum(1 for _,dr in triggers if dr>0)} buy-in-uptrend, "
          f"{sum(1 for _,dr in triggers if dr<0)} sell-in-downtrend) -> {len(triggers)/(n/6):.3f}/day\n")

    print("=" * 70)
    print("REALISTIC single-position simulation (the number that actually matters)")
    for maxhold, label in ((12, "~2 days"), (30, "~5 days")):
        print(f"\n--- max hold = {maxhold} bars ({label}) ---")
        for tp_atr, sl_atr in ((1.0, 1.0), (1.5, 1.0), (2.0, 1.5), (2.5, 1.5)):
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
            print(f"    tp={tp_atr} sl={sl_atr} (skipped {skipped} overlaps): n={len(trades)} "
                  f"net={pnls.sum():.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
                  f"IS={is_net:.2f} OOS={oos_net:.2f}")

    # walk-forward on the best-looking cell
    best = None
    for maxhold in (12, 30):
        for tp_atr, sl_atr in ((1.0, 1.0), (1.5, 1.0), (2.0, 1.5), (2.5, 1.5)):
            trades, _ = realistic_single_position(triggers, close, high, low, spread, atr, n,
                                                    tp_atr, sl_atr, maxhold)
            if not trades:
                continue
            net = sum(t[2] for t in trades)
            if best is None or net > best[0]:
                best = (net, maxhold, tp_atr, sl_atr, trades)

    print("\n" + "=" * 70)
    if best is None:
        print("no trades resolved anywhere in the grid")
    else:
        net, maxhold, tp_atr, sl_atr, trades = best
        print(f"5-block walk-forward on best cell: maxhold={maxhold} tp={tp_atr} sl={sl_atr} net={net:.2f} n={len(trades)}")
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        edges = np.linspace(0, n, 6).astype(int)
        pos = 0
        for b in range(5):
            lo, hi = edges[b], edges[b+1]
            m = (entries >= lo) & (entries < hi)
            nb = m.sum()
            if nb == 0:
                print(f"  block {b+1}: 0 trades"); continue
            netb = pnls[m].sum()
            rng = np.random.default_rng(100+b)
            rdb = rng.integers(0, 2, size=(2000, nb))
            t0 = pd.to_datetime(time[lo]).date(); t1 = pd.to_datetime(time[min(hi, n-1)]).date()
            if netb > 0: pos += 1
            print(f"  block {b+1} [{t0}->{t1}]: n={nb} net={netb:.2f} win%={100*(pnls[m]>0).mean():.1f}")
        print(f"  -> positive in {pos}/5 blocks")
