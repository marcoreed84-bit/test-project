"""
Follow-up to ema21_50_angle_parallel_200ema_test.py. User's new idea: gate
the EMA21/50 cross entry on the Bollinger middle band (20-period SMA,
2 std-dev bands - standard settings, no custom tuning). For a SELL cross:
require EMA21 roughly in line with the middle band AND price closes BELOW
the middle band. For a BUY cross: EMA21 in line with the middle band AND
price closes ABOVE it. Tested two sub-conditions separately (price-side
alone, and EMA21-near-midline alone) then combined, since it's unclear
which part (if either) carries the signal.

Base construction unchanged: pure EMA21/50 crossover, hold-to-next-
opposite-cross, confirm_bars=2 (the EA's real current default) already
baked in - this gate is tested as an ADDITIONAL condition on top, same
pattern as every filter test in this series.

Honest K: running total for this overlay's filter search was already 36
(gap_confirm_filter_test.py: 22, angle_parallel_200ema_test.py: 14).
This file adds however many configs below.
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
BB_PERIOD = 20
BB_STD = 2.0


def bollinger_mid(close, period=BB_PERIOD):
    return pd.Series(close).rolling(period, min_periods=period).mean().values


def build_trades(df, point, confirm_bars=CONFIRM_BARS, gate=None):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    e21 = ema(close_a, EMA_FAST)
    e50 = ema(close_a, EMA_SLOW)
    bb_mid = bollinger_mid(close_a)
    atr = wilder_atr(high_a, low_a, close_a, 14)

    close, spread = close_a.tolist(), spread_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(atr[i]) or np.isnan(bb_mid[i])) for i in range(n)]

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
            crossDown[i] = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]

    results = []
    start = EMA_SLOW + BB_PERIOD + 5
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


if __name__ == "__main__":
    df, point = load_m15("GOLD_M15_native.csv", trim_gold=True)
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    n = len(df)
    e21 = ema(close_a, EMA_FAST)
    bb_mid = bollinger_mid(close_a)
    atr = wilder_atr(high_a, low_a, close_a, 14)
    print(f"GOLD M15 real-data window: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)")
    print(f"Bollinger middle band = {BB_PERIOD}-period SMA (standard settings)\n")

    print("=" * 100)
    print("0. BASELINE - confirm_bars=2, no BB gate (current EA v2.01 behavior)")
    print("=" * 100)
    run("0. BASELINE", df, point)
    print()

    print("=" * 100)
    print("1. PRICE-SIDE ONLY: close beyond BB-mid in the cross direction (buy: close>mid, sell: close<mid)")
    print("=" * 100)
    def gate_price_side(cross_bar, is_buy):
        return (close_a[cross_bar] > bb_mid[cross_bar]) if is_buy else (close_a[cross_bar] < bb_mid[cross_bar])
    run("1. price beyond BB-mid", df, point, gate=gate_price_side)
    print()

    print("=" * 100)
    print("2. EMA21-NEAR-BBMID ONLY: |EMA21 - BBmid| <= tol x ATR (various tolerances)")
    print("=" * 100)
    for tol in (0.1, 0.2, 0.3, 0.5, 1.0):
        def gate_ema_near(cross_bar, is_buy, tol=tol):
            if np.isnan(atr[cross_bar]) or atr[cross_bar] <= 0:
                return False
            return abs(e21[cross_bar] - bb_mid[cross_bar]) <= tol * atr[cross_bar]
        run(f"2. |EMA21-BBmid|<={tol} ATR", df, point, gate=lambda cb, b, tol=tol: gate_ema_near(cb, b, tol))
    print()

    print("=" * 100)
    print("3. COMBINED: price beyond BB-mid AND EMA21 near BB-mid (the literal request)")
    print("=" * 100)
    for tol in (0.2, 0.3, 0.5, 1.0):
        def gate_combo(cross_bar, is_buy, tol=tol):
            if np.isnan(atr[cross_bar]) or atr[cross_bar] <= 0:
                return False
            price_ok = (close_a[cross_bar] > bb_mid[cross_bar]) if is_buy else (close_a[cross_bar] < bb_mid[cross_bar])
            if not price_ok:
                return False
            return abs(e21[cross_bar] - bb_mid[cross_bar]) <= tol * atr[cross_bar]
        run(f"3. price-side + |EMA21-BBmid|<={tol} ATR", df, point, gate=lambda cb, b, tol=tol: gate_combo(cb, b, tol))
    print()
    print("Honest K this file: 1 (price-side) + 5 (ema-near grid) + 4 (combo grid) = 10 configs,")
    print("on top of 36 already tried for this overlay (running total 46).")
