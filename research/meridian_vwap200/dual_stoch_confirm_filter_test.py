"""
Noise filter per direct chart example: a shallow fakeout cross near
80 (fast line barely dips below the slow line, then snaps straight
back up within a bar or two - visually a minor pullback/correction,
not a real reversal) still satisfied the plain cross-in-zone condition
and fired a signal. This adds a CONFIRMATION requirement: after the
raw cross at bar i, the fast line must stay on the signal side of the
slow line for CONFIRM_BARS consecutive bars (i+1 .. i+CONFIRM_BARS)
before the signal is accepted - if it crosses back before that, the
candidate is thrown out as noise. This delays entry (trades off some
timing for fewer false starts), same principle as requiring a breakout
to hold before acting on it elsewhere in this project.

Still causal/no lookahead - confirmation only ever waits and watches
already-closed bars, it never uses information from beyond the fill.

Built on top of the best-performing stack so far tonight (entry +
MA/VWAP stop + 1.0xATR target, dual_stoch_atr_target_test.py) so the
confirmation filter's effect is isolated from everything else already
tested, not conflated with a simultaneous exit change.

Honest K for this addition: 1 (CONFIRM_BARS=2, one fixed choice - not
swept across several values and the best one kept).
Cumulative honest K for 'dual-stoch-in-zone' line: 9.
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
CONFIRM_BARS = 2


def build_trades_confirmed(df, point, confirm_bars=CONFIRM_BARS, use_ema_filter=True, time_cap_bars=TIME_CAP_BARS):
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
    while i < n - 1 - confirm_bars:
        if (np.isnan(kA[i]) or np.isnan(kB[i]) or np.isnan(kA[i - 1]) or np.isnan(kB[i - 1])
                or np.isnan(m200[i]) or np.isnan(m50[i]) or np.isnan(m21[i]) or np.isnan(vwap[i])
                or np.isnan(atr[i]) or atr[i] <= 0):
            i += 1
            continue
        cross_up = kB[i - 1] <= kA[i - 1] and kB[i] > kA[i]
        cross_down = kB[i - 1] >= kA[i - 1] and kB[i] < kA[i]
        in_oversold = kA[i] <= OVERSOLD or kB[i] <= OVERSOLD
        in_overbought = kA[i] >= OVERBOUGHT or kB[i] >= OVERBOUGHT

        ema_ok_long = (close[i] > m200[i]) if use_ema_filter else True
        ema_ok_short = (close[i] < m200[i]) if use_ema_filter else True
        direction = 0
        if cross_up and in_oversold and ema_ok_long:
            direction = 1
        elif cross_down and in_overbought and ema_ok_short:
            direction = -1
        if direction == 0:
            i += 1
            continue

        # confirmation: the fast line must stay on the signal side for
        # confirm_bars consecutive closed bars after the raw cross, or
        # the candidate is thrown out as a fakeout/noise cross.
        confirmed = True
        for k in range(1, confirm_bars + 1):
            j = i + k
            if j >= n or np.isnan(kA[j]) or np.isnan(kB[j]):
                confirmed = False
                break
            if direction > 0 and kB[j] <= kA[j]:
                confirmed = False
                break
            if direction < 0 and kB[j] >= kA[j]:
                confirmed = False
                break
        if not confirmed:
            i += 1
            continue

        sig_i = i + confirm_bars
        fill_i = sig_i + 1
        if fill_i >= n or np.isnan(atr[sig_i]):
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)
        hard_limit = min(fill_i + time_cap_bars, n - 1)

        mas = [m21[sig_i], m50[sig_i], m200[sig_i], vwap[sig_i]]
        if direction > 0:
            below = [m for m in mas if m < close[sig_i]]
            ref_ma = max(below) if below else min(mas)
            stop_px = ref_ma - STOP_ATR_BUFFER * atr[sig_i]
        else:
            above = [m for m in mas if m > close[sig_i]]
            ref_ma = min(above) if above else max(mas)
            stop_px = ref_ma + STOP_ATR_BUFFER * atr[sig_i]
        target_px = entry_px + (TARGET_ATR * atr[sig_i] if direction > 0 else -TARGET_ATR * atr[sig_i])

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
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    for use_filter, flabel in ((True,  f"WITH 200EMA filter + {CONFIRM_BARS}-bar confirmation"),
                               (False, f"NO 200EMA filter (direction-agnostic) + {CONFIRM_BARS}-bar confirmation")):
        print(f"\n{'#'*100}\n{symbol} {tf_label} - {flabel}, MA/VWAP stop, 1.0xATR target\n{'#'*100}")
        print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
        is_res = build_trades_confirmed(df_is, point, use_ema_filter=use_filter)
        report(f"{symbol} {tf_label} - IN-SAMPLE", is_res, is_days, split_dir=True)
        oos_res = build_trades_confirmed(df_oos, point, use_ema_filter=use_filter)
        report(f"{symbol} {tf_label} - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
        full_res = build_trades_confirmed(df, point, use_ema_filter=use_filter)
        report(f"{symbol} {tf_label} - FULL HISTORY", full_res, full_days, split_dir=True)


if __name__ == "__main__":
    run_tf("GOLD", "M15", load_m15)
    run_tf("GOLD", "M5", load_m5)
    print(f"\n\n  Cumulative honest K for 'dual-stoch-in-zone' research line: 10")
    print(f"  (plain, +200EMA, +BB-touch-entry, +reverse-cross-exit, +BB-target-exit, +MA-stop,")
    print(f"  +MA-stop-with-VWAP, +1.0xATR-target, +2-bar-confirmation, +confirmation-no-EMA-filter).")
