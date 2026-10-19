"""
Per direct request: drop the stochastic entirely and test the EMA
stack idea as its OWN entry, not a filter on the stochastic cross.
Entry = the FIRST bar where EMA21/50/200 become freshly stacked in
trend order (21>50>200 for a buy, 21<50<200 for a sell) - a state
TRANSITION, not "every bar while stacked" (which would re-signal
continuously). Exit = the first of: swing stop, 1:2 R:R target, or the
stack breaking (losing its order) - no stochastic anywhere in this
construction.

Honest K=1 per instrument - new, fully independent construction from
every stochastic+MA-filter variant tried tonight (none of which
involved the EMA stack being the entry itself).
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

SWING_BARS = 10
RR = 2.0
EMA_FAST, EMA_MID, EMA_SLOW = 21, 50, 200
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
    e50_a = ema(close_a, EMA_MID)
    e200_a = ema(close_a, EMA_SLOW)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    e21, e50, e200 = e21_a.tolist(), e50_a.tolist(), e200_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(e200[i])) for i in range(n)]

    def stack_dir(i):
        if not valid[i]:
            return 0
        if e21[i] > e50[i] > e200[i]:
            return 1
        if e21[i] < e50[i] < e200[i]:
            return -1
        return 0

    results = []
    start = EMA_SLOW + SWING_BARS + 5
    i = start
    while i < n - 1:
        sd_prev = stack_dir(i - 1)
        sd_cur = stack_dir(i)
        fresh_dir = sd_cur if (sd_cur != 0 and sd_cur != sd_prev) else 0
        if fresh_dir == 0:
            i += 1
            continue

        dir_ = fresh_dir
        swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
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
            if stack_dir(j) != dir_ and stack_dir(j) != 0:
                scj = spread[j] * point
                exit_i = j
                exit_px = close[j] - (scj if dir_ > 0 else -scj)
                reason = "EXIT-STACKBREAK"
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
    print(f"\n{'#'*100}\n{label} M15 - EMA21/50/200 freshly-stacked entry (NO stochastic) - "
          f"stop/target/stack-break exit\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - pure EMA-stack entry", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - fully independent construction, no stochastic.")
