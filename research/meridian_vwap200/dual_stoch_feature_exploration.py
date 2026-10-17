"""
Exploratory, not a new tested construction: every attempt tonight to
tighten the ENTRY condition (zone-exit instead of cross, cross-after-
exit, confirmation delay) made results worse, not better - all three
ended up looser/noisier than the original plain cross-in-zone, not
stricter. Per direct question, instead of guessing another filter,
this measures real candidate features of the cross itself against
each trade's ACTUAL outcome, on the best construction so far
(dual_stoch_atr_target_test.py: plain cross-in-zone + 200EMA + MA/VWAP
stop + 1.0xATR target), same technique this project already used on
Meridian's cross/pullback research earlier tonight.

Candidate features, all measured causally at or before the signal bar:
  - line_gap_at_cross: |fast - slow| at the cross bar itself (how far
    apart they separate right at the cross, signed favorably)
  - line_gap_2bars_later: the same gap 2 bars after the cross - does
    the separation KEEP GROWING (real momentum) or stall/narrow
    (false start)?
  - fast_slope_3bar / slow_slope_3bar: each line's own rate of change
    over the 3 bars into the cross (the "angle" - steeper = more
    committed move, not just a lazy drift across the other line)
  - dip_depth: how far below 20 (or above 80) the deeper of the two
    lines reached before the cross - a shallow brush past 20 vs a
    real plunge to single digits

IS-ONLY (GOLD M15), per this project's walk-forward discipline -
exploring on OOS data would contaminate it for later confirmation.
Reports quintile breakdowns + correlation, same format as
pullback_feature_exploration.py/cross_feature_exploration.py earlier
tonight. This is NOT a new backtested variant and has no honest-K
cost by itself - but if any feature found here becomes an actual
filter, THAT becomes a new K entry, tested out-of-sample, not just
reported as "found significant" on the same data it was discovered in.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import stoch_close_smoothed, load_m15, ema, OVERSOLD, OVERBOUGHT
from vwap_open_scenarios_test import wilder_atr, session_vwap
from dual_stoch_atr_target_test import build_trades_atr_target


def report_feature(dfc, feature, target="pnl_pct", n_bins=5):
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
            print(f"    {str(b):28s}  avg_pnl%={100*row['mean']:7.3f}  n={int(row['count'])}")


if __name__ == "__main__":
    df, point = load_m15("GOLD")
    n = len(df)
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    print(f"GOLD M15 IN-SAMPLE only: {df_is['time'].iloc[0]} .. {df_is['time'].iloc[-1]}")

    close = df_is["close"].values
    kA, _ = stoch_close_smoothed(close, 21, 5, 5)
    kB, _ = stoch_close_smoothed(close, 14, 3, 3)

    trades = build_trades_atr_target(df_is, point)
    print(f"Total trades: {len(trades)}")
    print(f"Baseline avg pnl%: {100*np.mean([t['pnl_pct'] for t in trades]):.4f}%   "
          f"win rate: {100*np.mean([t['pnl_pct']>0 for t in trades]):.1f}%")

    rows = []
    for t in trades:
        i = t["entry_i"]
        direction = t["dir"]
        if i < 3 or i + 2 >= len(kA):
            continue
        gap_now = (kB[i] - kA[i]) * direction
        gap_later = (kB[i + 2] - kA[i + 2]) * direction if not (np.isnan(kB[i+2]) or np.isnan(kA[i+2])) else np.nan
        fast_slope = (kB[i] - kB[i - 3]) * direction
        slow_slope = (kA[i] - kA[i - 3]) * direction
        dip_depth = (OVERSOLD - min(kA[i], kB[i])) if direction > 0 else (max(kA[i], kB[i]) - OVERBOUGHT)
        rows.append(dict(gap_now=gap_now, gap_later=gap_later, fast_slope=fast_slope,
                          slow_slope=slow_slope, dip_depth=dip_depth, pnl_pct=t["pnl_pct"]))

    dfc = pd.DataFrame(rows)
    print(f"\n{'='*100}\nFEATURE BREAKDOWN (quintiles, target = realized trade pnl%)\n{'='*100}")
    for feat in ["gap_now", "gap_later", "fast_slope", "slow_slope", "dip_depth"]:
        report_feature(dfc, feat)
