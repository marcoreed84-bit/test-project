"""
Smart-exit addition per direct request: the plain dual-stoch-in-zone
construction (dual_stoch_cross_200ema_test.py, already Opus-audited,
clean net loser at %PF 0.77/0.85) only exits on reaching the OPPOSITE
zone or a time cap - nothing protects a trade if the move stalls and
reverses before ever getting there, which is exactly the "high win
rate but PF<1" failure mode Opus's audit flagged (no stop loss lets
occasional big adverse excursions outweigh the frequent small wins).

New exit added here, using the SAME mechanism that triggered entry
(no new arbitrary parameter invented): if the fast/slow lines cross
back the OTHER way - B crosses back below A for a long, or back above
A for a short - before the trade ever reached the opposite zone, that
is a real "the reversal failed" signal, and exits there instead of
waiting. Checked in the same bar-by-bar loop as the ZONE/TIME checks,
whichever of the three (ZONE, REVERSE, TIME) comes first wins.

Imports the entry logic unchanged from the already-audited file -
only the exit loop differs - so this isolates exactly one change
(the exit rule) against the already-known baseline.

Honest K for this addition: 1 (one exit rule, not swept/tuned).
Cumulative honest K for 'dual-stoch-in-zone' line: 4 (plain, +200EMA,
+BB-touch, +reverse-cross-exit).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from dual_stoch_cross_200ema_test import (
    stoch_close_smoothed, load_m15, load_m5, pct_pf, report, OVERSOLD, OVERBOUGHT, TIME_CAP_BARS
)


def build_trades_reverse_exit(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)

    results = []
    i = 210
    while i < n - 1:
        if np.isnan(kA[i]) or np.isnan(kB[i]) or np.isnan(kA[i - 1]) or np.isnan(kB[i - 1]):
            i += 1
            continue
        cross_up = kB[i - 1] <= kA[i - 1] and kB[i] > kA[i]
        cross_down = kB[i - 1] >= kA[i - 1] and kB[i] < kA[i]
        in_oversold = kA[i] <= OVERSOLD or kB[i] <= OVERSOLD
        in_overbought = kA[i] >= OVERBOUGHT or kB[i] >= OVERBOUGHT

        direction = 0
        if cross_up and in_oversold:
            direction = 1
        elif cross_down and in_overbought:
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
            if np.isnan(kA[j]) or np.isnan(kB[j]) or np.isnan(kA[j - 1]) or np.isnan(kB[j - 1]):
                continue
            hit_zone = (kA[j] >= OVERBOUGHT or kB[j] >= OVERBOUGHT) if direction > 0 else \
                       (kA[j] <= OVERSOLD or kB[j] <= OVERSOLD)
            if hit_zone:
                exit_i, exit_px, reason = j, close[j], "ZONE"
                break
            # reverse cross: the SAME crossing mechanism that triggered
            # entry, firing the other way, before the opposite zone was
            # ever reached - the "the reversal failed" protective exit.
            reverse_cross = (kB[j - 1] >= kA[j - 1] and kB[j] < kA[j]) if direction > 0 else \
                            (kB[j - 1] <= kA[j - 1] and kB[j] > kA[j])
            if reverse_cross:
                exit_i, exit_px, reason = j, close[j], "REVERSE"
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
    print(f"\n{'#'*100}\n{symbol} {tf_label} - dual-stoch cross-in-zone + reverse-cross smart exit\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_reverse_exit(df_is, point)
    report(f"{symbol} {tf_label} - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades_reverse_exit(df_oos, point)
    report(f"{symbol} {tf_label} - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades_reverse_exit(df, point)
    report(f"{symbol} {tf_label} - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run_tf("GOLD", "M15", load_m15)
    run_tf("GOLD", "M5", load_m5)
    print(f"\n\n  Cumulative honest K for 'dual-stoch-in-zone' research line: 4")
    print(f"  (plain, +200EMA, +BB-touch, +reverse-cross-exit - all reported, none")
    print(f"  selected after the fact).")
