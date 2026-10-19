"""
Direct request: does requiring the Stoch(21,5,5) zone-cross to happen
WITH the trend (price above EMA21 AND EMA50 for a buy, below both for
a sell) AND specifically on a REJECTION of those MAs (price dipped to
or through one of them in the last few bars, then closed back on the
trend side by the signal bar - a bounce, not just "already far above")
tests better than the unfiltered construction - on GOLD, SILVER, and
BTCUSD.

Same exact M15 zone-cross construction as classic_stoch_21_5_5_btc_test.py
(the one actually drawn on TradePanel_EA's chart overlay): Stoch(21,5,5)
Low/High/SMA, entry on cross-in-zone, exit on the SAME stoch's opposite
cross (no zone requirement), swing stop (10-bar), 1:2 R:R target, real
variable spread, fill on next bar close.

MA_REJECT_LOOKBACK bars controls how recent the MA touch must be.

Data: GOLD_M15_native.csv (trimmed to the real-data window starting
2014-06-13 - known gotcha, the pre-2014 bars are mislabeled daily/hourly
data), SILVER_M15_native.csv (no such contamination, full history used),
BTCUSD_M15_native.csv (full history). Point size read from each CSV's
own header line, never hardcoded.

This is the FIRST time this exact construction (M15, no grace/trail) has
been run on GOLD or SILVER at all, and the first time this specific MA-
trend-rejection filter has been tested on any of the three - a new line
for each instrument. Honest K=1 per instrument for this filter (baseline
construction itself is the established TradePanel-matching one, already
run unfiltered on BTC M15 before - not re-counted here).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report, TIME_CAP_BARS
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from vwap_open_scenarios_test import ema

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_SLOW = 21, 50
MA_REJECT_LOOKBACK = 5
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")


def load_m15(symbol_file, trim_gold=False):
    path = os.path.join(DATA_DIR, symbol_file)
    with open(path) as f:
        header1 = f.readline()
    point = float(header1.split("meta_point,")[1].split(",")[0])
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    if trim_gold:
        df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df, point


def build_trades(df, point, use_ma_filter):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    k, d = stochastic_lowhigh_sma(high, low, close, K_PERIOD, SLOWING, D_PERIOD)
    ema_fast = ema(close, EMA_FAST)
    ema_slow = ema(close, EMA_SLOW)

    results = []
    posDir = 0
    open_i = open_fill_i = None
    open_entry_px = open_dir = None
    open_stop_px = open_target_px = open_hard_limit = None
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW) + SWING_BARS + MA_REJECT_LOOKBACK + 5
    i = start
    while i < n - 1:
        if np.isnan(k[i]) or np.isnan(d[i]) or np.isnan(k[i - 1]) or np.isnan(d[i - 1]):
            i += 1
            continue
        crossUp = k[i - 1] <= d[i - 1] and k[i] > d[i]
        crossDown = k[i - 1] >= d[i - 1] and k[i] < d[i]
        dir_ = 0
        if crossUp and k[i] < ZONE_LOW:
            dir_ = 1
        elif crossDown and k[i] > ZONE_HIGH:
            dir_ = -1

        if dir_ != 0 and use_ma_filter:
            trend_ok = (close[i] > ema_fast[i] and close[i] > ema_slow[i]) if dir_ > 0 else \
                       (close[i] < ema_fast[i] and close[i] < ema_slow[i])
            rejection_ok = False
            if trend_ok:
                for j in range(i - MA_REJECT_LOOKBACK, i + 1):
                    if dir_ > 0 and (low[j] <= ema_fast[j] or low[j] <= ema_slow[j]):
                        rejection_ok = True
                        break
                    if dir_ < 0 and (high[j] >= ema_fast[j] or high[j] >= ema_slow[j]):
                        rejection_ok = True
                        break
            if not (trend_ok and rejection_ok):
                dir_ = 0

        if dir_ != 0:
            swing = low[i - SWING_BARS:i].min() if dir_ > 0 else high[i - SWING_BARS:i].max()
            risk = dir_ * (close[i] - swing)
            if risk > 0.0:
                posDir = dir_
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
                    open_i, open_fill_i = i, fill_i
                    open_entry_px, open_dir = entry_px, dir_
                    open_stop_px = swing
                    open_target_px = entry_px + dir_ * RR * risk
                    open_hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        if posDir != 0 and not np.isnan(k[i]) and not np.isnan(d[i]) and not np.isnan(k[i - 1]) and not np.isnan(d[i - 1]):
            exCrossUp = crossUp
            exCrossDown = crossDown
            exitFires = (posDir > 0 and exCrossDown) or (posDir < 0 and exCrossUp)
            if exitFires and open_fill_i is not None and i > open_fill_i:
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    exit_px = close[fill_i] - (sc if open_dir > 0 else -sc)
                    pnl_pct = ((exit_px - open_entry_px) / open_entry_px) * open_dir
                    results.append(dict(entry_i=open_i, exit_i=i, pnl_pct=pnl_pct, dir=open_dir,
                                         reason="EXIT-STOCH", hold_bars=i - open_fill_i))
                posDir = 0
                open_fill_i = None
        i += 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    print(f"\n{'#'*100}\n{label} M15 - Stoch(21,5,5) zone-cross, swing stop/1:2RR, opposite-cross exit\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")

    base = build_trades(df, point, use_ma_filter=False)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    report(f"{label} M15 - BASELINE (no filter)", base, full_days, split_dir=True)

    filt = build_trades(df, point, use_ma_filter=True)
    report(f"{label} M15 - MA21/50 trend+rejection FILTER", filt, full_days, split_dir=True)

    return base, filt


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K: FIRST test of this MA21/50 trend+rejection filter on all three")
    print(f"  instruments - K=1 per instrument for this filter. The unfiltered M15")
    print(f"  Stoch(21,5,5) baseline itself was already established/tested on BTC M15")
    print(f"  before (not re-counted); this is its first run on GOLD and SILVER M15.")
