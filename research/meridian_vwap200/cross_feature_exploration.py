"""
Exploratory feature scan, per direct request: rather than hand-specify one
more rule from one more chart screenshot (which risks cherry-picking -
every rule tested tonight has had both a supporting and a contradicting
example findable by eye), take EVERY 21/50-EMA cross in the dataset and
measure which, if any, measurable characteristics of the cross separate
the ones that run for hours from the ones that go nowhere.

Candidate features, all computed causally at/before the cross bar (no
lookahead):
  - cross_angle_atr: steepness of the 21-EMA's own slope over the 3 bars
    into the cross, in ATR units - a fast, sharp cross vs a shallow,
    grinding one.
  - gap_velocity_atr: how fast the 21/50 gap itself is widening at the
    moment of the cross (rate of separation), in ATR units.
  - dist_vwap_atr: distance from VWAP at the cross, signed by direction
    (positive = cross happening on the "overextended" side already).
  - dist_200ema_atr: distance from the 200-EMA at the cross, signed by
    direction.
  - prior_day_ret_pct: the previous full day's close-to-close return,
    signed by direction (was yesterday already moving the same way).
  - vol_ratio: tick volume at the cross bar relative to the trailing
    20-bar average (relative participation).
  - hour_of_day: local hour the cross occurred (session timing).

Forward return measured two ways: 6h (24 bars) and "rest of session"
(until the next day's first bar), both direction-adjusted (positive means
the cross's direction was right).

IS/OOS discipline preserved: this exploration runs ONLY on the IN-SAMPLE
split. Whatever feature(s) look like they separate winners from losers
get confirmed on the untouched OOS split in a follow-up script, not here -
this file is for discovery, not a verdict.

Run on GOLD M15 (clean 2014-06-13+ window).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema, wilder_atr, session_vwap
from meridian_early_cross_test import load_m15


def build_cross_dataset(df):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    tick_vol = df["tick_volume"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)
    day = df["time"].dt.date.values
    hour = df["time"].dt.hour.values
    n = len(df)

    day_start_idx = {}
    day_prior_close_open = {}
    for i in range(n):
        if day[i] not in day_start_idx:
            day_start_idx[day[i]] = i
    days_sorted = sorted(day_start_idx.keys())
    day_open = {}
    day_close = {}
    for idx, d in enumerate(days_sorted):
        s = day_start_idx[d]
        e = (day_start_idx[days_sorted[idx + 1]] - 1) if idx + 1 < len(days_sorted) else n - 1
        day_open[d] = close[s]
        day_close[d] = close[e]

    vol_avg20 = pd.Series(tick_vol).rolling(20, min_periods=20).mean().values

    rows = []
    for i in range(215, n - 1):
        if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(m200[i]) or np.isnan(vwap[i])
                or np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(m21[i - 3])):
            continue
        cross_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
        cross_down = m21[i - 1] >= m50[i - 1] and m21[i] < m50[i]
        if not (cross_up or cross_down):
            continue
        direction = 1 if cross_up else -1

        a = atr[i]
        cross_angle_atr = direction * (m21[i] - m21[i - 3]) / a
        gap_now = m21[i] - m50[i]
        gap_prev = m21[i - 3] - m50[i - 3]
        gap_velocity_atr = direction * (gap_now - gap_prev) / a
        dist_vwap_atr = direction * (close[i] - vwap[i]) / a
        dist_200ema_atr = direction * (close[i] - m200[i]) / a

        d = day[i]
        d_idx = days_sorted.index(d) if d in day_open else None
        prior_day_ret_pct = np.nan
        if d_idx is not None and d_idx > 0:
            prev_d = days_sorted[d_idx - 1]
            if day_open[prev_d] > 0:
                prior_day_ret_pct = direction * (day_close[prev_d] - day_open[prev_d]) / day_open[prev_d] * 100

        vol_ratio = tick_vol[i] / vol_avg20[i] if not np.isnan(vol_avg20[i]) and vol_avg20[i] > 0 else np.nan

        fill_i = i + 1
        if fill_i >= n:
            continue
        entry_px = close[fill_i]

        h6_i = min(fill_i + 24, n - 1)
        fwd_ret_6h = direction * (close[h6_i] - entry_px) / entry_px * 100

        rest_end_i = (day_start_idx[days_sorted[d_idx + 1]] - 1) if d_idx is not None and d_idx + 1 < len(days_sorted) else n - 1
        rest_end_i = max(rest_end_i, fill_i)
        fwd_ret_rest = direction * (close[rest_end_i] - entry_px) / entry_px * 100

        rows.append(dict(i=i, dir=direction, cross_angle_atr=cross_angle_atr, gap_velocity_atr=gap_velocity_atr,
                          dist_vwap_atr=dist_vwap_atr, dist_200ema_atr=dist_200ema_atr,
                          prior_day_ret_pct=prior_day_ret_pct, vol_ratio=vol_ratio, hour_of_day=hour[i],
                          fwd_ret_6h=fwd_ret_6h, fwd_ret_rest=fwd_ret_rest))
    return pd.DataFrame(rows)


def report_feature(dfc, feature, target="fwd_ret_rest", n_bins=5):
    sub = dfc[[feature, target]].dropna()
    if len(sub) < 50:
        print(f"  {feature}: insufficient data (n={len(sub)})")
        return
    corr = sub[feature].corr(sub[target])
    try:
        sub = sub.copy()
        sub["bin"] = pd.qcut(sub[feature], n_bins, duplicates="drop")
        grouped = sub.groupby("bin", observed=True)[target].agg(["mean", "count"])
    except Exception:
        grouped = None
    print(f"\n  {feature}  (corr with {target} = {corr:+.4f}, n={len(sub)})")
    if grouped is not None:
        for b, row in grouped.iterrows():
            print(f"    {str(b):28s}  avg_fwd_ret={row['mean']:7.3f}%  n={int(row['count'])}")


if __name__ == "__main__":
    df, point = load_m15("GOLD")
    n = len(df)
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    print(f"GOLD M15 IN-SAMPLE only: {df_is['time'].iloc[0]} .. {df_is['time'].iloc[-1]}")

    dfc = build_cross_dataset(df_is)
    print(f"\nTotal 21/50 crosses found (any location, any direction): {len(dfc)}")
    print(f"Baseline avg fwd_ret_rest (all crosses, direction-adjusted): {dfc['fwd_ret_rest'].mean():.3f}%")
    print(f"Baseline avg fwd_ret_6h: {dfc['fwd_ret_6h'].mean():.3f}%")
    print(f"Baseline win rate (fwd_ret_rest > 0): {100*(dfc['fwd_ret_rest']>0).mean():.1f}%")

    print(f"\n{'='*100}\nFEATURE BREAKDOWN (quintiles, target = rest-of-session forward return)\n{'='*100}")
    for feat in ["cross_angle_atr", "gap_velocity_atr", "dist_vwap_atr", "dist_200ema_atr",
                 "prior_day_ret_pct", "vol_ratio", "hour_of_day"]:
        report_feature(dfc, feat, "fwd_ret_rest")

    print(f"\n\n{'='*100}\nSame breakdown, target = 6h forward return\n{'='*100}")
    for feat in ["cross_angle_atr", "gap_velocity_atr", "dist_vwap_atr", "dist_200ema_atr",
                 "prior_day_ret_pct", "vol_ratio", "hour_of_day"]:
        report_feature(dfc, feat, "fwd_ret_6h")
