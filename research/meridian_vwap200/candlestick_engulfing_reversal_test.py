"""
Per direct request: "try a non-stochastic entry, like candlestick
reversal patterns." Fully non-stochastic construction - no stochastic
oscillator anywhere in this file, genuinely independent test.

Rule: classic bullish/bearish ENGULFING pattern occurring AT a local
price extreme (the pattern bar's low/high is the lowest/highest of the
preceding SWING_BARS bars - confirms it's a genuine reversal point, not
an engulfing pattern mid-trend with no exhaustion context):
  BULLISH: bar i-1 is bearish (close<open), bar i is bullish
    (close>open), bar i's body fully engulfs bar i-1's body
    (open[i]<=close[i-1] and close[i]>=open[i-1]), AND low[i] is the
    lowest low of the preceding SWING_BARS bars.
  BEARISH: mirror (bar i-1 bullish, bar i bearish engulfing it, high[i]
    is the highest high of the preceding SWING_BARS bars).

Exit: swing stop (same SWING_BARS low/high used for the entry
qualification) + fixed 1:2 R:R target - no stochastic opposite-cross
exit available since there's no stochastic in this construction. Time-
capped fallback same as every other file tonight. Real spread, fill on
next bar close.

Tested on GOLD, SILVER, BTCUSD M15 (GOLD trimmed to its real-data
window, 2014-06-13+). Honest K=1 per instrument - first test of this
construction, genuinely independent of every stochastic-based entry
tested tonight.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report

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


def build_trades(df, point):
    close_a, high_a, low_a, open_a = df["close"].values, df["high"].values, df["low"].values, df["open"].values
    spread_a = df["spread"].values
    n = len(df)

    close, high, low, open_ = close_a.tolist(), high_a.tolist(), low_a.tolist(), open_a.tolist()
    spread = spread_a.tolist()

    results = []
    start = SWING_BARS + 5
    i = start
    while i < n - 1:
        dir_ = 0
        prev_bear = close[i - 1] < open_[i - 1]
        cur_bull = close[i] > open_[i]
        bullish_engulf = prev_bear and cur_bull and open_[i] <= close[i - 1] and close[i] >= open_[i - 1]

        prev_bull = close[i - 1] > open_[i - 1]
        cur_bear = close[i] < open_[i]
        bearish_engulf = prev_bull and cur_bear and open_[i] >= close[i - 1] and close[i] <= open_[i - 1]

        if bullish_engulf and low[i] <= min(low[i - SWING_BARS:i]):
            dir_ = 1
        elif bearish_engulf and high[i] >= max(high[i - SWING_BARS:i]):
            dir_ = -1
        if dir_ == 0:
            i += 1
            continue

        swing = low[i] if dir_ > 0 else high[i]
        risk = dir_ * (close[i] - swing)
        if risk <= 0.0:
            i += 1
            continue
        fill_i = i + 1
        if fill_i >= n:
            i += 1
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
        i = exit_i + 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - ENGULFING reversal at a swing extreme (no stochastic)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - Engulfing-at-extreme entry", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - fully non-stochastic entry construction.")
