"""
Legitimate (non-lookahead) version of the K/D-widening idea from
stoch_kd_widening_momentum_test.py: that file found a large correlation
between "did %K/%D's gap widen in the 3 bars after the signal" and
trade outcome, but flagged it as unusable AS AN ENTRY FILTER because it
needs information from 3 bars after the signal, which isn't available
at entry time.

This tests the legitimate reframing: an EARLY-EXIT / trade-management
rule. At WIDEN_CHECK_BAR bars after fill, check whether %K/%D's gap has
widened since entry (real-time information available at that point,
not lookahead). If it has NOT widened (gap same or smaller), exit the
trade right there instead of waiting for the stop/target/opposite-
cross rule. If it HAS widened, let the trade run under the normal
rules unchanged.

Same Stoch(21,5,5)/20-80 zone-cross construction, stop/target enforced,
tested on GOLD/SILVER/BTCUSD M15. Honest K=1 per instrument (new exit
modification, genuinely different question from the entry-timing tests
tonight).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
WIDEN_CHECK_BAR = 3
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


def build_trades(df, point, use_early_exit):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 0
        if crossUp[i] and k[i] < ZONE_LOW:
            dir_ = 1
        elif crossDown[i] and k[i] > ZONE_HIGH:
            dir_ = -1
        if dir_ == 0:
            i += 1
            continue

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
        gap_at_entry = abs(k[i] - d[i])
        check_bar = fill_i + WIDEN_CHECK_BAR

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
            if valid[j] and valid[j - 1]:
                opposite = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if opposite:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-STOCH"
                    break
            if use_early_exit and j == check_bar and valid[j]:
                gap_now = abs(k[j] - d[j])
                if gap_now <= gap_at_entry:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-KD-NOWIDEN"
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
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - Stoch(21,5,5)/20-80, early exit if K/D gap hasn't widened "
          f"by bar {WIDEN_CHECK_BAR}\n{'#'*100}")

    base = build_trades(df, point, use_early_exit=False)
    report(f"{label} M15 - BASELINE (no early exit)", base, full_days, split_dir=True)

    early = build_trades(df, point, use_early_exit=True)
    report(f"{label} M15 - WITH K/D-no-widen early exit", early, full_days, split_dir=True)

    return base, early


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument (new exit modification).")
