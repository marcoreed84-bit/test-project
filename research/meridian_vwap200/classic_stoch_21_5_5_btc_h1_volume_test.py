"""
Volume-confirmation filter for the best BTC construction found tonight
(H1, Stoch(21,5,5) zone-cross entry, swing stop + 1:2 R:R, grace=10
stop-trail exit - classic_stoch_21_5_5_btc_h1_stop_trail_test.py,
full-history %PF=0.614, OOS %PF=0.819, but WORSE than random-timing
per the null test), per direct request: has volume been tried with
this stochastic construction. It has not, until now.

Rule: at the signal (cross) bar, require tick_volume to be above its
own trailing VOL_LOOKBACK-bar average by at least VOL_MULT times -
i.e. only take a cross that happens on real conviction/participation,
not a quiet low-volume drift. Tested VOL_MULT in {1.0 (=no real
filter, baseline), 1.2, 1.5, 2.0} with VOL_LOOKBACK=20 H1 bars.

Same entry/stop/target/exit construction otherwise (grace_bars=10,
real spread). Tested on BTCUSD H1 full real history.

Honest K: this project's BTC stochastic exploration today is now at
K=27 (23 before this file + 4 volume-threshold values here).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR
from classic_stoch_21_5_5_btc_h1_test import load_btc_m15

TIME_CAP_BARS = 300
GRACE_BARS = 10
VOL_LOOKBACK = 20


def load_btc_h1_with_volume():
    df15, point = load_btc_m15()
    df15 = df15.set_index("time")
    h1 = df15.resample("1h", label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last",
         "spread": "max", "tick_volume": "sum"}
    ).dropna()
    return h1.reset_index(), point


def build_trades(df, point, vol_mult):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    vol_a = df["tick_volume"].values.astype(float)
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    vol_avg_a = pd.Series(vol_a).rolling(VOL_LOOKBACK, min_periods=VOL_LOOKBACK).mean().shift(1).values
    # shift(1): the average of the PRECEDING VOL_LOOKBACK bars, not including
    # the signal bar itself - causal, no lookahead

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    vol, vol_avg = vol_a.tolist(), vol_avg_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + VOL_LOOKBACK + 5
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

        va = vol_avg[i]
        if va is None or np.isnan(va) or va <= 0 or vol[i] < vol_mult * va:
            i += 1
            continue   # not enough volume conviction on this cross

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

        pending_exit_bar = None
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
                favorable = (dir_ > 0 and crossUp[j]) or (dir_ < 0 and crossDown[j])
                opposite  = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if pending_exit_bar is not None and favorable:
                    new_swing = min(low[j - SWING_BARS:j]) if dir_ > 0 else max(high[j - SWING_BARS:j])
                    if dir_ > 0 and new_swing > stop_px:
                        stop_px = new_swing
                    elif dir_ < 0 and new_swing < stop_px:
                        stop_px = new_swing
                    pending_exit_bar = None
                if pending_exit_bar is None and opposite:
                    pending_exit_bar = j + GRACE_BARS
                if pending_exit_bar is not None and j >= pending_exit_bar:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-STOCH-GRACE"
                    break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run(vol_mult):
    df, point = load_btc_h1_with_volume()
    n = len(df)
    label = f"volume >= {vol_mult}x its trailing {VOL_LOOKBACK}-bar average" if vol_mult > 1.0 else "NO volume filter (baseline)"
    print(f"\n{'#'*100}\nBTCUSD H1 - Stoch(21,5,5) entry + swing stop/1:2RR + grace=10 trail, requiring {label}\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, vol_mult)
    report(f"BTCUSD H1 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, vol_mult)
    report(f"BTCUSD H1 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, vol_mult)
    report(f"BTCUSD H1 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    for vm in (1.0, 1.2, 1.5, 2.0):
        run(vm)
    print(f"\n\n  Honest K: this project's BTC stochastic exploration today is now at K=27")
    print(f"  (23 before this file + 4 volume-threshold values here).")
