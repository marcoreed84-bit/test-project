"""
Per direct request: the pure EMA21/50 crossover entry
(ema21_50_pure_crossover_test.py) can't hold all the way to the next
opposite crossover - that's far too laggy an exit, giving back most of
the move before the signal even fires. This tests a faster exit
instead: the trade closes as soon as price CLOSES back on the wrong
side of the FASTER EMA21 (a much quicker warning than waiting for the
full EMA21/50 re-cross), with a hard swing stop underneath/above for
protection against a sharp reversal that blows through EMA21 in one
bar.

Rule: entry unchanged (EMA21 crosses EMA50, direction matches). Exit
is the FIRST of:
  - close moves back to the wrong side of EMA21 (close < EMA21 for a
    long, close > EMA21 for a short) - the fast reversal warning,
  - a hard swing stop (10-bar low/high at entry, never trailed, pure
    protection against a gap/spike),
  - time cap fallback.
No fixed take-profit target - this is still trend-following, exits are
purely risk/reversal-driven, matching "let the trade run until there's
a real sign it's turning."

Tested on GOLD, SILVER, BTCUSD M15. Honest K=1 per instrument - new
exit mechanism on the same entry just validated.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report
from vwap_open_scenarios_test import ema

EMA_FAST, EMA_SLOW = 21, 50
SWING_BARS = 10
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


def build_trades(df, point):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    e21_a = ema(close_a, EMA_FAST)
    e50_a = ema(close_a, EMA_SLOW)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    e21, e50 = e21_a.tolist(), e50_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(e50[i])) for i in range(n)]

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
            crossDown[i] = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]

    results = []
    start = EMA_SLOW + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 1 if crossUp[i] else (-1 if crossDown[i] else 0)
        if dir_ == 0:
            i += 1
            continue

        swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
        if dir_ * (close[i] - swing) <= 0.0:
            i += 1
            continue
        fill_i = i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
        stop_px = swing
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if valid[j]:
                reversal = (close[j] < e21[j]) if dir_ > 0 else (close[j] > e21[j])
                if reversal:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-EMA21-REVERSAL"
                    break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - EMA21/50 crossover entry, FAST exit on close back past EMA21 "
          f"(+ hard stop)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - EMA crossover, fast EMA21-reversal exit", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - new exit mechanism, same entry.")
