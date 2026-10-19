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

CORRECTED 2026-10-19: build_trades() had two real bugs, found while
investigating why a downstream filter test's numbers looked far worse
than anything else tested in this project.
  1. It computed a swing stop and 1:2 R:R target on every entry but
     NEVER checked subsequent bars' highs/lows against them - trades
     only ever exited on the opposite stochastic cross, with ZERO
     stop-loss protection the whole time this file existed.
  2. Its main loop only incremented `i` inside the NaN-skip branch -
     every other path (a live cross, an open position) left `i`
     unchanged, which is a literal infinite loop; the file could not
     finish running as originally written (confirmed by a run attempt
     timing out with no output).
Rewritten using the same stop/target-enforced, scored-flip-closes
pattern already validated in classic_stoch_21_5_5_btc_h1_stop_trail_
test.py. The corrected full-history %PF now comes out to 0.201, which
exactly matches this project's own previously-cited number for this
exact construction (classic_stoch_21_5_5_btc_h1_test.py's own
docstring: "full-history %PF 0.201->0.388 just from moving off M15") -
confirming the fix is right, not a new/different number.
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
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    # entry and exit use the SAME Stochastic(21,5,5) per the request

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
        hard_limit = min(fill_i + time_cap_bars, n - 1)

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


def run():
    df, point = load_btc_m15()
    n = len(df)
    print(f"\n{'#'*100}\nBTCUSD M15 - classic Stochastic(21,5,5) Low/High+SMA, cross-in-zone entry, "
          f"SAME 21,5,5 opposite-cross exit, {SWING_BARS}-bar swing stop (enforced), "
          f"1:{RR:.0f} R:R target (enforced)\n{'#'*100}")
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
