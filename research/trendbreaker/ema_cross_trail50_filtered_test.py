"""
Follow-up to ema_cross_trail50_test.py (rejected, raw cross, PF=0.489,
net loser) - user's pushback: add the alignment stack (same 5-MA
trend-context filter Aurelius/H&S already use), plus volume/spread/RSI,
since a raw cross alone is "mostly noise with a few genuine trends
mixed in" per that file's own conclusion - the claim being that
filtering should separate the good trades from the choppy losers.

Periods for the alignment stack reuse Aurelius M15's own real values
(InpP150=150, InpP600=200, InpP2400=1200) rather than inventing new
ones. Entry/exit mechanism (21/50 cross, pure 50-EMA trail, no fixed
stop/target) is UNCHANGED from the rejected baseline - only entry-side
filters are added, layered one at a time so each filter's own
contribution is visible, not just the final combination.

Restricted to the clean 2014-2025 Silver M15 window (2026 portion has
a known data-quality problem, see earlier in this session).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from aurelius_m15_silver_test import load_m15_silver

CLEAN_END = pd.Timestamp("2025-12-31")
TRAIL_BUFFER_ATR = 0.15
SILVER_POINT = 0.001


def ema(arr, period):
    out = np.full(len(arr), np.nan)
    alpha = 2.0 / (period + 1)
    out[period - 1] = np.mean(arr[:period])
    for i in range(period, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def wilder_atr(h, l, c, n=14):
    tr = np.zeros(len(c))
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    out = np.full(len(c), np.nan)
    out[n] = tr[1:n + 1].mean()
    for i in range(n + 1, len(c)):
        out[i] = (out[i - 1] * (n - 1) + tr[i]) / n
    return out


def wilder_rsi(c, n=14):
    delta = np.diff(c, prepend=c[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = np.full(len(c), np.nan)
    avg_loss = np.full(len(c), np.nan)
    avg_gain[n] = gain[1:n + 1].mean()
    avg_loss[n] = loss[1:n + 1].mean()
    for i in range(n + 1, len(c)):
        avg_gain[i] = (avg_gain[i - 1] * (n - 1) + gain[i]) / n
        avg_loss[i] = (avg_loss[i - 1] * (n - 1) + loss[i]) / n
    rs = avg_gain / np.where(avg_loss == 0, np.nan, avg_loss)
    return 100 - 100 / (1 + rs)


def simulate(close, high, low, spread, m21, m50, atr, sign, gate=None):
    n = len(close)
    trades = []
    i = 1201
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
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        is_buy = d > 0
        sc = spread[fill_i] * SILVER_POINT
        entry_px = close[i] + sc if is_buy else close[i] - sc
        exit_i, exit_px, reason = None, None, None
        for kk in range(fill_i, n):
            a = atr[kk]
            if np.isnan(m50[kk]) or np.isnan(a) or a <= 0:
                continue
            buf = TRAIL_BUFFER_ATR * a
            c = close[kk]
            broke = (c < m50[kk] - buf) if is_buy else (c > m50[kk] + buf)
            if broke:
                exit_i, exit_px, reason = kk, c, "TRAIL50"
                break
        if exit_i is None:
            exit_i, exit_px, reason = n - 1, close[n - 1], "EOD"
        pnl = (exit_px - entry_px) * (1 if is_buy else -1)
        trades.append(dict(entry_i=i, exit_i=exit_i, pnl=pnl, dir=1 if is_buy else -1, reason=reason))
        i = exit_i + 1
    return trades


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.3f}  avg={pnl.mean():7.4f}")


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
    m600 = ema(close, 200)      # Aurelius M15's own real InpP600 value
    m2400 = ema(close, 1200)    # Aurelius M15's own real InpP2400 value
    atr = wilder_atr(high, low, close, 14)
    rsi = wilder_rsi(close, 14)
    sign = np.sign(m21 - m50)

    vol_avg = pd.Series(vol).shift(1).rolling(100, min_periods=100).mean().values
    vol_ratio = vol / vol_avg

    cutoff_i = int(n * 0.70)

    def run(label, gate):
        trades = simulate(close, high, low, spread, m21, m50, atr, sign, gate=gate)
        print(f"{'='*92}\n{label}\n{'='*92}")
        report("IS ", [t for t in trades if t["entry_i"] < cutoff_i])
        report("OOS", [t for t in trades if t["entry_i"] >= cutoff_i])
        report("ALL", trades)
        print()
        return trades

    run("0. BASELINE: raw 21/50 cross (no filter) - already rejected, for reference", None)

    def gate_align(i, is_buy):
        if np.isnan(m150[i]) or np.isnan(m600[i]) or np.isnan(m2400[i]):
            return False
        if is_buy:
            return close[i] > m2400[i] and m21[i] > m50[i] > m150[i] > m600[i]
        else:
            return close[i] < m2400[i] and m21[i] < m50[i] < m150[i] < m600[i]

    run("1. + Alignment stack (c vs 2400-EMA, 21>50>150>600 or mirror)", gate_align)

    def gate_align_vol(i, is_buy, min_vr=1.3):
        if not gate_align(i, is_buy):
            return False
        vr = vol_ratio[i]
        return np.isnan(vr) or vr >= min_vr

    run("2. + Volume (>= 1.3x avg)", gate_align_vol)

    def gate_align_vol_spread(i, is_buy, max_sp=60):
        if not gate_align_vol(i, is_buy):
            return False
        return spread[i + 1] <= max_sp

    run("3. + Spread filter (<=60 points)", gate_align_vol_spread)

    def gate_align_vol_spread_rsi(i, is_buy):
        if not gate_align_vol_spread(i, is_buy):
            return False
        r = rsi[i]
        if np.isnan(r):
            return False
        return (r > 50) if is_buy else (r < 50)

    run("4. + RSI momentum-aligned (>50 buy / <50 sell)", gate_align_vol_spread_rsi)
