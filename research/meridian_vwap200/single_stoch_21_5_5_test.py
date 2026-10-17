"""
Simpler construction per direct request: drop the dual-stochastic
(two different parameter sets crossing each other, which may itself
be a source of noisy/questionable crosses) in favor of a single,
standard Stochastic(21,5,5) - Price field Close/Close, MA method
Smoothed, same as every other stochastic test tonight - using its own
MAIN line (%K) crossing its own SIGNAL line (%D), the textbook
construction. M15 only, per direct request.

Entry: %K crosses UP through %D while either is <=20 (oversold) AND
price above 200-EMA -> BUY. Mirror for SELL (cross down through %D
while either >=80, price below 200-EMA).
Stop: nearest of EMA21/50/200/VWAP on the protective side + 0.25xATR -
same construction as dual_stoch_ma_stop_test.py, but with the
fallback bug just found FIXED here: if no reference line sits on the
correct side of price (only possible without a trend filter forcing
one to be there - not expected to trigger with the 200EMA filter kept
on below, but fixed defensively so it can never silently produce a
backwards stop again), falls back to a flat 1.5xATR stop instead of
picking a line that might be on the wrong side.
Target: 1.0xATR (the one validated target from tonight's research).

Honest K for this file: 1 (one fixed construction, M15 only, not
swept). This is a NEW research line (single-stoch, not dual-stoch),
so it starts its own K count rather than inheriting the dual-stoch
line's K=10.
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

STOP_ATR_BUFFER = 0.25
STOP_FALLBACK_ATR = 1.5   # used only if no reference line is on the protective side
TARGET_ATR = 1.0


def nearest_protective_stop(mas, price, direction, atr, buffer=STOP_ATR_BUFFER, fallback_atr=STOP_FALLBACK_ATR):
    if direction > 0:
        below = [m for m in mas if m < price]
        if below:
            return max(below) - buffer * atr
        return price - fallback_atr * atr   # fixed: never pick a line on the wrong side
    else:
        above = [m for m in mas if m > price]
        if above:
            return min(above) + buffer * atr
        return price + fallback_atr * atr


def build_trades_single_stoch(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    vwap = session_vwap(df)
    atr = wilder_atr(high, low, close, 14)
    k, d = stoch_close_smoothed(close, 21, 5, 5)   # single stoch - %K (main) and %D (signal)

    results = []
    i = 210
    while i < n - 1:
        if (np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(k[i - 1]) or np.isnan(d[i - 1])
                or np.isnan(m200[i]) or np.isnan(m50[i]) or np.isnan(m21[i]) or np.isnan(vwap[i])
                or np.isnan(atr[i]) or atr[i] <= 0):
            i += 1
            continue
        cross_up = k[i - 1] <= d[i - 1] and k[i] > d[i]
        cross_down = k[i - 1] >= d[i - 1] and k[i] < d[i]
        in_oversold = k[i] <= OVERSOLD or d[i] <= OVERSOLD
        in_overbought = k[i] >= OVERBOUGHT or d[i] >= OVERBOUGHT

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
    print(f"\n{'#'*100}\nGOLD M15 - single Stochastic(21,5,5) %K/%D cross-in-zone + 200EMA, MA/VWAP stop, 1.0xATR target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_single_stoch(df_is, point)
    report("GOLD M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades_single_stoch(df_oos, point)
    report("GOLD M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades_single_stoch(df, point)
    report("GOLD M15 - FULL HISTORY", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K for 'single-stoch-21-5-5' research line: 1 (new line, M15 only, one fixed construction).")
