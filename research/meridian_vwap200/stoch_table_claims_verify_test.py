"""
Verifying an externally-sourced table of "best" stochastic settings for
Gold/Silver/BTC at 5m and 15m (pasted in by the user, source unknown -
treated as an unverified claim, not fact, per this project's standing
rule to check external claims against real data before trusting them).

Claimed table:
  GOLD   M5:  (8,3,3)   80/20 -> claimed 85/15
  GOLD   M15: (14,3,3)  80/20
  SILVER M5:  (14,3,3)  90/10
  SILVER M15: (21,3,3)  85/15
  BTC    M5:  (14,3,3)  80/20
  BTC    M15: (21,5,5)  80/20

Same corrected (stop/target ENFORCED) Stoch zone-cross construction
used throughout tonight: Low/High+SMA stochastic, entry on cross-in-
zone, swing stop (10-bar)/1:2RR target, exit on the SAME stoch's
opposite cross (no zone requirement), real variable spread, fill on
next bar close. BTC M15 (21,5,5, 80/20) is the exact construction
already tested extensively tonight (full-history %PF=0.201) - not
re-run here, cited directly instead.

Gold trimmed to its real-data window (2014-06-13+, known M15/M5
contamination gotcha - applied to both timeframes out of caution).
Silver and BTC use full history. Point size read from each CSV's own
header line.

Honest K=1 per NEW config tested here (5 new - Gold M5, Gold M15,
Silver M5, Silver M15, BTC M5 - BTC M15 is a citation of an existing
result, not a new test).
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

SWING_BARS = 10
RR = 2.0
TIME_CAP_BARS = 300
GOLD_REAL_START = pd.Timestamp("2014-06-13")


def load(symbol_file, trim_gold=False):
    path = os.path.join(DATA_DIR, symbol_file)
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    if trim_gold:
        df = df[df["time"] >= GOLD_REAL_START].reset_index(drop=True)
    return df, point


def build_trades(df, point, k_period, slowing, d_period, zone_low, zone_high):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, k_period, slowing, d_period)

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
    start = k_period + slowing + d_period + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 0
        if crossUp[i] and k[i] < zone_low:
            dir_ = 1
        elif crossDown[i] and k[i] > zone_high:
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
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run_config(label, symbol_file, trim_gold, k_period, slowing, d_period, zone_low, zone_high):
    df, point = load(symbol_file, trim_gold=trim_gold)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label}: Stoch({k_period},{slowing},{d_period}) zone {zone_low}/{zone_high}\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({len(df)} bars, point={point})")
    trades = build_trades(df, point, k_period, slowing, d_period, zone_low, zone_high)
    report(label, trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_config("GOLD M5  (claimed 8,3,3 / 85-15)",   "GOLD_M5.csv",   True,  8,  3, 3, 15.0, 85.0)
    run_config("GOLD M15 (claimed 14,3,3 / 80-20)",   "GOLD_M15_native.csv", True, 14, 3, 3, 20.0, 80.0)
    run_config("SILVER M5  (claimed 14,3,3 / 90-10)", "SILVER_M5.csv", False, 14, 3, 3, 10.0, 90.0)
    run_config("SILVER M15 (claimed 21,3,3 / 85-15)", "SILVER_M15_native.csv", False, 21, 3, 3, 15.0, 85.0)
    run_config("BTC M5  (claimed 14,3,3 / 80-20)",    "BTCUSD_M5.csv", False, 14, 3, 3, 20.0, 80.0)
    print(f"\n{'#'*100}\nBTC M15 (claimed 21,5,5 / 80-20) - ALREADY TESTED tonight, cited not re-run\n{'#'*100}")
    print(f"  Full-history %PF=0.201 (classic_stoch_21_5_5_btc_test.py, corrected)")

    print(f"\n\n  Honest K=1 per NEW config (Gold M5/M15, Silver M5/M15, BTC M5 - 5 new).")
    print(f"  BTC M15 is a citation, not a new test.")
