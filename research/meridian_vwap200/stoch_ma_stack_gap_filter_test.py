"""
Per direct request, from TWO annotated live charts:

Chart 1: stochastic crosses up out of oversold, but price sits a LARGE
gap away from the 21EMA - "there is room should it reject to come
further down" - i.e. a big extension (gap) between price and the fast
EMA at signal time means more room for a failed reversal, so the
signal is less trustworthy when that gap is large.

Chart 2: a sell setup where price rejects the 200EMA and closes below
the 50EMA, with the 21/50/200 EMAs STACKED in bearish order
(21<50<200) - i.e. the signal is more trustworthy when all three EMAs
already agree on the trend direction.

This combines both into ONE filter on top of the existing baseline
zone-cross entry (same trigger as every stochastic test tonight):
  (a) EMA21/50/200 must be STACKED in the signal's own direction
      (buy: 21>50>200, sell: 21<50<200) at the signal bar, and
  (b) the gap between close and EMA21, in ATR, must be <= GAP_ATR_MAX
      (NOT already extended far from the fast EMA).//
Both conditions checked on CLOSED bars only (signal bar itself), same-
timeframe EMAs (21/50/200 on M15 directly) - no cross-timeframe lookup,
so none of the H4-lookahead risk that sank the first MA-filter attempt.
Distinct from EMA2400 single-MA filter (3rd attempt) and the H4 trend
filter (1st attempt) and the MA-order-flip-confirmation test (a
DIFFERENT construction - that one required a confirmation bar AFTER
the signal; this one filters the signal bar itself, no confirmation
delay).

Same validated swing-stop/1:2RR/opposite-stoch-cross exit used
throughout tonight. Tested on GOLD, SILVER, BTCUSD M15.

Honest K=1 per instrument for this exact filter construction (4th
MA-related filter idea tried tonight, after H4-trend/low-vol-regime/
EMA2400 all failed - tracking per CLAUDE.md's running K count).
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
EMA_FAST, EMA_MID, EMA_SLOW = 21, 50, 200
ATR_PERIOD = 14
GAP_ATR_MAX = 1.5
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


def wilder_atr(h, l, c, period):
    n = len(c)
    atr = np.full(n, np.nan)
    if n < period + 1:
        return atr
    tr = np.maximum(h[1:] - l[1:], np.maximum(np.abs(h[1:] - c[:-1]), np.abs(l[1:] - c[:-1])))
    atr[period] = tr[:period].mean()
    for i in range(period + 1, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i - 1]) / period
    return atr


def build_trades(df, point):
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
    n_pass_stack, n_pass_gap, n_candidates = 0, 0, 0
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
        n_candidates += 1

        stacked = (e21[i] > e50[i] > e200[i]) if trig_dir > 0 else (e21[i] < e50[i] < e200[i])
        if not stacked:
            i += 1
            continue
        n_pass_stack += 1

        gap_atr = abs(close[i] - e21[i]) / atr[i]
        if gap_atr > GAP_ATR_MAX:
            i += 1
            continue
        n_pass_gap += 1

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

    print(f"  candidates(zone-cross)={n_candidates}  pass-stack={n_pass_stack}  "
          f"pass-stack+gap={n_pass_gap}  (gap<= {GAP_ATR_MAX} ATR)")
    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - zone-cross + EMA21/50/200 STACK filter + gap<={GAP_ATR_MAX}ATR "
          f"filter\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - MA-stack + gap filter", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument for this exact construction (4th MA-related")
    print(f"  filter idea tried tonight - H4-trend, low-vol-regime, EMA2400 slow filter,")
    print(f"  all three failed).")
