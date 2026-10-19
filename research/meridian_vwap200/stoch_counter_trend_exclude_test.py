"""
Per direct request: "test filtering out the counter-trend signals
directly." The diagnostic (stoch_ma_side_failure_rate_diagnostic.py)
found buy signals with price below BOTH EMA21/50 fail (re-cross into
oversold) ~81-85% of the time vs ~51-55% when above both - this tests
whether simply EXCLUDING those counter-trend-only signals (keeping
with-trend AND mixed signals, not forcing a trend+rejection
requirement like the earlier filter test did) changes real %PF.

Different from stoch_ma_trend_rejection_filter_test.py (which REQUIRED
trend-alignment AND a rejection bounce, cutting ~95% of trades and
making %PF worse on Gold/Silver) - this is a much lighter touch: only
removes the single worst bucket from the diagnostic (purely
counter-trend, price below both EMAs for a buy / above both for a
sell), keeps everything else including mixed-EMA signals.

Same corrected (stop/target enforced) Stoch(21,5,5)/20-80 zone-cross
construction as the project's main reference, so results compare
directly against the already-established baselines (Gold 0.700,
Silver 0.230, BTC 0.201 - stoch_ma_trend_rejection_filter_test.py).

Honest K=1 per instrument for this exclusion filter (new, lighter
construction than the earlier trend+rejection filter).
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
from vwap_open_scenarios_test import ema

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_SLOW = 21, 50
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


def build_trades(df, point, exclude_counter_trend):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    ema_fast_a = ema(close_a, EMA_FAST)
    ema_slow_a = ema(close_a, EMA_SLOW)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    ema_fast, ema_slow = ema_fast_a.tolist(), ema_slow_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW) + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i] or np.isnan(ema_fast[i]) or np.isnan(ema_slow[i]):
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

        if exclude_counter_trend:
            below_both = close[i] < ema_fast[i] and close[i] < ema_slow[i]
            above_both = close[i] > ema_fast[i] and close[i] > ema_slow[i]
            counter_trend = (dir_ > 0 and below_both) or (dir_ < 0 and above_both)
            if counter_trend:
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
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - Stoch(21,5,5) zone-cross, counter-trend-only signals EXCLUDED\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")

    base = build_trades(df, point, exclude_counter_trend=False)
    report(f"{label} M15 - BASELINE (all signals)", base, full_days, split_dir=True)

    filt = build_trades(df, point, exclude_counter_trend=True)
    report(f"{label} M15 - COUNTER-TREND-ONLY EXCLUDED", filt, full_days, split_dir=True)

    return base, filt


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument (new, lighter-touch filter than the earlier")
    print(f"  trend+rejection construction).")
