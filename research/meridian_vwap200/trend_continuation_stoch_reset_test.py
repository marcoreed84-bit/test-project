"""
New construction, per direct request: "signals for trend continuation,
example where price is overbought and the stochastic crosses to go back
to oversold near the moving averages." Read as: in an UPTREND, the
stochastic reaches overbought then crosses back down (resetting) WHILE
price is near the moving averages (pulled back, not extended) - a
continuation BUY (buy the dip in an ongoing uptrend, using the stoch
reset as the pullback's timing trigger). Mirror for a DOWNTREND:
stochastic reaches oversold then crosses back up, price near the MAs -
continuation SELL.

Conditions (buy case):
  T = trend: EMA21 > EMA50
  N = price near the MAs: |close - EMA21| <= InpNearATR x ATR (pulled
      back close to the fast MA, not extended away from it)
  S = stochastic reset: %K reached >= zoneHigh (overbought) within the
      last RESET_LOOKBACK bars, THEN crossed back below %D (the actual
      reset-down event) on this bar

Mirror for sell: T'=EMA21<EMA50, N same, S'=%K reached <= zoneLow then
crossed back above %D.

Genuinely new construction (not a filter on anything already tested) -
honest K=1. Same SL(swing)/TP(RR) exit and spread/null-test methodology
as every other overlay test in this project, tested on GOLD M5 (2022+)
and M15 (2014-06-13+) so the two timeframes can be compared directly.
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

STOCH_K, STOCH_SLOW, STOCH_D = 14, 5, 5
ZONE_LOW, ZONE_HIGH = 15.0, 85.0
RESET_LOOKBACK = 10      # %K must have reached the zone within this many bars before the cross
NEAR_ATR = 1.0            # how close to EMA21 counts as "near the moving averages"
NULL_DRAWS = 2000


def build_signals(df, point, near_atr=NEAR_ATR, reset_lookback=RESET_LOOKBACK):
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
        near = abs(c[i] - e21[i]) <= near_atr * atr[i]
        if not near:
            continue
        dir_ = 0
        if e21[i] > e50[i] and stCrossDown[i]:
            # reset-from-overbought: %K reached >= ZONE_HIGH within the lookback, ending at this cross
            win = k[max(0, i - reset_lookback):i]
            if np.any(~np.isnan(win) & (win >= ZONE_HIGH)):
                dir_ = 1
        elif e21[i] < e50[i] and stCrossUp[i]:
            win = k[max(0, i - reset_lookback):i]
            if np.any(~np.isnan(win) & (win <= ZONE_LOW)):
                dir_ = -1
        if dir_ != 0 and dir_ != last_dir:
            dirs[i] = dir_
            last_dir = dir_
    return dirs, atr, e21, e50


def random_null(df, point, dirs, atr, e21, e50, n_buy, n_sell):
    n = len(df)
    bull_idx = np.where(e21 > e50)[0]
    bear_idx = np.where(e21 < e50)[0]
    rng = np.random.default_rng(11)
    pf_draws, net_draws = [], []
    for _ in range(NULL_DRAWS):
        rand_dirs = np.zeros(n, dtype=int)
        if n_buy > 0 and len(bull_idx) >= n_buy:
            sel = rng.choice(bull_idx, size=n_buy, replace=False)
            rand_dirs[sel] = 1
        if n_sell > 0 and len(bear_idx) >= n_sell:
            sel = rng.choice(bear_idx, size=n_sell, replace=False)
            rand_dirs[sel] = -1
        pnl_r = simulate(df, point, rand_dirs, atr)
        if len(pnl_r) > 0:
            pf_draws.append(pf(pnl_r))
            net_draws.append(pnl_r.sum())
    return np.array(pf_draws), np.array(net_draws)


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

        print(f"\n{'#'*100}\n{label}: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars)\n{'#'*100}")

        dirs, atr, e21, e50 = build_signals(df, point)
        n_buy, n_sell = int(np.sum(dirs > 0)), int(np.sum(dirs < 0))
        print(f"  Signals: {n_buy + n_sell}  (buy={n_buy}, sell={n_sell})")

        pnl = simulate(df, point, dirs, atr)
        report("REAL trend-continuation stoch-reset (SL/TP exit)", pnl)
        if n_buy > 0:
            report("  -> BUY only", simulate(df, point, dirs, atr, entry_idxs=np.where(dirs > 0)[0]))
        if n_sell > 0:
            report("  -> SELL only", simulate(df, point, dirs, atr, entry_idxs=np.where(dirs < 0)[0]))

        if n_buy + n_sell >= 20:
            pf_draws, net_draws = random_null(df, point, dirs, atr, e21, e50, n_buy, n_sell)
            real_pf, real_net = pf(pnl), pnl.sum()
            p_pf = (pf_draws >= real_pf).mean()
            p_net = (net_draws >= real_net).mean()
            print(f"  NULL (n={len(pf_draws)} draws, trend-side-matched random entries, same exit/spread): "
                  f"median %PF={np.median(pf_draws):.3f}  median net%={100*np.median(net_draws):.2f}")
            print(f"  p(null %PF >= real)={p_pf:.4f}   p(null net% >= real)={p_net:.4f}")
        else:
            print("  Too few signals for a meaningful null test.")
