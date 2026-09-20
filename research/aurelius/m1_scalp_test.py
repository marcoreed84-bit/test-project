"""
Genuine scalp-resolution test: the trend+MA-bounce construction (Aurelius's
own real aligned_buy/sell + pullback_ok_buy/sell definitions - the SAME
signal already inside the validated live EA) combined with the ONE thing
that cleared zero with correct single-position sequencing so far
(session_filter_test.py's high-liquidity-hour restriction), now run on
REAL M1 (1-minute) bars instead of M5 - true few-MINUTE holds, not the
30-minute minimum M5 allowed. This is the finest resolution tested this
session, using the Ultra Low account's real M1 export.

Honest limitation upfront: the M1 data only covers ~10 months
(2025-11-12 -> 2026-09-18), not years - far less statistical power than
every other test this session. Treat any result here with EXTRA
skepticism for that reason alone, on top of everything else.

Still just OHLCV bars - no order-flow/DOM visibility, consistent with
the structural limitation already established. This test answers "does
finer bar resolution change anything", not "do we now have real
order-flow scalping" - those are different questions.

Correct single-position sequential simulation from the start (the
lesson from the cloud-confluence overlap bug) - no repeat.
"""
import sys
sys.path.insert(0, ".")
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


if __name__ == "__main__":
    df = load_m1()
    n = len(df)
    close = df["close"].values.astype(float)
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    spread = df["spread"].values.astype(float)
    hour = df["time"].dt.hour.values
    tick_vol = df["tick_volume"].values.astype(float)

    print(f"M1 data: {df['time'].min()} -> {df['time'].max()}, n={n} bars "
          f"(~{(df['time'].max()-df['time'].min()).days} real days)\n")

    # --- verify the high-liquidity window still holds at M1 resolution,
    # rather than assuming the M5 finding (hours 15-18) transfers as-is ---
    by_hour = pd.Series(tick_vol).groupby(hour).mean()
    print("mean tick_volume by hour (M1, this account):")
    print(by_hour.round(1).to_string())
    HIGH_LIQ_HOURS = set(by_hour.sort_values(ascending=False).index[:4])
    print(f"\ntop-4 hours by volume: {sorted(HIGH_LIQ_HOURS)}\n")

    # --- same real alignment-stack + pullback-off-50EMA construction
    # Aurelius's own CheckEntry() uses, built fresh on M1 bars (same
    # helper functions, same periods - a genuinely faster version of the
    # identical real signal, not a new invented one) ---
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
    triggers_all = [(i, 1.0) for i in np.where(trig_buy)[0]] + [(i, -1.0) for i in np.where(trig_sell)[0]]
    triggers_all.sort(key=lambda t: t[0])
    triggers = [(i, d) for i, d in triggers_all if int(hour[i]) in HIGH_LIQ_HOURS]
    print(f"{len(triggers_all)} total trend+bounce triggers -> {len(triggers)} inside the "
          f"high-liquidity window ({100*len(triggers)/max(1,len(triggers_all)):.1f}%)\n")

    def sim(triggers, tp_atr, sl_atr, maxhold):
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

    print("=" * 70)
    print("TRUE SCALP holds - 3/5/10 MINUTE max hold (M1 bars = 1:1 with minutes)")
    for maxhold, label in ((3, "3min"), (5, "5min"), (10, "10min")):
        print(f"\n--- max hold = {maxhold} bars ({label}) ---")
        for tp_atr, sl_atr in ((0.3, 0.3), (0.3, 0.5), (0.5, 0.5), (0.5, 0.75)):
            trades, skipped = sim(triggers, tp_atr, sl_atr, maxhold)
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

    # --- 4-block walk-forward on the best-looking cell, given only ~10
    # months of data - shorter/fewer blocks than the 5-block standard used
    # on multi-year datasets, since each block still needs enough trades
    # to mean anything ---
    print("\n" + "=" * 70)
    print("4-block walk-forward (only ~10mo of M1 history - blocks are necessarily short)")
    best = None
    for maxhold in (3, 5, 10):
        for tp_atr, sl_atr in ((0.3, 0.3), (0.3, 0.5), (0.5, 0.5), (0.5, 0.75)):
            trades, _ = sim(triggers, tp_atr, sl_atr, maxhold)
            if not trades:
                continue
            net = sum(t[2] for t in trades)
            if best is None or net > best[0]:
                best = (net, maxhold, tp_atr, sl_atr, trades)
    if best is None:
        print("no trades resolved anywhere in the grid")
    else:
        net, maxhold, tp_atr, sl_atr, trades = best
        print(f"best cell: maxhold={maxhold} tp={tp_atr} sl={sl_atr} net={net:.2f} n={len(trades)}")
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        edges = np.linspace(0, n, 5).astype(int)
        pos = 0
        for b in range(4):
            lo, hi = edges[b], edges[b+1]
            m = (entries >= lo) & (entries < hi)
            nb = m.sum()
            if nb == 0:
                print(f"  block {b+1}: 0 trades"); continue
            netb = pnls[m].sum()
            t0 = df["time"].iloc[lo]; t1 = df["time"].iloc[min(hi, n-1)]
            if netb > 0: pos += 1
            print(f"  block {b+1} [{t0.date()}->{t1.date()}]: n={nb} net={netb:.2f} win%={100*(pnls[m]>0).mean():.1f}")
        print(f"  -> positive in {pos}/4 blocks")
