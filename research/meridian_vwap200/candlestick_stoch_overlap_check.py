"""
Direct question: do any of the engulfing-at-extreme candlestick signals
(candlestick_engulfing_reversal_test.py) occur on the SAME bar as a
stochastic zone-cross signal (the construction tested all night)?

Measures, for every engulfing-at-extreme entry bar: does the Stoch
(21,5,5) zone-cross condition ALSO fire on that exact bar, same
direction? Reports the overlap count/percentage, and splits the
engulfing trades' own %PF by overlap vs no-overlap, to see whether the
(small) overlapping subset performs differently - purely descriptive,
not a new tested construction.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from candlestick_engulfing_reversal_test import load_m15, build_trades as build_engulf_trades
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
ZONE_LOW, ZONE_HIGH = 20.0, 80.0


def pct_pf(pnls):
    pnls = np.array(pnls)
    gw = pnls[pnls > 0].sum()
    gl = -pnls[pnls <= 0].sum()
    return gw / gl if gl > 0 else np.inf


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    engulf_trades = build_engulf_trades(df, point)

    high_a, low_a, close_a = df["high"].values, df["low"].values, df["close"].values
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    n = len(df)
    valid = ~(np.isnan(k_a) | np.isnan(d_a))
    crossUp = np.zeros(n, dtype=bool)
    crossDown = np.zeros(n, dtype=bool)
    crossUp[1:] = valid[1:] & valid[:-1] & (k_a[:-1] <= d_a[:-1]) & (k_a[1:] > d_a[1:])
    crossDown[1:] = valid[1:] & valid[:-1] & (k_a[:-1] >= d_a[:-1]) & (k_a[1:] < d_a[1:])

    overlap_pnls, no_overlap_pnls = [], []
    overlap_count = 0
    for t in engulf_trades:
        i = t["entry_i"]
        dir_ = t["dir"]
        stoch_fires = (crossUp[i] and k_a[i] < ZONE_LOW) if dir_ > 0 else \
                      (crossDown[i] and k_a[i] > ZONE_HIGH)
        if stoch_fires:
            overlap_count += 1
            overlap_pnls.append(t["pnl_pct"])
        else:
            no_overlap_pnls.append(t["pnl_pct"])

    total = len(engulf_trades)
    print(f"\n{'#'*100}\n{label} M15 - engulfing-at-extreme vs Stoch(21,5,5)/20-80 same-bar overlap\n{'#'*100}")
    print(f"  Total engulfing-at-extreme signals: {total}")
    print(f"  Also had a stochastic zone-cross on the SAME bar, same direction: "
          f"{overlap_count} ({100*overlap_count/total:.1f}%)")
    if overlap_pnls:
        print(f"    Overlap subset:    n={len(overlap_pnls):5d}  %PF={pct_pf(overlap_pnls):.3f}  "
              f"win%={100*np.mean(np.array(overlap_pnls)>0):.1f}")
    if no_overlap_pnls:
        print(f"    No-overlap subset: n={len(no_overlap_pnls):5d}  %PF={pct_pf(no_overlap_pnls):.3f}  "
              f"win%={100*np.mean(np.array(no_overlap_pnls)>0):.1f}")


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", True)
    run_instrument("SILVER", "SILVER_M15_native.csv", False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", False)
    print(f"\n\n  Descriptive check only - not a new tested construction, no honest K consumed.")
