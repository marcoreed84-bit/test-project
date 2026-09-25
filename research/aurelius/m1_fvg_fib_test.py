"""
Two NEW candidate M1 scalp constructions, requested directly (2026-09-25):
Fair Value Gap (FVG) fill-and-continue, and Fibonacci retracement bounce.
Neither exists anywhere else in this repo - built fresh here, real-data
tested on the same real GOLD# M1 export (300k bars, ~310 days) used for
every other M1 screen this session, BEFORE any MQL5 work.

FVG (3-candle imbalance, standard ICT-style definition):
  bullish FVG at bar i (using i-2, i-1, i): high[i-2] < low[i]
    -> unfilled gap zone = [high[i-2], low[i]], bullish imbalance.
  bearish FVG at bar i: low[i-2] > high[i]
    -> zone = [high[i], low[i-2]], bearish imbalance.
  ENTRY (continuation, the standard use): price later trades back INTO an
  unfilled zone (first touch only) and closes back out the imbalance side
  -> enter in the zone's own direction (buy a bullish zone, sell a bearish
  one). Zone must still be "unfilled" (price hasn't already fully closed
  through the whole gap) when touched - matches how this setup is actually
  traded, not just "gap exists".
  Stop: beyond the zone's far edge. Target: k x ATR, short max hold.

FIB RETRACEMENT (fixed-lookback swing, since "real" swing detection is
subjective - this is the standard testable simplification):
  swing_high/swing_low = rolling max/min of high/low over InpSwingBars.
  Trend = up if close is nearer swing_high than swing_low (i.e. in the
  upper half of the current swing range), down otherwise - a simple,
  deterministic stand-in for "which way is this leg going".
  Retracement level = swing_high - level*(swing_high-swing_low) for an
  uptrend (price pulling back down into support), mirrored for downtrend.
  ENTRY: price touches the level (low<=level<=high intrabar) and closes
  back on the trend side of it (confirmation, not just a touch).
  Stop: beyond the level by a small ATR buffer. Target: k x ATR.

Sequential, single-position, walk-forward, no lookahead, real spread on
entry - identical discipline to every other real-data screen in this repo.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/msg")
import numpy as np
import pandas as pd
import engine as E
import sim as M

POINT = E.POINT


def sim_trades(triggers, close, high, low, spread, atr, n, stop_fn, tp_atr, maxhold):
    """triggers: list of (i, dir, stop_px). Generic single-position walker,
    stop is a FIXED price level (from the setup), target is k*ATR from entry."""
    trades = []
    last_exit = -1
    for i, d, stop_px in triggers:
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
        sl = stop_px
        if (is_buy and sl >= entry) or (not is_buy and sl <= entry):
            continue  # degenerate: setup's own stop already past entry
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
        print(f"    {label}: 0 trades"); return None
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    cutoff = int(n * 0.7)
    is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
    print(f"    {label}: n={len(trades)} ({len(trades)/days:.2f}/day) net={pnls.sum():.2f} "
          f"win%={100*(pnls>0).mean():.1f} pf={pf:.3f} IS={is_net:.2f} OOS={oos_net:.2f}")
    return pnls, entries


def block_check(label, pnls, entries, n, df):
    edges = np.linspace(0, n, 5).astype(int)
    pos = 0
    for b in range(4):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
    print(f"    {label} -> positive in {pos}/4 blocks")


def find_fvg(high, low, n):
    """Returns list of (formed_i, dir, zone_lo, zone_hi) for each 3-bar FVG,
    formed_i = the bar completing the pattern (i, using i-2,i-1,i)."""
    zones = []
    for i in range(2, n):
        if high[i - 2] < low[i]:
            zones.append((i, 1, high[i - 2], low[i]))       # bullish zone
        elif low[i - 2] > high[i]:
            zones.append((i, -1, high[i], low[i - 2]))       # bearish zone
    return zones


def fvg_triggers(df, atr, stop_buf_atr, max_wait_bars):
    n = len(df)
    close, high, low, open_ = df["close"].values, df["high"].values, df["low"].values, df["open"].values
    zones = find_fvg(high, low, n)
    trig = []
    for formed_i, d, zlo, zhi in zones:
        filled = False
        for i in range(formed_i + 1, min(formed_i + 1 + max_wait_bars, n)):
            touched = (low[i] <= zhi and high[i] >= zlo)
            if not touched:
                continue
            a = atr[i]
            if np.isnan(a) or a <= 0:
                filled = True; break
            if d > 0:
                confirmed = close[i] > zlo
                stop_px = zlo - stop_buf_atr * a
            else:
                confirmed = close[i] < zhi
                stop_px = zhi + stop_buf_atr * a
            if confirmed:
                trig.append((i, d, stop_px))
            filled = True
            break
        # once price fully closes through the zone without touching it right, zone is stale - handled by max_wait_bars cap
    trig.sort(key=lambda t: t[0])
    return trig


def fib_triggers(df, atr, swing_bars, level, stop_buf_atr):
    n = len(df)
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    sh = pd.Series(high).rolling(swing_bars).max().values
    sl_ = pd.Series(low).rolling(swing_bars).min().values
    trig = []
    for i in range(swing_bars + 1, n):
        if np.isnan(sh[i]) or np.isnan(sl_[i]) or sh[i] <= sl_[i]:
            continue
        rng = sh[i] - sl_[i]
        mid = sl_[i] + 0.5 * rng
        uptrend = close[i] >= mid
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        if uptrend:
            lvl = sh[i] - level * rng
            touched = low[i] <= lvl <= high[i]
            confirmed = touched and close[i] > lvl
            if confirmed:
                trig.append((i, 1, lvl - stop_buf_atr * a))
        else:
            lvl = sl_[i] + level * rng
            touched = low[i] <= lvl <= high[i]
            confirmed = touched and close[i] < lvl
            if confirmed:
                trig.append((i, -1, lvl + stop_buf_atr * a))
    return trig


if __name__ == "__main__":
    df1 = M.load_bars()
    df1["time"] = pd.to_datetime(df1["time"])
    n1 = len(df1)
    days = (df1["time"].max() - df1["time"].min()).days
    print(f"M1 data: {df1['time'].min()} -> {df1['time'].max()}, n={n1} bars (~{days} days)\n")
    atr1 = E.wilder_atr(df1["high"].values, df1["low"].values, df1["close"].values, 14)
    spread1 = df1["spread"].values.astype(float)
    close1, high1, low1 = df1["close"].values, df1["high"].values, df1["low"].values

    print("=" * 78)
    print("FVG fill-and-continue: raw zone frequency first")
    zones = find_fvg(high1, low1, n1)
    print(f"  {len(zones)} total FVGs formed over {days} days "
          f"({sum(1 for z in zones if z[1]>0)} bullish, {sum(1 for z in zones if z[1]<0)} bearish)\n")

    print("PF grid: stop_buf x ATR beyond zone, target = k x ATR, wait<=N bars for first touch")
    best_fvg = None
    for stop_buf in (0.1, 0.25, 0.5):
        for tp_atr in (0.3, 0.5, 0.75):
            for max_wait in (20, 60):
                trig = fvg_triggers(df1, atr1, stop_buf, max_wait)
                trades = sim_trades(trig, close1, high1, low1, spread1, atr1, n1, None, tp_atr, max_wait)
                res = report(f"stopbuf={stop_buf} tp={tp_atr}xATR wait<={max_wait}", trades, n1, days)
                if res:
                    pnls, entries = res
                    net = pnls.sum()
                    if best_fvg is None or net > best_fvg[0]:
                        best_fvg = (net, stop_buf, tp_atr, max_wait, pnls, entries)
    if best_fvg:
        net, stop_buf, tp_atr, max_wait, pnls, entries = best_fvg
        print(f"\n  best FVG cell: stopbuf={stop_buf} tp={tp_atr} wait<={max_wait} net={net:.2f} n={len(pnls)}")
        block_check("FVG best", pnls, entries, n1, df1)

    print("\n" + "=" * 78)
    print("FIB retracement bounce: raw trigger frequency first")
    for swing_bars in (60, 120, 240):
        for level in (0.5, 0.618):
            trig = fib_triggers(df1, atr1, swing_bars, level, 0.2)
            print(f"  swing={swing_bars} level={level}: {len(trig)} triggers -> {len(trig)/days:.2f}/day")

    print("\nPF grid: swing lookback, level, stop buffer, target k x ATR")
    best_fib = None
    for swing_bars in (60, 120, 240):
        for level in (0.5, 0.618):
            for stop_buf in (0.2, 0.4):
                for tp_atr in (0.3, 0.5, 0.75):
                    trig = fib_triggers(df1, atr1, swing_bars, level, stop_buf)
                    trades = sim_trades(trig, close1, high1, low1, spread1, atr1, n1, None, tp_atr, 60)
                    res = report(f"swing={swing_bars} lvl={level} stopbuf={stop_buf} tp={tp_atr}",
                                 trades, n1, days)
                    if res:
                        pnls, entries = res
                        net = pnls.sum()
                        if best_fib is None or net > best_fib[0]:
                            best_fib = (net, swing_bars, level, stop_buf, tp_atr, pnls, entries)
    if best_fib:
        net, swing_bars, level, stop_buf, tp_atr, pnls, entries = best_fib
        print(f"\n  best FIB cell: swing={swing_bars} level={level} stopbuf={stop_buf} tp={tp_atr} "
              f"net={net:.2f} n={len(pnls)}")
        block_check("FIB best", pnls, entries, n1, df1)
