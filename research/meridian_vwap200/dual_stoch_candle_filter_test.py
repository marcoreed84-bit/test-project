"""
Builds and OOS-tests the filter suggested by the candle-pattern
feature exploration (dual_stoch_candle_feature_exploration.py,
IS-only). The two features with a real, if still weak, monotonic
relationship to outcome were candle_range_atr (corr +0.086, the
strongest found across both feature-exploration passes tonight) and
rejection_wick (corr +0.052). body_ratio, opposite_wick, and whether
the signal candle itself closed in the trade's direction showed no
usable signal and are not used here.

Filter, both conditions required on top of the unchanged base
(cross-in-zone + 200EMA + MA/VWAP stop + 1.0xATR target):
  1. candle_range_atr > 1.0 - the signal candle's own high-low range
     must exceed its own ATR(14) (roughly the IS data's top-40% cutoff
     of 0.975, rounded to a plain number rather than hand-fit).
  2. rejection_wick > 0.2 - the wick on the trade's side (lower wick
     for a buy, upper for a sell) must be at least 20% of the
     candle's full range (roughly the IS top-40% cutoff of 0.229,
     again rounded rather than hand-fit).

No delayed confirmation needed here (unlike the dip_depth/gap_later
filter) - both features are known immediately at the signal bar
itself, so entry timing is unchanged from the base construction.

TESTED OUT-OF-SAMPLE as the real test. Honest K: 1 (one fixed filter
built from IS correlation, not swept against OOS).
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

RANGE_ATR_MIN = 1.0
REJECTION_WICK_MIN = 0.2


def build_trades_candle_filtered(df, point, time_cap_bars=TIME_CAP_BARS):
    open_ = df["open"].values
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

        rng = high[i] - low[i]
        if rng <= 0:
            i += 1
            continue
        candle_range_atr = rng / atr[i]
        if candle_range_atr <= RANGE_ATR_MIN:
            i += 1
            continue
        lower_wick = min(open_[i], close[i]) - low[i]
        upper_wick = high[i] - max(open_[i], close[i])
        rejection_wick = (lower_wick if direction > 0 else upper_wick) / rng
        if rejection_wick <= REJECTION_WICK_MIN:
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
    print(f"\n{'#'*100}\nGOLD M15 - dual-stoch cross-in-zone + candle_range_atr>{RANGE_ATR_MIN} + rejection_wick>{REJECTION_WICK_MIN}, MA/VWAP stop, 1.0xATR target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades_candle_filtered(df_is, point)
    report("GOLD M15 - IN-SAMPLE (same data the filter was built from)", is_res, is_days, split_dir=True)
    oos_res = build_trades_candle_filtered(df_oos, point)
    report("GOLD M15 - OUT-OF-SAMPLE (the real test)", oos_res, oos_days, split_dir=True)
    full_res = build_trades_candle_filtered(df, point)
    report("GOLD M15 - FULL HISTORY", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K for 'dual-stoch-candle-filter' research line: 1 (filter built from IS")
    print(f"  correlation, tested OOS - not swept/tuned against OOS data).")
