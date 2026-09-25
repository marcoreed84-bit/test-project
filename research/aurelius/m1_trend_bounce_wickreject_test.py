"""
M1 trend+bounce (Aurelius's own real aligned+pullback trigger, same as
m1_scalp_test.py) + Ratchet's real, validated wick-reject filter
(Ratchet_EA.mq5 line 2654-2660: wick INTO the 21 on the trigger bar must be
>= InpWickRejectRatio(1.5) x body) added on top, to see whether a real,
already-validated quality filter pushes m1_scalp_test.py's marginal best
cell (PF 1.118, only 2/4 walk-forward blocks positive) into something
robust - rather than inventing a new untested filter.

Wick-reject is computed against the 50 MA touch bar (the same bar the
pullback condition is evaluated on), matching Ratchet's own convention of
checking the trigger candle's rejection wick.

High-liquidity hour filter (hours 4,16,17,18 by real M1 tick_volume,
established in m1_scalp_test.py) kept, since removing it wasn't tested and
this is an ADD-a-filter test, not a redesign.

Sequential, single-position, walk-forward, no lookahead - same discipline
as every other script in this repo.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E

DATA_DIR = E.DATA_DIR
POINT = E.POINT


def load_m1():
    df = pd.read_csv(f"{DATA_DIR}/GOLD_M1.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    return df


def sim(triggers, close, high, low, spread, atr, n, tp_atr, sl_atr, maxhold):
    trades = []
    last_exit = -1
    for i, d in triggers:
        if i < last_exit:
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
    return trades


def report(label, trades, n, days):
    if not trades:
        print(f"    {label}: 0 trades"); return
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    cutoff = int(n * 0.7)
    is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
    print(f"    {label}: n={len(trades)} ({len(trades)/days:.2f}/day) net={pnls.sum():.2f} "
          f"win%={100*(pnls>0).mean():.1f} pf={pf:.3f} IS={is_net:.2f} OOS={oos_net:.2f}")
    return pnls, entries


if __name__ == "__main__":
    df = load_m1()
    n = len(df)
    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    open_ = df["open"].values.astype(float)
    spread = df["spread"].values.astype(float)
    hour = df["time"].dt.hour.values
    tick_vol = df["tick_volume"].values.astype(float)
    days = (df["time"].max() - df["time"].min()).days

    by_hour = pd.Series(tick_vol).groupby(hour).mean()
    HIGH_LIQ_HOURS = set(by_hour.sort_values(ascending=False).index[:4])

    p = E.P
    m21 = E.ma(close, p["p21"], p["m21"])
    m50 = E.ma(close, p["p50"], p["m50"])
    m150 = E.ma(close, p["p150"], p["m150"])
    m600 = E.ma(close, p["p600"], p["m600"])
    m2400 = E.ma(close, p["p2400"], p["m2400"])
    atr = E.wilder_atr(high, low, close, 14)

    aligned_buy = (close > m2400) & (m21 > m50) & (m50 > m150) & (m150 > m600)
    aligned_sell = (close < m2400) & (m21 < m50) & (m50 < m150) & (m150 < m600)

    pb, tol_mult = p["pullback_bars"], p["pullback_tol_atr"]
    diff_buy = low - m50
    diff_sell = m50 - high
    roll_min_buy = pd.Series(diff_buy).rolling(pb, min_periods=1).min().values
    roll_min_sell = pd.Series(diff_sell).rolling(pb, min_periods=1).min().values
    tol_i = tol_mult * atr
    pullback_ok_buy = (close > m50) & (roll_min_buy <= tol_i)
    pullback_ok_sell = (close < m50) & (roll_min_sell <= tol_i)

    sig_buy = aligned_buy & pullback_ok_buy
    sig_sell = aligned_sell & pullback_ok_sell
    trig_buy = sig_buy & ~np.concatenate(([False], sig_buy[:-1]))
    trig_sell = sig_sell & ~np.concatenate(([False], sig_sell[:-1]))

    # Ratchet's real wick-reject: on the trigger bar itself, wick into the
    # direction of the pullback must dominate the body by InpWickRejectRatio
    body = np.abs(close - open_)
    wick_buy = np.minimum(open_, close) - low     # lower wick (rejection off the downside)
    wick_sell = high - np.maximum(open_, close)   # upper wick (rejection off the upside)

    triggers_all = [(i, 1.0) for i in np.where(trig_buy)[0]] + [(i, -1.0) for i in np.where(trig_sell)[0]]
    triggers_all.sort(key=lambda t: t[0])
    triggers_liq = [(i, d) for i, d in triggers_all if int(hour[i]) in HIGH_LIQ_HOURS]

    print(f"M1: {len(triggers_all)} total triggers, {len(triggers_liq)} in high-liq hours "
          f"({days} days)\n")

    print("=" * 78)
    print("BASELINE (no wick-reject) vs WICK-REJECT ADDED, at m1_scalp_test.py's best cell "
          "(tp=0.3 sl=0.3, maxhold=5min)")
    for ratio in (None, 1.0, 1.5, 2.0):
        if ratio is None:
            trig = triggers_liq
            label = "no wick-reject filter"
        else:
            trig = []
            for i, d in triggers_liq:
                if d > 0:
                    ok = body[i] > 0 and wick_buy[i] >= ratio * body[i]
                else:
                    ok = body[i] > 0 and wick_sell[i] >= ratio * body[i]
                if ok:
                    trig.append((i, d))
            label = f"wick-reject ratio={ratio}"
        trades = sim(trig, close, high, low, spread, atr, n, 0.3, 0.3, 5)
        report(label, trades, n, days)

    print("\n" + "=" * 78)
    print("Full TP/SL/hold grid WITH wick-reject=1.5 (Ratchet's real default)")
    trig15 = []
    for i, d in triggers_liq:
        if d > 0:
            ok = body[i] > 0 and wick_buy[i] >= 1.5 * body[i]
        else:
            ok = body[i] > 0 and wick_sell[i] >= 1.5 * body[i]
        if ok:
            trig15.append((i, d))
    print(f"{len(trig15)} triggers survive wick-reject=1.5 ({len(trig15)/days:.2f}/day)\n")

    best = None
    for maxhold, hlabel in ((3, "3min"), (5, "5min"), (10, "10min")):
        for tp_atr, sl_atr in ((0.3, 0.3), (0.3, 0.5), (0.5, 0.5), (0.5, 0.75)):
            trades = sim(trig15, close, high, low, spread, atr, n, tp_atr, sl_atr, maxhold)
            res = report(f"hold<={hlabel} tp={tp_atr} sl={sl_atr}", trades, n, days)
            if trades:
                net = sum(t[2] for t in trades)
                if best is None or net > best[0]:
                    best = (net, maxhold, tp_atr, sl_atr, trades)

    if best:
        net, maxhold, tp_atr, sl_atr, trades = best
        print(f"\nbest cell: maxhold={maxhold} tp={tp_atr} sl={sl_atr} net={net:.2f} n={len(trades)}")
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        edges = np.linspace(0, n, 5).astype(int)
        pos = 0
        for b in range(4):
            lo, hi = edges[b], edges[b + 1]
            m = (entries >= lo) & (entries < hi)
            nb = m.sum()
            if nb == 0:
                print(f"  block {b+1}: 0 trades"); continue
            netb = pnls[m].sum()
            t0 = df["time"].iloc[lo]; t1 = df["time"].iloc[min(hi, n - 1)]
            if netb > 0: pos += 1
            print(f"  block {b+1} [{t0.date()}->{t1.date()}]: n={nb} net={netb:.2f} win%={100*(pnls[m]>0).mean():.1f}")
        print(f"  -> positive in {pos}/4 blocks")
