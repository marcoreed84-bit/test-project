"""
Per direct request: test the 21/50 EMA crossover ON ITS OWN as the
entry - no stochastic anywhere. "When they cross price goes in that
direction... how far is dependent on the next cross" - i.e. enter when
EMA21 crosses EMA50, direction matches the cross, and HOLD until the
next opposite crossover (classic trend-following, not a fixed stop/
target) - the literal construction described, tested as-is before any
modification.

Rule: BUY when EMA21 crosses above EMA50 (close confirms the cross -
checked on the EMA values themselves, not price). SELL when EMA21
crosses below EMA50. Exit on the NEXT opposite crossover - fully
trend-following, no fixed stop-loss or take-profit, no time cap beyond
the next signal. Real spread both legs, fill on next bar close.

Tested on GOLD, SILVER, BTCUSD M15 (GOLD trimmed to its real-data
window, 2014-06-13+). Honest K=1 per instrument - first test of this
exact construction tonight (distinct from every EMA-as-filter variant
already tried - here the EMA cross IS the whole system, not a filter
on something else).
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
    close_a = df["close"].values
    spread_a = df["spread"].values
    n = len(df)
    e21_a = ema(close_a, EMA_FAST)
    e50_a = ema(close_a, EMA_SLOW)

    close, spread = close_a.tolist(), spread_a.tolist()
    e21, e50 = e21_a.tolist(), e50_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(e50[i])) for i in range(n)]

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
            crossDown[i] = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]

    results = []
    start = EMA_SLOW + 5
    i = start
    posDir, open_fill_i, open_entry_px = 0, None, None
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

        if dir_ != 0 and posDir == 0:
            fill_i = i + 1
            if fill_i < n:
                sc = spread[fill_i] * point
                entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
                posDir, open_fill_i, open_entry_px = dir_, fill_i, entry_px

        i += 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - PURE EMA21/50 crossover (no stochastic, exit on next opposite "
          f"cross)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - Pure EMA21/50 crossover", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - fully independent construction, no")
    print(f"  stochastic, no fixed stop/target, pure trend-following.")
