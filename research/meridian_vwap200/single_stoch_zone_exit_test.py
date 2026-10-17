"""
Stricter entry criterion per direct request: a raw %K/%D cross can
happen in passing even when the lines barely dip into the zone - not
a real "the move exhausted itself" signal. This instead requires:
  1. Price enters the zone (EITHER %K or %D reaches <=20 for a buy
     setup, >=80 for a sell setup) - this ARMS the setup.
  2. The entry fires on the bar where BOTH %K and %D have risen back
     above 20 together (buy) / fallen back below 80 together (sell) -
     i.e. the whole move has cleared the extreme, not just one line
     ticking across the other mid-zone.
This replaces the %K/%D CROSS condition entirely (crossing is no
longer the trigger - BOTH LINES EXITING THE ZONE TOGETHER is), still
combined with the 200-EMA direction filter, same stop/target stack as
every other construction tonight (MA/VWAP stop with the fixed
fallback, 1.0xATR target).

Single Stochastic(21,5,5), Close/Close, Smoothed - same base indicator
as single_stoch_21_5_5_test.py. M15 only, per the ongoing focus
tonight.

Honest K for this file: 1 (one fixed zone-exit rule, not swept).
This is a new entry-logic variant, not an addition to the raw %K/%D
cross tested in single_stoch_21_5_5_test.py (K=1 there), so it starts
its own K=1 rather than inheriting that count - they are mutually
exclusive entry rules on the same base indicator, not stacked.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import (
    stoch_close_smoothed, load_m15, pct_pf, report, ema,
    OVERSOLD, OVERBOUGHT, TIME_CAP_BARS
)
from vwap_open_scenarios_test import wilder_atr, session_vwap
from single_stoch_21_5_5_test import nearest_protective_stop, TARGET_ATR


def build_trades_zone_exit(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    vwap = session_vwap(df)
    atr = wilder_atr(high, low, close, 14)
    k, d = stoch_close_smoothed(close, 21, 5, 5)

    results = []
    armed_os = False   # was in the oversold zone, waiting for both lines to exit
    armed_ob = False
    i = 210
    while i < n - 1:
        if (np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(m200[i]) or np.isnan(m50[i])
                or np.isnan(m21[i]) or np.isnan(vwap[i]) or np.isnan(atr[i]) or atr[i] <= 0):
            i += 1
            continue

        if k[i] <= OVERSOLD or d[i] <= OVERSOLD:
            armed_os = True
        if k[i] >= OVERBOUGHT or d[i] >= OVERBOUGHT:
            armed_ob = True

        direction = 0
        if armed_os and k[i] > OVERSOLD and d[i] > OVERSOLD and close[i] > m200[i]:
            direction = 1
            armed_os = False
        elif armed_ob and k[i] < OVERBOUGHT and d[i] < OVERBOUGHT and close[i] < m200[i]:
            direction = -1
            armed_ob = False
        # the arm flag only clears once the direction's own filter side also
        # agreed - if the EMA filter blocked it, leave armed so a later exit
        # still has a chance to qualify, rather than silently discarding it.
        if direction == 0:
            i += 1
            continue

        fill_i = i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)
        hard_limit = min(fill_i + time_cap_bars, n - 1)

        mas = [m21[i], m50[i], m200[i], vwap[i]]
        stop_px = nearest_protective_stop(mas, close[i], direction, atr[i])
        target_px = entry_px + (TARGET_ATR * atr[i] if direction > 0 else -TARGET_ATR * atr[i])

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if direction > 0 else (high[j] >= stop_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            target_hit = (high[j] >= target_px) if direction > 0 else (low[j] <= target_px)
            if target_hit:
                exit_i, exit_px, reason = j, target_px, "ATR_TARGET"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


if __name__ == "__main__":
    df, point = load_m15("GOLD")
    n = len(df)
    print(f"\n{'#'*100}\nGOLD M15 - single Stochastic(21,5,5), BOTH lines exit zone together + 200EMA, MA/VWAP stop, 1.0xATR target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_zone_exit(df_is, point)
    report("GOLD M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades_zone_exit(df_oos, point)
    report("GOLD M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades_zone_exit(df, point)
    report("GOLD M15 - FULL HISTORY", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K for 'single-stoch-zone-exit' research line: 1 (new entry rule, M15 only).")
