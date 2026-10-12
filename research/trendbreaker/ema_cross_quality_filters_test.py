"""
Follow-up to ema_cross_trail50_filtered_test.py (best so far: alignment +
volume + spread, PF=0.600, win%=22.0, n=473 - still a loser, win rate
short of breakeven by ~4pts at the 2.0 ATR buffer's 2.37:1 payoff ratio).

User's new ask: check the QUALITY of the cross itself, not just trend
context - angle/steepness, whether it's a clean cross or a choppy
back-and-forth, and whether price actually continues after crossing
(not an immediate fake-out). Three real, testable ideas, layered one at
a time on top of the best config so far (alignment + volume + spread,
TRAIL_BUFFER_ATR=2.0, the best buffer found in the last round):

1. SLOPE/ANGLE: the crossing MA's slope over the last N bars, ATR-
   normalized - a steep cross should mean real momentum, not a shallow
   drift-through.
2. NOT CHOPPY: no OTHER 21/50 cross in the last N bars before this one -
   a cross that's part of a recent back-and-forth is more likely fake
   (same concept as Fulcrum's own CrissCross filter).
3. CONTINUATION CONFIRM: price must still be on the cross's side N bars
   later before the trade is even counted as taken (tests whether
   requiring post-cross follow-through, not just the cross itself,
   screens out fake-outs) - flagged clearly that every entry-side
   "wait and confirm" idea tested on other EAs tonight has hurt, so
   this one gets reported honestly even if it's negative.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
from aurelius_m15_silver_test import load_m15_silver
from ema_cross_trail50_filtered_test import ema, wilder_atr, pf

CLEAN_END = pd.Timestamp("2025-12-31")
SILVER_POINT = 0.001
BUF_ATR = 2.0   # best buffer found in the prior round


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    ratio = wins.mean() / abs(losses.mean()) if len(losses) and losses.mean() != 0 else float("nan")
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.3f}  win/loss ratio={ratio:.2f}")


def simulate(close, high, low, spread, m21, m50, atr, sign, start, gate=None, confirm_bars=0):
    n = len(close)
    trades = []
    i = start
    while i < n - 1:
        fire = (not np.isnan(sign[i]) and not np.isnan(sign[i - 1]) and sign[i] != 0
                and sign[i] != sign[i - 1] and sign[i - 1] != 0)
        if not fire:
            i += 1
            continue
        d = 1 if sign[i] > 0 else -1
        if gate is not None and not gate(i, d > 0):
            i += 1
            continue
        fill_i = i + 1
        if confirm_bars > 0:
            fill_i = i + 1 + confirm_bars
            if fill_i >= n:
                i += 1
                continue
            still_ok = (close[fill_i - 1] > m50[fill_i - 1]) if d > 0 else (close[fill_i - 1] < m50[fill_i - 1])
            if not still_ok:
                i += 1
                continue
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        is_buy = d > 0
        sc = spread[fill_i] * SILVER_POINT
        ref_px = close[fill_i - 1]
        entry_px = ref_px + sc if is_buy else ref_px - sc
        exit_i, exit_px = None, None
        for kk in range(fill_i, n):
            a = atr[kk]
            if np.isnan(m50[kk]) or np.isnan(a) or a <= 0:
                continue
            buf = BUF_ATR * a
            c = close[kk]
            broke = (c < m50[kk] - buf) if is_buy else (c > m50[kk] + buf)
            if broke:
                exit_i, exit_px = kk, c
                break
        if exit_i is None:
            exit_i, exit_px = n - 1, close[n - 1]
        pnl = (exit_px - entry_px) * (1 if is_buy else -1)
        trades.append(dict(entry_i=i, exit_i=exit_i, pnl=pnl))
        i = exit_i + 1
    return trades


if __name__ == "__main__":
    df = load_m15_silver()
    df = df[df["time"] <= CLEAN_END].reset_index(drop=True)
    close, high, low, spread = df["close"].values, df["high"].values, df["low"].values, df["spread"].values
    vol = df["tick_volume"].values.astype(float)
    n = len(df)
    print(f"SILVER M15, clean window only: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")

    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m150 = ema(close, 150)
    m600 = ema(close, 200)
    m2400 = ema(close, 1200)
    atr = wilder_atr(high, low, close, 14)
    sign = np.sign(m21 - m50)
    vol_avg = pd.Series(vol).shift(1).rolling(100, min_periods=100).mean().values
    vol_ratio = vol / vol_avg

    def gate_base(i, is_buy, max_sp=60, min_vr=1.3):
        if np.isnan(m150[i]) or np.isnan(m600[i]) or np.isnan(m2400[i]):
            return False
        ok_align = (close[i] > m2400[i] and m21[i] > m50[i] > m150[i] > m600[i]) if is_buy \
            else (close[i] < m2400[i] and m21[i] < m50[i] < m150[i] < m600[i])
        if not ok_align:
            return False
        vr = vol_ratio[i]
        if not (np.isnan(vr) or vr >= min_vr):
            return False
        return spread[i + 1] <= max_sp

    trades0 = simulate(close, high, low, spread, m21, m50, atr, sign, 1201, gate=gate_base)
    print("0. BASELINE (alignment + volume + spread, buffer=2.0 ATR - for reference)")
    report("ALL", trades0)
    print()

    # 1. slope/angle of the crossing MA (m21) over last 10 bars, ATR-normalized
    slope21 = np.full(n, np.nan)
    slope21[10:] = (m21[10:] - m21[:-10]) / atr[10:]

    def gate_slope(i, is_buy, min_slope=0.3):
        if not gate_base(i, is_buy):
            return False
        s = slope21[i]
        if np.isnan(s):
            return False
        return (s >= min_slope) if is_buy else (s <= -min_slope)

    for ms in (0.2, 0.3, 0.5, 0.75):
        tr = simulate(close, high, low, spread, m21, m50, atr, sign, 1201,
                      gate=lambda i, b, ms=ms: gate_slope(i, b, ms))
        report(f"1. + slope>={ms} ATR/10bars", tr)
    print()

    # 2. not-choppy: no other 21/50 cross in last N bars before this one
    cross_bar = np.zeros(n, dtype=bool)
    cross_bar[1:] = (sign[1:] != sign[:-1]) & (sign[1:] != 0) & (sign[:-1] != 0)

    def gate_nochop(i, is_buy, lookback=20):
        if not gate_base(i, is_buy):
            return False
        window = cross_bar[max(0, i - lookback):i]
        return window.sum() == 0   # no OTHER cross in the lookback (this bar's own cross excluded)

    for lb in (10, 20, 40, 80):
        tr = simulate(close, high, low, spread, m21, m50, atr, sign, 1201,
                      gate=lambda i, b, lb=lb: gate_nochop(i, b, lb))
        report(f"2. + no other cross in last {lb} bars", tr)
    print()

    # 3. continuation confirm: price still on the cross's side N bars later
    for cb in (1, 2, 3, 5):
        tr = simulate(close, high, low, spread, m21, m50, atr, sign, 1201, gate=gate_base, confirm_bars=cb)
        report(f"3. + {cb}-bar continuation confirm", tr)
    print()

    # best combo: slope + no-chop together
    def gate_combo(i, is_buy, min_slope=0.3, lookback=20):
        if not gate_slope(i, is_buy, min_slope):
            return False
        window = cross_bar[max(0, i - lookback):i]
        return window.sum() == 0

    tr = simulate(close, high, low, spread, m21, m50, atr, sign, 1201,
                  gate=lambda i, b: gate_combo(i, b))
    report("4. + slope(0.3) AND no-chop(20) combined", tr)
