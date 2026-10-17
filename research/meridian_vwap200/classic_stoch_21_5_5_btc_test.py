"""
Exact backtest of the classic Stochastic(21,5,5) construction now drawn
on TradePanel_EA v1.28's chart overlay on BTCUSD M15, per direct
request - SAME settings (21,5,5) used for BOTH the entry stochastic
AND the exit stochastic (the EA lets them be set independently, but
the request was specifically "using the 21,5,5 for entry and exit").

Construction (mirrors SigClassicStoch()/ComputeStochSignals() in
TradePanel_EA.mq5 exactly):
  - Stochastic(21,5,5), Low/High price field, SMA smoothing (MT5's own
    native default - same formula as the EA, NOT this project's usual
    Close/Close+Smoothed convention).
  - ENTRY: %K crosses %D WHILE STILL INSIDE the zone - buy when
    cross-up happens with %K<20, sell when cross-down happens with
    %K>80.
  - EXIT: the SAME Stochastic(21,5,5)'s %K/%D cross AGAINST the open
    position's direction - NO zone requirement (textbook "exit on
    opposite cross"), only while a position is open. Fires once, then
    re-arms on the next entry.
  - Stop: the lowest low / highest high of the preceding 10 closed
    bars (InpSigSwingBars default in the EA).
  - Target: fixed 1:2 risk:reward off that stop distance (InpSigRR
    default in the EA).
  - Fill on the next bar's close +/- real spread, same convention as
    every other test in this project.

Tested on BTCUSD M15 (2013-01-02 to 2026-09-27, full real history,
real variable spread from the CSV's own spread column). Honest K: 1
(the user's own stated construction/settings, not swept or tuned - a
single eyeballed day on this exact chart prompted the request).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import pct_pf, report, TIME_CAP_BARS
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0


def load_btc_m15():
    path = os.path.join(DATA_DIR, "BTCUSD_M15_native.csv")
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.reset_index(drop=True), point


def build_trades(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    k, d = stochastic_lowhigh_sma(high, low, close, K_PERIOD, SLOWING, D_PERIOD)
    # entry and exit use the SAME Stochastic(21,5,5) per the request
    kE, dE = k, d

    results = []
    posDir = 0
    open_i = open_fill_i = None
    open_entry_px = None
    i = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    while i < n - 1:
        if k[i] == np.nan or np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(k[i - 1]) or np.isnan(d[i - 1]):
            i += 1
            continue
        crossUp = k[i - 1] <= d[i - 1] and k[i] > d[i]
        crossDown = k[i - 1] >= d[i - 1] and k[i] < d[i]
        dir_ = 0
        if crossUp and k[i] < ZONE_LOW:
            dir_ = 1
        elif crossDown and k[i] > ZONE_HIGH:
            dir_ = -1

        if dir_ != 0:
            swing_low = low[i - SWING_BARS:i].min()
            swing_high = high[i - SWING_BARS:i].max()
            swing = swing_low if dir_ > 0 else swing_high
            risk = dir_ * (close[i] - swing)
            if risk > 0.0:
                # a new entry flips/opens the position (reversal = implicit
                # close of the old one with no explicit exit event, same as
                # the EA's own overlay logic)
                posDir = dir_
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
                    stop_px = swing
                    target_px = entry_px + dir_ * RR * risk
                    open_i, open_fill_i = i, fill_i
                    open_entry_px, open_dir = entry_px, dir_
                    open_stop_px, open_target_px = stop_px, target_px
                    open_hard_limit = min(fill_i + time_cap_bars, n - 1)

        if posDir != 0 and not np.isnan(kE[i]) and not np.isnan(dE[i]) and not np.isnan(kE[i - 1]) and not np.isnan(dE[i - 1]):
            exCrossUp = kE[i - 1] <= dE[i - 1] and kE[i] > dE[i]
            exCrossDown = kE[i - 1] >= dE[i - 1] and kE[i] < dE[i]
            exitFires = (posDir > 0 and exCrossDown) or (posDir < 0 and exCrossUp)
            if exitFires and open_fill_i is not None and i > open_fill_i:
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    exit_px = close[fill_i] - (sc if open_dir > 0 else -sc)
                    pnl_pct = ((exit_px - open_entry_px) / open_entry_px) * open_dir
                    results.append(dict(entry_i=open_i, exit_i=i, pnl_pct=pnl_pct, dir=open_dir,
                                         reason="EXIT-STOCH", hold_bars=i - open_fill_i))
                posDir = 0
                open_fill_i = None

    return results


def run():
    df, point = load_btc_m15()
    n = len(df)
    print(f"\n{'#'*100}\nBTCUSD M15 - classic Stochastic(21,5,5) Low/High+SMA, cross-in-zone entry, "
          f"SAME 21,5,5 opposite-cross exit, {SWING_BARS}-bar swing stop (exits ignored unless taken), "
          f"1:{RR:.0f} R:R target as reference only\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point)
    report(f"BTCUSD M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point)
    report(f"BTCUSD M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point)
    report(f"BTCUSD M15 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run()
    print(f"\n\n  Honest K: 1 (user's own stated 21,5,5 entry+exit construction, not swept,")
    print(f"  prompted by a single day's signals eyeballed on the live chart).")
