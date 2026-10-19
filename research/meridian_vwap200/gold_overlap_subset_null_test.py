"""
Per direct request: run GOLD's overlap subset (engulfing-at-extreme
signals that ALSO had a same-bar Stoch(21,5,5)/20-80 zone-cross, same
direction - n=270, %PF=0.936, found in candlestick_stoch_overlap_check.py)
through its own risk-matched random-timing null, same methodology
already validated tonight (candlestick_engulfing_null_test.py).

Honest K=1 (first null check of this specific subset).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from candlestick_engulfing_reversal_test import load_m15, build_trades as build_engulf_trades, SWING_BARS, RR, TIME_CAP_BARS
from candlestick_engulfing_null_test import random_timing_null
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
ZONE_LOW, ZONE_HIGH = 20.0, 80.0


def get_overlap_subset(df, point):
    engulf_trades = build_engulf_trades(df, point)
    high_a, low_a, close_a = df["high"].values, df["low"].values, df["close"].values
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    n = len(df)
    valid = ~(np.isnan(k_a) | np.isnan(d_a))
    crossUp = np.zeros(n, dtype=bool)
    crossDown = np.zeros(n, dtype=bool)
    crossUp[1:] = valid[1:] & valid[:-1] & (k_a[:-1] <= d_a[:-1]) & (k_a[1:] > d_a[1:])
    crossDown[1:] = valid[1:] & valid[:-1] & (k_a[:-1] >= d_a[:-1]) & (k_a[1:] < d_a[1:])

    overlap = []
    for t in engulf_trades:
        i = t["entry_i"]
        dir_ = t["dir"]
        stoch_fires = (crossUp[i] and k_a[i] < ZONE_LOW) if dir_ > 0 else \
                      (crossDown[i] and k_a[i] > ZONE_HIGH)
        if stoch_fires:
            overlap.append(t)
    return overlap


def run():
    df, point = load_m15("GOLD_M15_native.csv", trim_gold=True)
    overlap_trades = get_overlap_subset(df, point)
    real_net = sum(t["pnl_pct"] for t in overlap_trades)
    print(f"\n{'#'*100}\nGOLD M15 - OVERLAP SUBSET (engulfing-at-extreme + same-bar stoch cross) "
          f"vs RISK-MATCHED random timing\n{'#'*100}")
    print(f"  Real: n={len(overlap_trades)}  net%={100*real_net:.2f}")
    real_net2, null_dist, p = random_timing_null(df, point, overlap_trades)
    print(f"  null mean net%  = {100*null_dist.mean():8.2f}")
    print(f"  null std%       = {100*null_dist.std():8.2f}")
    print(f"  null 5th pct    = {100*np.percentile(null_dist, 5):8.2f}")
    print(f"  null 95th pct   = {100*np.percentile(null_dist, 95):8.2f}")
    print(f"  p-value         = {p:.4f}")
    if real_net2 < null_dist.mean():
        verdict = "WORSE than random-timing - entry is picking worse-than-chance timing"
    elif p > 0.05:
        verdict = "NOT distinguishable from random timing (p>0.05) - no demonstrated timing skill"
    else:
        verdict = "BEATS random-timing at p<0.05 - real signal"
    print(f"  -> {verdict}")
    print(f"\n  Honest K=1 (first null check of this specific overlap subset).")


if __name__ == "__main__":
    run()
