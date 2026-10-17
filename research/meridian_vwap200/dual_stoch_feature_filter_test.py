"""
Builds and OOS-tests the filter suggested by the feature-correlation
exploration (dual_stoch_feature_exploration.py, IS-only): the two
features with the cleanest (if still weak, r~0.05-0.06) monotonic
relationship to outcome were dip_depth (how far past 20/80 the
deeper line reached before the cross) and gap_later (line separation
2 bars after the cross vs at the cross itself - is momentum still
building or did it stall).

Filter, both conditions required on top of the unchanged base
(cross-in-zone + 200EMA + MA/VWAP stop + 1.0xATR target):
  1. dip_depth > 7.0 points past the 20/80 line - roughly the IS
     data's own top-40%-by-depth cutoff (7.443 exactly; rounded to a
     plain number rather than hand-fit to that exact boundary).
  2. gap_later > gap_now - the fast/slow separation must still be
     GROWING 2 bars after the cross, not stalling or narrowing. A
     binary "still growing" condition, not a magnitude threshold -
     more robust to the exact IS distribution than matching a
     percentile cutoff on gap_later itself.

Condition 2 means the entry can't be confirmed until 2 bars after the
raw cross (it has to wait and see whether the gap kept growing) -
still fully causal, just a delayed fill: fill is bar i+3 instead of
i+1 (cross bar i, confirmation check at i+2, fill the bar after that).

TESTED OUT-OF-SAMPLE as the real test (the features were only ever
correlated on IS data) - IS and full-history numbers are reported
too, but OOS is what actually answers the question. Honest K: 1 (one
fixed filter built from the IS correlation findings, not swept/tuned
against OOS).
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

DIP_DEPTH_MIN = 7.0


def build_trades_feature_filtered(df, point, time_cap_bars=TIME_CAP_BARS):
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
    while i < n - 3:
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

        dip_depth = (OVERSOLD - min(kA[i], kB[i])) if direction > 0 else (max(kA[i], kB[i]) - OVERBOUGHT)
        if dip_depth < DIP_DEPTH_MIN:
            i += 1
            continue

        j2 = i + 2
        if j2 >= n or np.isnan(kA[j2]) or np.isnan(kB[j2]):
            i += 1
            continue
        gap_now = (kB[i] - kA[i]) * direction
        gap_later = (kB[j2] - kA[j2]) * direction
        if not (gap_later > gap_now):
            i += 1
            continue

        fill_i = j2 + 1
        if fill_i >= n or np.isnan(atr[i]):
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
    print(f"\n{'#'*100}\nGOLD M15 - dual-stoch cross-in-zone + dip_depth>{DIP_DEPTH_MIN} + growing-gap filter, MA/VWAP stop, 1.0xATR target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_feature_filtered(df_is, point)
    report("GOLD M15 - IN-SAMPLE (same data the filter was built from - expect it to look good here)", is_res, is_days, split_dir=True)
    oos_res = build_trades_feature_filtered(df_oos, point)
    report("GOLD M15 - OUT-OF-SAMPLE (the real test)", oos_res, oos_days, split_dir=True)
    full_res = build_trades_feature_filtered(df, point)
    report("GOLD M15 - FULL HISTORY", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K for 'dual-stoch-feature-filter' research line: 1 (filter built from IS")
    print(f"  correlation, tested OOS - not swept/tuned against OOS data).")
