"""
Follow-up to trend_continuation_stoch_reset_test.py. The original
Continuation construction had the stochastic direction backwards
(uptrend+crossDown+overbought fired BUY; downtrend+crossUp+oversold fired
SELL) - found by checking it against a real annotated chart showing a
downtrend where price rallied to the 21/50EMA at several points and
rolled back over, exactly where a continuation SELL should have fired
and didn't. Corrected:

  BUY  (uptrend): price DIPS to the MA (stoch toward OVERSOLD during the
       dip), stoch crosses UP as the uptrend resumes
  SELL (downtrend): price RALLIES to the MA (stoch toward OVERBOUGHT
       during the rally), stoch crosses DOWN as the downtrend resumes

Same SL/TP exit, spread, and random-timing-null methodology as every
other test in this file. Honest K=1 for this corrected construction
(distinct from the original, backwards version already tested).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from ema21_50_pure_crossover_test import EMA_FAST, EMA_SLOW, GOLD_M15_REAL_START
from vwap_open_scenarios_test import ema
from stoch_ma_stack_gap_filter_test import wilder_atr
from rejection_signal_test import stoch_simple_hl, simulate, pf, report
from trend_continuation_stoch_reset_test import random_null, STOCH_K, STOCH_SLOW, STOCH_D, ZONE_LOW, ZONE_HIGH, RESET_LOOKBACK, NEAR_ATR


def build_signals_fixed(df, point, near_atr=NEAR_ATR, reset_lookback=RESET_LOOKBACK):
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    n = len(df)
    e21 = ema(c, EMA_FAST)
    e50 = ema(c, EMA_SLOW)
    atr = wilder_atr(h, l, c, 14)
    k, d = stoch_simple_hl(h, l, c, STOCH_K, STOCH_SLOW, STOCH_D)

    stCrossUp = np.zeros(n, dtype=bool)
    stCrossDown = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(k[i - 1]) or np.isnan(d[i - 1]):
            continue
        stCrossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
        stCrossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    min_bars = STOCH_K + STOCH_SLOW + STOCH_D + reset_lookback + 10
    dirs = np.zeros(n, dtype=int)
    last_dir = 0
    for i in range(min_bars, n - 1):
        if np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        near = (abs(c[i] - e21[i]) <= near_atr * atr[i]) or (abs(c[i] - e50[i]) <= near_atr * atr[i])
        if not near:
            continue
        dir_ = 0
        if e21[i] > e50[i] and stCrossUp[i]:
            win = k[max(0, i - reset_lookback):i]
            if np.any(~np.isnan(win) & (win <= ZONE_LOW)):
                dir_ = 1
        elif e21[i] < e50[i] and stCrossDown[i]:
            win = k[max(0, i - reset_lookback):i]
            if np.any(~np.isnan(win) & (win >= ZONE_HIGH)):
                dir_ = -1
        if dir_ != 0 and dir_ != last_dir:
            dirs[i] = dir_
            last_dir = dir_
    return dirs, atr, e21, e50


if __name__ == "__main__":
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

        print(f"\n{'#'*100}\n{label} - CORRECTED direction logic\n{'#'*100}")
        dirs, atr, e21, e50 = build_signals_fixed(df, point)
        n_buy, n_sell = int(np.sum(dirs > 0)), int(np.sum(dirs < 0))
        print(f"  Signals: {n_buy + n_sell}  (buy={n_buy}, sell={n_sell})")
        pnl = simulate(df, point, dirs, atr)
        report("  FIXED direction logic", pnl)
        if n_buy > 0:
            report("    -> BUY only", simulate(df, point, dirs, atr, entry_idxs=np.where(dirs > 0)[0]))
        if n_sell > 0:
            report("    -> SELL only", simulate(df, point, dirs, atr, entry_idxs=np.where(dirs < 0)[0]))
        pf_draws, net_draws = random_null(df, point, dirs, atr, e21, e50, n_buy, n_sell)
        real_pf, real_net = pf(pnl), pnl.sum()
        p_pf = (pf_draws >= real_pf).mean()
        p_net = (net_draws >= real_net).mean()
        print(f"  p(null %PF >= real)={p_pf:.4f}   p(null net% >= real)={p_net:.4f}")
