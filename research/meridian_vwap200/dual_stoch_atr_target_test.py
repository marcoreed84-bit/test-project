"""
Direct response to a real, data-confirmed finding: the BB-band TARGET
used in every prior exit variant tonight sits 3.33 ATR away from entry
on average, while even the trades that got stopped out only managed
0.82 ATR of favorable movement before reversing (checked directly
against 1,201 real stop-exit trades - 68.1% of them moved >=0.5 ATR
favorably first, confirming the entry DIRECTION is usually right; the
exit TARGET was just set too far away to realistically reach).

This keeps the already-tested entry (dual-stoch cross-in-zone +
200EMA filter) and the already-tested MA/VWAP stop UNCHANGED, and
replaces ONLY the take-profit: instead of the distant BB band, the
target is now a fixed 1.0x ATR from entry - close to the median
favorable excursion actually observed, not an arbitrary guess.

Honest K for this addition: 1 (one fixed ATR target, not swept/tuned -
1.0x was chosen from the MFE data above, not by trying several
multiples and picking the best on this dataset).
Cumulative honest K for 'dual-stoch-in-zone' line: 8.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import (
    stoch_close_smoothed, load_m15, load_m5, pct_pf, report, ema,
    OVERSOLD, OVERBOUGHT, TIME_CAP_BARS
)
from vwap_open_scenarios_test import wilder_atr, session_vwap

STOP_ATR_BUFFER = 0.25
TARGET_ATR = 1.0


def build_trades_atr_target(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    vwap = session_vwap(df)
    atr = wilder_atr(high, low, close, 14)
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)

    results = []
    i = 210
    while i < n - 1:
        if (np.isnan(kA[i]) or np.isnan(kB[i]) or np.isnan(kA[i - 1]) or np.isnan(kB[i - 1])
                or np.isnan(m200[i]) or np.isnan(m50[i]) or np.isnan(m21[i]) or np.isnan(vwap[i])
                or np.isnan(atr[i]) or atr[i] <= 0):
            i += 1
            continue
        cross_up = kB[i - 1] <= kA[i - 1] and kB[i] > kA[i]
        cross_down = kB[i - 1] >= kA[i - 1] and kB[i] < kA[i]
        in_oversold = kA[i] <= OVERSOLD or kB[i] <= OVERSOLD
        in_overbought = kA[i] >= OVERBOUGHT or kB[i] >= OVERBOUGHT

        direction = 0
        if cross_up and in_oversold and close[i] > m200[i]:
            direction = 1
        elif cross_down and in_overbought and close[i] < m200[i]:
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

        # stop: nearest EMA/VWAP reference line on the protective side,
        # at the signal bar - same construction as dual_stoch_ma_stop_test.py
        mas = [m21[i], m50[i], m200[i], vwap[i]]
        if direction > 0:
            below = [m for m in mas if m < close[i]]
            ref_ma = max(below) if below else min(mas)
            stop_px = ref_ma - STOP_ATR_BUFFER * atr[i]
        else:
            above = [m for m in mas if m > close[i]]
            ref_ma = min(above) if above else max(mas)
            stop_px = ref_ma + STOP_ATR_BUFFER * atr[i]

        # target: fixed 1.0x ATR (at entry) instead of the far-away BB band
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


def run_tf(symbol, tf_label, loader):
    df, point = loader(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} {tf_label} - dual-stoch cross-in-zone + 200EMA filter, MA/VWAP stop, 1.0xATR target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_atr_target(df_is, point)
    report(f"{symbol} {tf_label} - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades_atr_target(df_oos, point)
    report(f"{symbol} {tf_label} - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades_atr_target(df, point)
    report(f"{symbol} {tf_label} - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run_tf("GOLD", "M15", load_m15)
    run_tf("GOLD", "M5", load_m5)
    print(f"\n\n  Cumulative honest K for 'dual-stoch-in-zone' research line: 8")
    print(f"  (plain, +200EMA, +BB-touch-entry, +reverse-cross-exit, +BB-target-exit, +MA-stop,")
    print(f"  +MA-stop-with-VWAP, +1.0xATR-target).")
