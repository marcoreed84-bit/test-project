"""
Investigation, NOT a new finding to report - SR_BOUNCE's null-test
p-value (0.0005) hit the exact floor of 2000 draws, the same shape of
red flag that turned out to be a real confound twice earlier tonight
(risk-distance mismatch in the first stochastic null; entry/exit
coupling in the second). Before trusting SR_BOUNCE, check whether the
edge is really about the REJECTION geometry (close ends back past the
level) or just about ANY bar that happens to touch a recorded S/R
level, regardless of how it closes - the same kind of "fresh position
timing" artifact already found and controlled for with the stochastic
construction (an "any-cross" control there).

Control: same S/R levels, same risk-matched entry/exit mechanics, but
NO reject condition - entry fires on ANY bar whose wick touches a
recorded level (within the same tolerance), direction = fade away from
the level (same as SR_BOUNCE assigns), regardless of where that bar's
close ends up.

If this ALSO shows a strong edge, SR_BOUNCE's apparent edge is likely
NOT specifically about the rejection candle - it would be about
something more general (level-proximity timing itself). If this
control is weak/flat while SR_BOUNCE is strong, that's real evidence
the rejection geometry specifically matters.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from smc_concepts_batch_test import load_m15, build_trades, SWING_BARS, RR, TIME_CAP_BARS, ATR_PERIOD, PIVOT_LEFT, PIVOT_RIGHT, SR_TOL_ATR, SR_LEVEL_MAX_AGE_BARS
from stoch_ma_stack_gap_filter_test import wilder_atr
from rsi_divergence_entry_test import find_pivots
from dual_stoch_cross_200ema_test import report


def signals_sr_anytouch(o, h, l, c, atr, n, pivot_lows, pivot_highs):
    dirs = [0] * n
    levels = []
    piv_idx = {}
    for p in pivot_lows:
        piv_idx.setdefault(p + PIVOT_RIGHT, []).append(('S', l[p]))
    for p in pivot_highs:
        piv_idx.setdefault(p + PIVOT_RIGHT, []).append(('R', h[p]))

    for i in range(max(PIVOT_LEFT, ATR_PERIOD) + 5, n):
        if i in piv_idx:
            for kind, price in piv_idx[i]:
                levels.append([price, i, kind])
        levels[:] = [lv for lv in levels if i - lv[1] <= SR_LEVEL_MAX_AGE_BARS]
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        tol = SR_TOL_ATR * atr[i]
        for price, created, kind in levels:
            if created >= i:
                continue
            #--- ONLY difference from signals_sr_bounce: no close-reject
            #--- requirement, any touch of the level fires the signal
            if kind == 'R' and h[i] >= price - tol:
                dirs[i] = -1
                break
            if kind == 'S' and l[i] <= price + tol:
                dirs[i] = 1
                break
    return dirs


if __name__ == "__main__":
    df, point = load_m15("GOLD_M15_native.csv", trim_gold=True)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    atr = wilder_atr(h, l, c, ATR_PERIOD)
    pivot_lows = find_pivots(l, PIVOT_LEFT, PIVOT_RIGHT, is_low=True)
    pivot_highs = find_pivots(h, PIVOT_LEFT, PIVOT_RIGHT, is_low=False)

    dirs = signals_sr_anytouch(o, h, l, c, atr, n, pivot_lows, pivot_highs)
    trades = build_trades(df, point, dirs)
    print(f"\n{'#'*100}\nGOLD M15 - SR 'ANY TOUCH' control (no reject requirement)\n{'#'*100}")
    report("GOLD M15 - SR any-touch control", trades, full_days, split_dir=True)
    print(f"\n  Compare against SR_BOUNCE (with reject): n=6764 PF=1.044 net%=56.94")
