"""
New construction per uploaded PDF (Paik, Choi & Ureta Vaquero 2024,
"Algorithm-Based Low-Frequency Trading Using a Stochastic Oscillator,
Williams%R, and Trading Volume"): combines the stochastic oscillator
with Williams %R as a double-confirmation filter - a genuinely
different indicator (Williams %R has not been used anywhere else
tonight), not just another stochastic-only variant.

Original paper's rule (on SPY weekly, 2010-2023): BUY when
stochastic<30 AND Williams%R<-75; SELL when stochastic>80 AND
Williams%R>-20; otherwise stay in cash. That's a regime/state system
on weekly bars - adapted here to M15 as an ENTRY trigger (fires once,
on the bar where both conditions first become simultaneously true,
rather than holding a position for as long as the regime persists),
since this project's framework is trade-by-trade with a stop/target,
not a persistent regime-switching position. This is a real adaptation
choice, documented because it changes what's being tested: this
checks "does the combined signal predict a short-term move", not the
original paper's own buy-and-hold-until-opposite-regime approach.

Single Stochastic(21,5,5), Close/Close+Smoothed (this project's
convention). Williams %R(21) - same period as the stochastic for a
fair, non-cherry-picked comparison, using the paper's own stated
levels (-75/-20, not the standard -80/-20). Stop/target: unchanged
MA/VWAP stop + 1.0xATR target.

Tested Gold + Silver M15, full rigor. Honest K: 1 per symbol (paper's
own stated levels, not re-tuned).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import stoch_close_smoothed, load_m15, ema, report, TIME_CAP_BARS
from vwap_open_scenarios_test import wilder_atr, session_vwap
from single_stoch_21_5_5_test import nearest_protective_stop, TARGET_ATR

WR_PERIOD = 21
WR_OVERSOLD = -75.0
WR_OVERBOUGHT = -20.0
STOCH_OVERSOLD = 30.0
STOCH_OVERBOUGHT = 80.0


def williams_r(high, low, close, period):
    highest = pd.Series(high).rolling(period, min_periods=period).max().values
    lowest = pd.Series(low).rolling(period, min_periods=period).min().values
    rng = highest - close
    full_range = highest - lowest
    out = np.full(len(close), np.nan)
    valid = full_range > 0
    out[valid] = (rng[valid] / full_range[valid]) * -100.0
    return out


def build_trades(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    vwap = session_vwap(df)
    atr = wilder_atr(high, low, close, 14)
    k, _ = stoch_close_smoothed(close, 21, 5, 5)
    wr = williams_r(high, low, close, WR_PERIOD)

    results = []
    was_armed_long = False   # tracks whether the combined condition was NOT true last bar
    was_armed_short = False
    i = 210
    while i < n - 1:
        if (np.isnan(k[i]) or np.isnan(wr[i]) or np.isnan(m200[i]) or np.isnan(m50[i])
                or np.isnan(m21[i]) or np.isnan(vwap[i]) or np.isnan(atr[i]) or atr[i] <= 0):
            i += 1
            continue

        long_cond = k[i] < STOCH_OVERSOLD and wr[i] < WR_OVERSOLD
        short_cond = k[i] > STOCH_OVERBOUGHT and wr[i] > WR_OVERBOUGHT

        direction = 0
        # fire only on the TRANSITION into the combined condition (both
        # just became true), not on every bar the condition stays true
        if long_cond and not was_armed_long:
            direction = 1
        elif short_cond and not was_armed_short:
            direction = -1
        was_armed_long = long_cond
        was_armed_short = short_cond
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
                exit_i, exit_px, reason = j, target_px, "TARGET"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run_symbol(symbol):
    df, point = load_m15(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} M15 - Stochastic(21,5,5) + Williams%R(21) double-confirmation, MA/VWAP stop, 1.0xATR target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point)
    report(f"{symbol} M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point)
    report(f"{symbol} M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point)
    report(f"{symbol} M15 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run_symbol("GOLD")
    run_symbol("SILVER")
    print(f"\n\n  Honest K: 1 per symbol (paper's own Stoch<30/WR<-75 levels, not re-tuned).")
