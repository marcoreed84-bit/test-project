"""
A genuinely different entry trigger, not a filter on the stochastic
cross - everything tried tonight on top of the stochastic (MA stack x4,
reject, snapback, BB-width, tick-volume, and all 15 combinations of
those) failed, so this tests a different mechanism from scratch.

RSI DIVERGENCE: price makes a new swing low/high, but RSI does NOT
confirm it (a higher low on RSI while price makes a lower low = bullish
divergence; mirror for bearish). This directly targets "is this a real
reversal or a fake one" - divergence is specifically a disagreement
between price and momentum, unlike a stochastic cross which only looks
at the oscillator's own level.

Construction: Wilder RSI(14). Pivot lows/highs found with a
PIVOT_LEFT/PIVOT_RIGHT confirmation window (a bar is a pivot low if its
low is the lowest within [i-PIVOT_LEFT, i+PIVOT_RIGHT] - confirmed
PIVOT_RIGHT bars later, no lookahead at the confirmation bar itself).
Bullish divergence: the current confirmed pivot low's price is LOWER
than the previous confirmed pivot low's price, but RSI at the current
pivot is HIGHER than RSI at the previous pivot (within
MAX_PIVOT_GAP_BARS of each other). Bearish is the exact mirror on
pivot highs.

Exit: swing stop (same SWING_BARS convention used all night) + fixed
1:2 R:R target, time-capped - no stochastic anywhere, so no
opposite-cross exit option here; this mirrors the candlestick
construction's own exit convention instead (the other non-stochastic
success tonight).

Tested on GOLD, SILVER, BTCUSD M15. Honest K=1 per instrument - first
RSI-divergence construction tonight, a different mechanism from every
stochastic-based or EMA-based idea tried so far.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report

PIVOT_LEFT, PIVOT_RIGHT = 5, 5
MAX_PIVOT_GAP_BARS = 60
RSI_PERIOD = 14
SWING_BARS = 10
RR = 2.0
TIME_CAP_BARS = 300
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")


def load_m15(symbol_file, trim_gold=False):
    path = os.path.join(DATA_DIR, symbol_file)
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    if trim_gold:
        df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df, point


def wilder_rsi(close, period):
    n = len(close)
    rsi = np.full(n, np.nan)
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    if n < period + 1:
        return rsi
    avg_gain = gain[1:period + 1].mean()
    avg_loss = loss[1:period + 1].mean()
    rsi[period] = 100.0 - 100.0 / (1.0 + (avg_gain / avg_loss if avg_loss > 0 else np.inf))
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        rs = (avg_gain / avg_loss) if avg_loss > 0 else np.inf
        rsi[i] = 100.0 - 100.0 / (1.0 + rs)
    return rsi


def find_pivots(values, left, right, is_low):
    """Returns array of bar indices that are confirmed pivot lows/highs."""
    n = len(values)
    pivots = []
    for i in range(left, n - right):
        window = values[i - left:i + right + 1]
        if is_low:
            if values[i] == window.min() and (window == values[i]).sum() == 1:
                pivots.append(i)
        else:
            if values[i] == window.max() and (window == values[i]).sum() == 1:
                pivots.append(i)
    return pivots


def build_trades(df, point):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    rsi_a = wilder_rsi(close_a, RSI_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    rsi = rsi_a.tolist()

    pivot_lows = find_pivots(low_a, PIVOT_LEFT, PIVOT_RIGHT, is_low=True)
    pivot_highs = find_pivots(high_a, PIVOT_LEFT, PIVOT_RIGHT, is_low=False)

    # signal fires at the CONFIRMATION bar (pivot_i + PIVOT_RIGHT) - the
    # earliest point the pivot is actually known, no lookahead
    signals = []   # (confirm_bar, dir)
    for idx in range(1, len(pivot_lows)):
        p_cur, p_prev = pivot_lows[idx], pivot_lows[idx - 1]
        if p_cur - p_prev > MAX_PIVOT_GAP_BARS:
            continue
        if np.isnan(rsi[p_cur]) or np.isnan(rsi[p_prev]):
            continue
        if low[p_cur] < low[p_prev] and rsi[p_cur] > rsi[p_prev]:
            confirm_bar = p_cur + PIVOT_RIGHT
            if confirm_bar < n:
                signals.append((confirm_bar, 1))
    for idx in range(1, len(pivot_highs)):
        p_cur, p_prev = pivot_highs[idx], pivot_highs[idx - 1]
        if p_cur - p_prev > MAX_PIVOT_GAP_BARS:
            continue
        if np.isnan(rsi[p_cur]) or np.isnan(rsi[p_prev]):
            continue
        if high[p_cur] > high[p_prev] and rsi[p_cur] < rsi[p_prev]:
            confirm_bar = p_cur + PIVOT_RIGHT
            if confirm_bar < n:
                signals.append((confirm_bar, -1))

    signals.sort(key=lambda s: s[0])

    results = []
    next_free = SWING_BARS + 5
    for i, dir_ in signals:
        if i < next_free:
            continue
        if i < SWING_BARS:
            continue
        swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
        risk = dir_ * (close[i] - swing)
        if risk <= 0.0:
            continue
        fill_i = i + 1
        if fill_i >= n:
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
        stop_px = swing
        target_px = entry_px + dir_ * RR * risk
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
            target_hit = (high[j] >= target_px) if dir_ > 0 else (low[j] <= target_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if target_hit:
                exit_i, exit_px, reason = j, target_px, "TARGET"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        next_free = exit_i + 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - RSI(14) price/momentum DIVERGENCE entry (no stochastic)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - RSI divergence", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - first RSI-divergence construction tonight,")
    print(f"  a different mechanism (price/momentum disagreement) from everything else tried.")
