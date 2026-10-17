"""
Per direct request: replaces EA_Stochastic.mq5's broken entry logic
(confirmed catastrophic - %PF 0.586 Gold / 0.173 Silver, essentially
no real filtering, fires on ~580-640 bars/month) with the single
Stochastic(21,5,5) %K/%D cross-in-zone entry already tested tonight
(single_stoch_21_5_5_test.py: Close/Close price field, Smoothed/SMMA
method - NOT the uploaded EA's own Low/High+SMA convention). Keeps
everything else about the EA-replication file unchanged: the
ATR-scaled SL/TP/trailing stop (same 1:3 R:R, trailing ratios as the
EA's own stated defaults), no 200-EMA filter (the original EA had
none, and this is a straight entry swap, not adding a new filter on
top).

Tested Gold + Silver M15, full rigor. Honest K: 1 per symbol (this
exact swap, not tuned).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import (
    stoch_close_smoothed, load_m15, report, OVERSOLD, OVERBOUGHT, TIME_CAP_BARS
)
from vwap_open_scenarios_test import wilder_atr
from ea_stochastic_uploaded_test import SL_ATR, TP_ATR, TRAIL_ATR, TRAIL_STEP_ATR, random_timing_null


def build_trades(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    atr = wilder_atr(high, low, close, 14)
    k, d = stoch_close_smoothed(close, 21, 5, 5)

    results = []
    i = 210
    while i < n - 1:
        if np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(k[i - 1]) or np.isnan(d[i - 1]) or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        cross_up = k[i - 1] <= d[i - 1] and k[i] > d[i]
        cross_down = k[i - 1] >= d[i - 1] and k[i] < d[i]
        in_oversold = k[i] <= OVERSOLD or d[i] <= OVERSOLD
        in_overbought = k[i] >= OVERBOUGHT or d[i] >= OVERBOUGHT

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

        a = atr[i]
        stop_px = entry_px - direction * SL_ATR * a
        target_px = entry_px + direction * TP_ATR * a
        trail_dist = TRAIL_ATR * a
        trail_step = TRAIL_STEP_ATR * a

        exit_i, exit_px, reason = None, None, None
        best = entry_px
        cur_stop = stop_px
        for j in range(fill_i + 1, hard_limit + 1):
            px = close[j]
            if direction > 0:
                if px > best:
                    best = px
                    if best - entry_px > trail_dist + trail_step:
                        new_stop = best - trail_dist
                        if new_stop > cur_stop:
                            cur_stop = new_stop
                stop_hit = low[j] <= cur_stop
                target_hit = high[j] >= target_px
            else:
                if px < best:
                    best = px
                    if entry_px - best > trail_dist + trail_step:
                        new_stop = best + trail_dist
                        if new_stop < cur_stop:
                            cur_stop = new_stop
                stop_hit = high[j] >= cur_stop
                target_hit = low[j] <= target_px
            if stop_hit:
                exit_i, exit_px, reason = j, cur_stop, "STOP"
                break
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
    print(f"\n{'#'*100}\n{symbol} M15 - single-stoch(21,5,5) cross entry, EA_Stochastic's own ATR-scaled stop/target/trail\n{'#'*100}")
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

    if len(full_res) >= 10:
        real_net, null_dist, p = random_timing_null(df, point, full_res)
        print(f"\n  Random-timing null (full history, n=500 draws): real net%={100*real_net:.2f}  "
              f"null mean%={100*null_dist.mean():.2f}  null std%={100*null_dist.std():.2f}  p-value={p:.4f}")
    return full_res


if __name__ == "__main__":
    run_symbol("GOLD")
    run_symbol("SILVER")
    print(f"\n\n  Honest K: 1 per symbol (single-stoch-21-5-5 cross entry, EA's own ATR-scaled stop/target ratios).")
