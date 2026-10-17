"""
Higher-timeframe (H4) trend-alignment filter for the BTC classic
Stoch(21,5,5) construction, per direct request: in a downtrend only
take sells, in an uptrend only take buys (cancel counter-trend
signals). This project got burned once already on an H4-filter
lookahead bug (see CLAUDE.md's 2026-10-04 entry and
research/meridian/audit_2026-09-28/h4_trend_filter_test.py) - a naive
searchsorted(h4_time, t, side="left")-1 picked the H4 candle still
FORMING for any M-bar not exactly on an H4 boundary, leaking up to ~4h
of future H4 price into the filter. This file uses the SAME corrected,
non-lookahead lookup the project standardized on afterward:
  searchsorted(h4_time, t + bar_len, side="right") - 2
which only ever returns the H4 bar that has ACTUALLY CLOSED as of
time t.

H4 bars here are resampled directly from the same BTCUSD_M15_native.csv
(a real aggregation of the same feed, not a separate/different one -
no data-quality concern). Trend direction = close vs a 50-period EMA
on the H4 close series (same construction used in the project's prior
H4-filter work).

Entry/stop/target/exit otherwise identical to classic_stoch_21_5_5_btc_
entry_confirm_test.py's confirm_bars=0 case (the un-filtered baseline),
so the ONLY thing that changes is whether a signal against the H4
trend is thrown away.

Tested on BTCUSD M15 full real history, real spread. Honest K: this
project's BTC stochastic exploration today is now at K=16 (15 before
this file + 1 H4-trend-filter variant here).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import load_btc_m15, K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR
from vwap_open_scenarios_test import ema

TIME_CAP_BARS = 300
H4_EMA_PERIOD = 50


def build_h4_trend(df):
    """Resample the M15 df to H4 OHLC, compute a 50-EMA trend direction,
    then map each M15 bar to the MOST RECENTLY CLOSED H4 bar's trend -
    using the project's corrected non-lookahead lookup."""
    h4 = (df.set_index("time")["close"].resample("4h", label="right", closed="right")
          .ohlc().dropna())
    h4_close = h4["close"].values
    h4_time = h4.index.values.astype("datetime64[ns]")
    h4_ema = ema(h4_close, H4_EMA_PERIOD)
    h4_trend_up = h4_close > h4_ema   # True = uptrend, False = downtrend (NaN EMA -> False, filtered by valid)
    h4_ema_valid = ~np.isnan(h4_ema)

    m15_time = df["time"].values.astype("datetime64[ns]")
    bar_len = np.timedelta64(15, "m")
    h4_idx = np.searchsorted(h4_time, m15_time + bar_len, side="right") - 2
    h4_idx = np.clip(h4_idx, 0, len(h4_time) - 1)
    valid = (h4_idx >= 1) & h4_ema_valid[h4_idx]
    return h4_trend_up[h4_idx], valid


def build_trades(df, point, use_h4_filter):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    h4_up, h4_valid = build_h4_trend(df)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    h4_up_l, h4_valid_l = h4_up.tolist(), h4_valid.tolist()
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

        if use_h4_filter:
            if not h4_valid_l[i]:
                i += 1
                continue
            trend_up = h4_up_l[i]
            if dir_ > 0 and not trend_up:   # buy signal, but H4 is in a downtrend
                i += 1
                continue
            if dir_ < 0 and trend_up:       # sell signal, but H4 is in an uptrend
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


def run(use_h4_filter):
    df, point = load_btc_m15()
    n = len(df)
    label = f"WITH H4-trend alignment filter (50EMA, no-lookahead lookup)" if use_h4_filter else "NO filter (baseline)"
    print(f"\n{'#'*100}\nBTCUSD M15 - Stoch(21,5,5) entry + swing stop/1:2RR, {label}\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, use_h4_filter)
    report(f"BTCUSD M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, use_h4_filter)
    report(f"BTCUSD M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, use_h4_filter)
    report(f"BTCUSD M15 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run(False)
    run(True)
    print(f"\n\n  Honest K: this project's BTC stochastic exploration today is now at K=16")
    print(f"  (15 before this file + 1 H4-trend-filter variant here).")
