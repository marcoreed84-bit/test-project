"""
One bounded follow-up to dual_stoch_cross_200ema_test.py (which came
back a clean net loser, Opus-audited, no bugs) - per direct request to
test Bollinger Bands as a possible missing confirmation. Adds a BB(20,2)
touch requirement on top of the EXACT SAME entry/exit already tested:
a BUY additionally requires the bar's LOW touched or pierced the lower
band (price itself, not just the oscillator, reached an extreme);  a
SELL requires the HIGH touched/pierced the upper band. Everything else
(cross detection, zone check, fill timing, opposite-zone exit, time cap)
is unchanged and imported directly from the already-audited file, not
reimplemented, so this can't accidentally diverge from what was tested.

Honest K for this specific addition: 1 (one filter, fixed standard
Bollinger settings, not swept/tuned against this data).
Cumulative honest K for the "dual-stoch-in-zone" research line started
2026-10-17: 3 (plain, +200EMA, +BB - all three reported here or in the
prior file, none chosen by picking whichever looked best on this data).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from dual_stoch_cross_200ema_test import (
    stoch_close_smoothed, load_m15, load_m5, pct_pf, report, OVERSOLD, OVERBOUGHT, TIME_CAP_BARS
)


def bollinger(close, period=20, mult=2.0):
    s = pd.Series(close)
    mid = s.rolling(period, min_periods=period).mean().values
    std = s.rolling(period, min_periods=period).std(ddof=0).values
    upper = mid + mult * std
    lower = mid - mult * std
    return upper, mid, lower


def build_trades_bb(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)
    bb_upper, bb_mid, bb_lower = bollinger(close, 20, 2.0)

    results = []
    i = 210
    while i < n - 1:
        if (np.isnan(kA[i]) or np.isnan(kB[i]) or np.isnan(kA[i - 1]) or np.isnan(kB[i - 1])
                or np.isnan(bb_lower[i]) or np.isnan(bb_upper[i])):
            i += 1
            continue
        cross_up = kB[i - 1] <= kA[i - 1] and kB[i] > kA[i]
        cross_down = kB[i - 1] >= kA[i - 1] and kB[i] < kA[i]
        in_oversold = kA[i] <= OVERSOLD or kB[i] <= OVERSOLD
        in_overbought = kA[i] >= OVERBOUGHT or kB[i] >= OVERBOUGHT
        bb_touch_low = low[i] <= bb_lower[i]
        bb_touch_high = high[i] >= bb_upper[i]

        direction = 0
        if cross_up and in_oversold and bb_touch_low:
            direction = 1
        elif cross_down and in_overbought and bb_touch_high:
            direction = -1
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

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            if np.isnan(kA[j]) or np.isnan(kB[j]):
                continue
            hit = (kA[j] >= OVERBOUGHT or kB[j] >= OVERBOUGHT) if direction > 0 else \
                  (kA[j] <= OVERSOLD or kB[j] <= OVERSOLD)
            if hit:
                exit_i, exit_px, reason = j, close[j], "ZONE"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run_tf(symbol, tf_label, loader):
    df, point = loader(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} {tf_label} - dual-stoch cross-in-zone + Bollinger(20,2) touch confirmation\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_bb(df_is, point)
    report(f"{symbol} {tf_label} - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades_bb(df_oos, point)
    report(f"{symbol} {tf_label} - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades_bb(df, point)
    report(f"{symbol} {tf_label} - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run_tf("GOLD", "M15", load_m15)
    run_tf("GOLD", "M5", load_m5)
    print(f"\n\n  Cumulative honest K for 'dual-stoch-in-zone' research line: 3")
    print(f"  (plain, +200EMA, +BB-touch - all reported, none selected after the fact).")
