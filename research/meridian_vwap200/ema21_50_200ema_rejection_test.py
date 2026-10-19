"""
Follow-up to ema21_50_bb_mid_filter_test.py (that combo FAILED walk-forward:
IS PF=0.922, OOS PF=1.303 - classic overfit signature, not real, rejected).

User's refined 200EMA idea, distinct from the earlier static-distance test
(ema21_50_angle_parallel_200ema_test.py #3, which required the cross to be
FAR from EMA200 and made things worse): "when they are close to the 200ema,
and price rejects the 200ema, thats when you have a shitty criss cross."
This is a REJECTION pattern, not a distance threshold - price approaches/
wicks the 200EMA shortly before the cross, then pulls back away without
sustaining a break. Hypothesis: a cross that happens in the wake of that
kind of rejection is the "shitty criss cross" - so the gate here SUPPRESSES
entries where a 200EMA rejection happened in the N bars before the cross,
rather than requiring one.

Rejection defined per bar k: high[k]/low[k] came within TOUCH_ATR of EMA200
(wicked into it) but close[k] did NOT close through it by more than
BREAK_ATR - i.e. touched and bounced, not touched and broke through.

Base construction unchanged: pure EMA21/50 crossover, hold-to-next-
opposite-cross, confirm_bars=2 (EA's current default).

Honest K: running total for this overlay's filter search was 46 before
this file (22 + 14 + 10). This file adds its own grid on top.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from ema21_50_pure_crossover_test import load_m15, EMA_FAST, EMA_SLOW
from dual_stoch_cross_200ema_test import report
from vwap_open_scenarios_test import ema
from stoch_ma_stack_gap_filter_test import wilder_atr

CONFIRM_BARS = 2


def build_trades(df, point, confirm_bars=CONFIRM_BARS, gate=None):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    e21 = ema(close_a, EMA_FAST)
    e50 = ema(close_a, EMA_SLOW)
    e200 = ema(close_a, 200)
    atr = wilder_atr(high_a, low_a, close_a, 14)

    close, spread = close_a.tolist(), spread_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(atr[i]) or np.isnan(e200[i])) for i in range(n)]

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
            crossDown[i] = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]

    results = []
    start = EMA_SLOW + 210
    i = start
    posDir, open_fill_i, open_entry_px = 0, None, None
    pendingDir, pendingElapsed = 0, 0
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 1 if crossUp[i] else (-1 if crossDown[i] else 0)

        if posDir != 0 and dir_ != 0 and dir_ != posDir:
            fill_i = i + 1
            if fill_i < n:
                sc = spread[fill_i] * point
                exit_px = close[fill_i] - (sc if posDir > 0 else -sc)
                pnl_pct = ((exit_px - open_entry_px) / open_entry_px) * posDir
                results.append(dict(entry_i=open_fill_i, exit_i=fill_i, pnl_pct=pnl_pct, dir=posDir,
                                     reason="EXIT-EMA-CROSS", hold_bars=fill_i - open_fill_i))
            posDir, open_fill_i, open_entry_px = 0, None, None

        entry_dir, entry_bar = 0, None
        if posDir == 0:
            if pendingDir != 0:
                pendingElapsed += 1
                if pendingElapsed >= confirm_bars:
                    still_ok = (close[i] > e50[i]) if pendingDir > 0 else (close[i] < e50[i])
                    if still_ok:
                        entry_dir, entry_bar = pendingDir, i
                    pendingDir, pendingElapsed = 0, 0
            if dir_ != 0:
                pendingDir, pendingElapsed = dir_, 0

        if entry_dir != 0 and posDir == 0:
            is_buy = entry_dir > 0
            if gate is None or gate(entry_bar, is_buy):
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    entry_px = close[fill_i] + (sc if is_buy else -sc)
                    posDir, open_fill_i, open_entry_px = entry_dir, fill_i, entry_px

        i += 1

    return results


def run(label, df, point, gate=None):
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    trades = build_trades(df, point, gate=gate)
    report(label, trades, full_days, split_dir=True)
    return trades


def make_rejection_detector(high_a, low_a, close_a, e200, atr, touch_atr, lookback):
    n = len(close_a)
    rejected_recently = np.zeros(n, dtype=bool)
    for k in range(1, n):
        if np.isnan(e200[k]) or np.isnan(atr[k]) or atr[k] <= 0:
            continue
        tol = touch_atr * atr[k]
        touched_from_above = (low_a[k] <= e200[k] + tol) and (close_a[k] > e200[k])
        touched_from_below = (high_a[k] >= e200[k] - tol) and (close_a[k] < e200[k])
        if touched_from_above or touched_from_below:
            rejected_recently[k] = True
    # roll forward: "a rejection happened in the last `lookback` bars"
    any_recent = np.zeros(n, dtype=bool)
    s = pd.Series(rejected_recently)
    any_recent = s.rolling(lookback, min_periods=1).max().astype(bool).values
    return any_recent


if __name__ == "__main__":
    df, point = load_m15("GOLD_M15_native.csv", trim_gold=True)
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    n = len(df)
    e200 = ema(close_a, 200)
    atr = wilder_atr(high_a, low_a, close_a, 14)
    print(f"GOLD M15 real-data window: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")

    print("=" * 100)
    print("0. BASELINE - confirm_bars=2, no gate")
    print("=" * 100)
    run("0. BASELINE", df, point)
    print()

    print("=" * 100)
    print("1. SUPPRESS crosses following a recent 200EMA rejection (touch_atr x lookback_bars grid)")
    print("=" * 100)
    for touch_atr in (0.15, 0.3, 0.5):
        for lookback in (5, 10, 20):
            rejected = make_rejection_detector(high_a, low_a, close_a, e200, atr, touch_atr, lookback)
            def gate_avoid_rejection(cross_bar, is_buy, rejected=rejected):
                return not rejected[cross_bar]
            run(f"1. avoid 200EMA-rejection (touch={touch_atr} ATR, lookback={lookback})",
                df, point, gate=gate_avoid_rejection)
        print()

    print("Honest K this file: 3 x 3 = 9 configs, on top of 46 already tried for this overlay")
    print("(running total 55). Any surviving config here still needs a walk-forward split check")
    print("before going anywhere near the EA - the BB-mid filter looked fine on the full window")
    print("too, and failed outright once split.")
