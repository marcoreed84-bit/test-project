"""
Combines both ideas tested tonight, per direct request, applied back
to the ORIGINAL dual-stochastic construction (slow line %K(21,5,5) vs
fast line %K(14,3,3) crossing each other - not the single-stoch %K/%D
version): keeps the actual CROSS as the trigger (dropping it entirely
made single_stoch_zone_exit_test.py worse, not better - a raw
zone-exit with no cross requirement at all let chop near the 20/80
boundary re-arm and fire repeatedly), but ALSO requires the setup to
have been genuinely ARMED by a real prior dip into the zone, and both
lines to have fully cleared the zone (both >20 / both <80) at the
exact cross bar - not just one line ticking past the other mid-zone.

Entry:
  1. ARM: either line reaches <=20 (oversold) or >=80 (overbought) at
     some point - this is the "a real move into the extreme happened"
     gate.
  2. TRIGGER: on a later bar, the fast line (14,3,3) crosses the slow
     line (21,5,5), AND at that exact bar BOTH lines are already clear
     of the zone (both >20 for a buy, both <80 for a sell) - i.e. the
     cross confirms the move out, rather than being the move itself.
  3. 200-EMA direction filter, same as every construction tonight.
Stop/target: unchanged MA/VWAP stop (fixed fallback) + 1.0xATR target.

M15 only, per tonight's focus. Honest K for this file: 1 (new entry
rule - combines without sweeping any new threshold). This is a new
entry-logic variant on the dual-stoch indicator, its own research
line separate from the original dual-stoch-in-zone K=10 line (that
line's raw-cross entry is being replaced here, not added to).
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


def build_trades_cross_zone_exit(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    vwap = session_vwap(df)
    atr = wilder_atr(high, low, close, 14)
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)   # slow
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)   # fast

    results = []
    armed_os = False
    armed_ob = False
    i = 210
    while i < n - 1:
        if (np.isnan(kA[i]) or np.isnan(kB[i]) or np.isnan(kA[i - 1]) or np.isnan(kB[i - 1])
                or np.isnan(m200[i]) or np.isnan(m50[i]) or np.isnan(m21[i]) or np.isnan(vwap[i])
                or np.isnan(atr[i]) or atr[i] <= 0):
            i += 1
            continue

        if kA[i] <= OVERSOLD or kB[i] <= OVERSOLD:
            armed_os = True
        if kA[i] >= OVERBOUGHT or kB[i] >= OVERBOUGHT:
            armed_ob = True

        cross_up = kB[i - 1] <= kA[i - 1] and kB[i] > kA[i]
        cross_down = kB[i - 1] >= kA[i - 1] and kB[i] < kA[i]
        both_clear_os = kA[i] > OVERSOLD and kB[i] > OVERSOLD
        both_clear_ob = kA[i] < OVERBOUGHT and kB[i] < OVERBOUGHT

        direction = 0
        if armed_os and cross_up and both_clear_os and close[i] > m200[i]:
            direction = 1
            armed_os = False
        elif armed_ob and cross_down and both_clear_ob and close[i] < m200[i]:
            direction = -1
            armed_ob = False
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
    print(f"\n{'#'*100}\nGOLD M15 - dual-stoch (21,5,5 vs 14,3,3) cross AFTER zone-exit confirmation + 200EMA, MA/VWAP stop, 1.0xATR target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_cross_zone_exit(df_is, point)
    report("GOLD M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades_cross_zone_exit(df_oos, point)
    report("GOLD M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades_cross_zone_exit(df, point)
    report("GOLD M15 - FULL HISTORY", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K for 'dual-stoch-cross-zone-exit' research line: 1 (new entry rule, M15 only).")
