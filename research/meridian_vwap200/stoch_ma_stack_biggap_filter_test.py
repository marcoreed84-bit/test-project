"""
Correction per direct request: stoch_ma_stack_gap_filter_test.py filtered
OUT signals with a large gap between price and EMA21 (treating extension
as risk). That was the wrong direction - the user's point was the
opposite: a LARGE gap means the move still has room to run before
hitting resistance, i.e. the signal is MORE valid with a big gap, not
less. This flips the gap condition to a MINIMUM instead of a maximum,
keeping everything else (stacked EMA21/50/200, same baseline zone-cross
entry, same validated exit) identical to the prior test for a clean A/B.

Two variants run per instrument:
  (A) stack + gap >= GAP_ATR_MIN (the corrected combined filter)
  (B) gap >= GAP_ATR_MIN alone, no stack requirement (isolates whether
      the gap condition on its own is doing anything, independent of
      the stack condition which already failed badly in its own right
      combined with the WRONG gap direction - worth seeing on its own
      before concluding either piece is bad)

Honest K=1 per instrument for EACH variant (2 new constructions this
round, on top of the 4 MA-related filter ideas that already failed
tonight - running total before any null test here: 6).
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
from stoch_ma_stack_gap_filter_test import wilder_atr

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_MID, EMA_SLOW = 21, 50, 200
ATR_PERIOD = 14
GAP_ATR_MIN = 1.0
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


def build_trades(df, point, require_stack):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    e21_a = ema(close_a, EMA_FAST)
    e50_a = ema(close_a, EMA_MID)
    e200_a = ema(close_a, EMA_SLOW)
    atr_a = wilder_atr(high_a, low_a, close_a, ATR_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    e21, e50, e200 = e21_a.tolist(), e50_a.tolist(), e200_a.tolist()
    atr = atr_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    n_pass = 0
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW, ATR_PERIOD + 1) + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        trig_dir = 0
        if crossUp[i] and k[i] < ZONE_LOW:
            trig_dir = 1
        elif crossDown[i] and k[i] > ZONE_HIGH:
            trig_dir = -1
        if trig_dir == 0:
            i += 1
            continue
        if np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(e200[i]) or np.isnan(atr[i]) or atr[i] <= 0.0:
            i += 1
            continue

        if require_stack:
            stacked = (e21[i] > e50[i] > e200[i]) if trig_dir > 0 else (e21[i] < e50[i] < e200[i])
            if not stacked:
                i += 1
                continue

        gap_atr = abs(close[i] - e21[i]) / atr[i]
        if gap_atr < GAP_ATR_MIN:
            i += 1
            continue
        n_pass += 1

        dir_ = trig_dir
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

    print(f"  pass={n_pass}  (gap >= {GAP_ATR_MIN} ATR, stack required={require_stack})")
    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")

    print(f"\n  --- (A) stack + gap>={GAP_ATR_MIN}ATR ---")
    trades_a = build_trades(df, point, require_stack=True)
    report(f"{label} M15 - stack + big-gap filter", trades_a, full_days, split_dir=True)

    print(f"\n  --- (B) gap>={GAP_ATR_MIN}ATR alone, no stack ---")
    trades_b = build_trades(df, point, require_stack=False)
    report(f"{label} M15 - big-gap filter only", trades_b, full_days, split_dir=True)
    return trades_a, trades_b


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument PER VARIANT (A and B each count separately).")
