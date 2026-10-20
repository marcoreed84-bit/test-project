"""
Follow-up to rejection_signal_test.py. The Rejection signal (5 conditions:
trend + 50EMA-reject + 21EMA-break + BB-mid-close + stoch-confirm) came
back a net loser (%PF ~0.97-1.00) on both GOLD M5 and M15, and tightening
the lookback window (2-20 bars) didn't rescue it. This isolates which of
the individual conditions is actually hurting, by dropping each one at a
time from the base construction (lookback=3, the best value found) and
re-testing - same SL/TP exit, same spread, same honest no-opposite-repeat
rule.

Conditions (sell case - buy is the mirror):
  T = trend (21EMA < 50EMA)
  R = reached/rejected the 50EMA within the lookback window
  X = broke back below the 21EMA this bar (the actual trigger - always on,
      can't meaningfully be dropped, it's what defines "this bar")
  B = closes below the Bollinger mid-band this bar
  S = a stochastic %K/%D down-cross happened within the confirm window
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from ema21_50_pure_crossover_test import load_m15, EMA_FAST, EMA_SLOW, GOLD_M15_REAL_START
from vwap_open_scenarios_test import ema
from stoch_ma_stack_gap_filter_test import wilder_atr
from rejection_signal_test import stoch_simple_hl, bb_mid, simulate, pf, report

STOCH_K, STOCH_SLOW, STOCH_D = 14, 5, 5
BB_PERIOD = 20
REJ_LOOKBACK = 3
REJ_TOUCH_ATR = 0.3
REJ_STOCH_WINDOW = 5


def build_signals_flex(df, point, use_reach=True, use_bb=True, use_stoch=True):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    e21 = ema(c, EMA_FAST)
    e50 = ema(c, EMA_SLOW)
    atr = wilder_atr(h, l, c, 14)
    mid = bb_mid(c, BB_PERIOD)
    k, d = stoch_simple_hl(h, l, c, STOCH_K, STOCH_SLOW, STOCH_D)

    n_ = len(c)
    stCrossUp = np.zeros(n_, dtype=bool)
    stCrossDown = np.zeros(n_, dtype=bool)
    for i in range(1, n_):
        if np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(k[i - 1]) or np.isnan(d[i - 1]):
            continue
        stCrossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
        stCrossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    min_bars = max(BB_PERIOD, STOCH_K + STOCH_SLOW + STOCH_D) + REJ_LOOKBACK + 10
    dirs = np.zeros(n, dtype=int)
    last_dir = 0
    for i in range(min_bars, n - 1):
        if np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(mid[i]) or np.isnan(atr[i]):
            continue
        tol = REJ_TOUCH_ATR * atr[i]
        bear = e21[i] < e50[i]
        bull = e21[i] > e50[i]
        dir_ = 0
        if bear and c[i - 1] >= e21[i - 1] and c[i] < e21[i]:
            ok_bb = (c[i] < mid[i]) if use_bb else True
            ok_reach = (not use_reach) or np.any(h[max(0, i - REJ_LOOKBACK):i] >= e50[max(0, i - REJ_LOOKBACK):i] - tol)
            ok_stoch = (not use_stoch) or np.any(stCrossDown[max(0, i - REJ_STOCH_WINDOW):i + 1])
            if ok_bb and ok_reach and ok_stoch:
                dir_ = -1
        elif bull and c[i - 1] <= e21[i - 1] and c[i] > e21[i]:
            ok_bb = (c[i] > mid[i]) if use_bb else True
            ok_reach = (not use_reach) or np.any(l[max(0, i - REJ_LOOKBACK):i] <= e50[max(0, i - REJ_LOOKBACK):i] + tol)
            ok_stoch = (not use_stoch) or np.any(stCrossUp[max(0, i - REJ_STOCH_WINDOW):i + 1])
            if ok_bb and ok_reach and ok_stoch:
                dir_ = 1
        if dir_ != 0 and dir_ != last_dir:
            dirs[i] = dir_
            last_dir = dir_
    return dirs, atr


if __name__ == "__main__":
    variants = [
        ("FULL (T+R+X+B+S)",        True,  True,  True),
        ("drop STOCH (T+R+X+B)",    True,  True,  False),
        ("drop BB-mid (T+R+X+S)",   True,  False, True),
        ("drop REACH (T+X+B+S)",    False, True,  True),
        ("just T+X (trend+21break only)", False, False, False),
    ]

    for label, fname, trim in [("GOLD M5", "GOLD_M5_native.csv", False), ("GOLD M15", "GOLD_M15_native.csv", True)]:
        path = os.path.join(os.path.dirname(__file__), "..", "data", fname)
        with open(path) as f:
            header1 = f.readline()
        point = float(header1.split("meta_point,")[1].split(",")[0])
        df = pd.read_csv(path, skiprows=1)
        df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
        df = df.sort_values("time").reset_index(drop=True)
        if trim:
            df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)

        print(f"\n{'#'*90}\n{label}\n{'#'*90}")
        for vlabel, use_reach, use_bb, use_stoch in variants:
            dirs, atr = build_signals_flex(df, point, use_reach, use_bb, use_stoch)
            n_sig = int(np.sum(dirs != 0))
            pnl = simulate(df, point, dirs, atr)
            report(f"{vlabel:32s} n_sig={n_sig:5d}", pnl)
