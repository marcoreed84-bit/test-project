"""
Adds a real stop loss to the BB-target-exit construction, per direct
instruction with a chart example: at entry, find whichever MA (21, 50,
or 200 EMA) price is closest to on the trade's protective side - for a
long, the nearest EMA BELOW price (the one price looks like it just
"rejected" off); for a short, the nearest EMA above - and place the
stop just beyond it (a small ATR buffer past the MA, not exactly at it,
so normal noise/spread doesn't stop it out instantly). This is a real
answer to the single biggest flaw already found tonight: the BB-target
construction has NO protective exit at all, which is exactly why one
crash trade cost -$218 against ~$3 average wins.

Entry: unchanged from dual_stoch_bb_target_exit_test.py (dual-stoch
cross-in-zone + 200EMA direction filter).
Exit: whichever comes first - BB-band target (unchanged), the new MA
stop, or the time cap.

Honest K for this addition: 1 (one stop rule, fixed 0.25*ATR buffer,
not swept/tuned against this data).
Cumulative honest K for 'dual-stoch-in-zone' line: 6.
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
from vwap_open_scenarios_test import wilder_atr
from dual_stoch_bb_filter_test import bollinger

STOP_ATR_BUFFER = 0.25


def build_trades_ma_stop(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    atr = wilder_atr(high, low, close, 14)
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)
    bb_upper, bb_mid, bb_lower = bollinger(close, 20, 2.0)

    results = []
    i = 210
    while i < n - 1:
        if (np.isnan(kA[i]) or np.isnan(kB[i]) or np.isnan(kA[i - 1]) or np.isnan(kB[i - 1])
                or np.isnan(m200[i]) or np.isnan(m50[i]) or np.isnan(m21[i])
                or np.isnan(bb_upper[i]) or np.isnan(bb_lower[i]) or np.isnan(atr[i]) or atr[i] <= 0):
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

        # nearest MA on the protective side, at the ENTRY bar (i, the
        # signal bar - causal, known before the fill).
        mas = [m21[i], m50[i], m200[i]]
        if direction > 0:
            below = [m for m in mas if m < close[i]]
            ref_ma = max(below) if below else min(mas)   # closest below; degrade gracefully if none
            stop_px = ref_ma - STOP_ATR_BUFFER * atr[i]
        else:
            above = [m for m in mas if m > close[i]]
            ref_ma = min(above) if above else max(mas)
            stop_px = ref_ma + STOP_ATR_BUFFER * atr[i]

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            if np.isnan(bb_upper[j]) or np.isnan(bb_lower[j]):
                continue
            # stop checked first - protective exits take priority over the target
            stop_hit = (low[j] <= stop_px) if direction > 0 else (high[j] >= stop_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            target_hit = (high[j] >= bb_upper[j]) if direction > 0 else (low[j] <= bb_lower[j])
            if target_hit:
                exit_i = j
                exit_px = bb_upper[j] if direction > 0 else bb_lower[j]
                reason = "BB_TARGET"
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
    print(f"\n{'#'*100}\n{symbol} {tf_label} - dual-stoch cross-in-zone + 200EMA filter, BB target, MA-based stop\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_ma_stop(df_is, point)
    report(f"{symbol} {tf_label} - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades_ma_stop(df_oos, point)
    report(f"{symbol} {tf_label} - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades_ma_stop(df, point)
    report(f"{symbol} {tf_label} - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run_tf("GOLD", "M15", load_m15)
    run_tf("GOLD", "M5", load_m5)
    print(f"\n\n  Cumulative honest K for 'dual-stoch-in-zone' research line: 6")
    print(f"  (plain, +200EMA, +BB-touch-entry, +reverse-cross-exit, +BB-target-exit, +MA-stop).")
