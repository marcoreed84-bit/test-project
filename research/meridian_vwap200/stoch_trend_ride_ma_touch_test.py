"""
Direct request, follow-up to the MA21/50 trend+rejection FILTER test
(which filtered the existing deep-zone cross and found no edge): "even
if price is riding the moving average, the [stochastic] cross still
happens" - in a real trend, pullbacks to the 21/50 EMA are often
SHALLOW and never reach the deep 20/80 zone the existing construction
requires, so a genuine trend-continuation cross at the MA would never
even register as a signal under the old rule. This is a genuinely NEW
entry construction, not a filter on the old one.

Rule: price in a trend (close above BOTH EMA21 and EMA50 for a buy,
below both for a sell). A BUY fires when %K crosses UP through %D
while price's LOW on the signal bar is within MA_TOUCH_ATR x ATR of
EMA21 or EMA50 (a genuine touch/ride, not a deep zone requirement -
%K can be anywhere, including nowhere near oversold). SELL is the
mirror (HIGH within MA_TOUCH_ATR of either MA). Same swing stop
(10-bar)/1:2RR/opposite-cross exit as the zone-cross construction,
WITH stop/target enforced every bar (the bug found and fixed in
classic_stoch_21_5_5_btc_test.py earlier tonight - not repeating that
mistake here).

Tested on GOLD, SILVER, BTCUSD M15 (point size read from each CSV's
own header, GOLD trimmed to its real-data window starting 2014-06-13).

Honest K=1 per instrument - first test of this entry construction on
any of the three.
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
from vwap_open_scenarios_test import ema, wilder_atr

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
EMA_FAST, EMA_SLOW = 21, 50
MA_TOUCH_ATR = 0.3
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
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    ema_fast_a = ema(close_a, EMA_FAST)
    ema_slow_a = ema(close_a, EMA_SLOW)
    atr_a = wilder_atr(high_a, low_a, close_a, 14)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    ema_fast, ema_slow, atr = ema_fast_a.tolist(), ema_slow_a.tolist(), atr_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW, 14) + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i] or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue

        dir_ = 0
        if crossUp[i] and close[i] > ema_fast[i] and close[i] > ema_slow[i]:
            touch = min(abs(low[i] - ema_fast[i]), abs(low[i] - ema_slow[i])) <= MA_TOUCH_ATR * atr[i]
            if touch:
                dir_ = 1
        elif crossDown[i] and close[i] < ema_fast[i] and close[i] < ema_slow[i]:
            touch = min(abs(high[i] - ema_fast[i]), abs(high[i] - ema_slow[i])) <= MA_TOUCH_ATR * atr[i]
            if touch:
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


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    print(f"\n{'#'*100}\n{label} M15 - TREND-RIDE entry: stoch cross while price touches EMA21/50 "
          f"(trend intact, no deep-zone requirement)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    trades = build_trades(df, point)
    report(f"{label} M15 - TREND-RIDE MA-touch entry", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - first test of this trend-ride MA-touch entry")
    print(f"  construction (genuinely new, not a filter on the zone-cross entry).")
