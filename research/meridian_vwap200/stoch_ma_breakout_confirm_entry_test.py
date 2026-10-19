"""
Per direct request, from an annotated live chart: moving averages
crossed, price riding along them, stochastic cross fires near the MA
cluster - "I think in this case the only valid stochastic cross would
be when price is near the moving averages but actually after the
cross closes at least above the 21ema, that has a better chance of
going up and breaking through to change direction."

Genuinely new entry construction (not a filter on the existing
zone-cross entry's own bar): stochastic crosses in zone while price is
NEAR the MA cluster (within MA_NEAR_ATR x ATR of EMA21 or EMA50 - not
required to already be above/below, matching "riding the MAs" in the
chart) - but does NOT enter immediately. Instead it WAITS up to
CONFIRM_BARS bars for a subsequent bar to actually CLOSE on the trade
side of EMA21 (above for a buy, below for a sell) - that confirmation
bar is the real entry trigger (filled next bar, same as every other
construction tonight). If no bar confirms within the window, the
signal is discarded - no trade.

This differs from both earlier MA tests tonight:
  - stoch_ma_trend_rejection_filter_test.py required trend-alignment
    AT the cross bar itself (no waiting) - found worse %PF.
  - stoch_counter_trend_exclude_test.py only removed the worst bucket,
    no waiting/confirmation either - also worse/flat.
This one is a genuine entry-timing DELAY: catch the cross near the MAs
(not already past them), then wait for real confirmation before
committing capital, which the chart specifically points at.

Same corrected (stop/target enforced) Stoch(21,5,5)/20-80 zone-cross
construction, swing stop measured from the CONFIRMATION bar (not the
original cross bar, since price has moved by the time of entry).

Honest K=1 per instrument for this new entry construction.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from vwap_open_scenarios_test import ema, wilder_atr

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_SLOW = 21, 50
MA_NEAR_ATR = 0.5
CONFIRM_BARS = 10
TIME_CAP_BARS = 300
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


def build_trades(df, point):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    ema_fast_a = ema(close_a, EMA_FAST)
    ema_slow_a = ema(close_a, EMA_SLOW)
    atr_a = wilder_atr(high_a, low_a, close_a, 14)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    ema_fast, ema_slow, atr = ema_fast_a.tolist(), ema_slow_a.tolist(), atr_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW, 14) + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i] or np.isnan(ema_fast[i]) or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        dir_ = 0
        if crossUp[i] and k[i] < ZONE_LOW:
            dir_ = 1
        elif crossDown[i] and k[i] > ZONE_HIGH:
            dir_ = -1
        if dir_ == 0:
            i += 1
            continue

        near = min(abs(close[i] - ema_fast[i]), abs(close[i] - ema_slow[i])) <= MA_NEAR_ATR * atr[i]
        if not near:
            i += 1
            continue

        confirm_i = None
        for j in range(i + 1, min(i + 1 + CONFIRM_BARS, n)):
            if np.isnan(ema_fast[j]):
                continue
            confirmed = (close[j] > ema_fast[j]) if dir_ > 0 else (close[j] < ema_fast[j])
            if confirmed:
                confirm_i = j
                break
        if confirm_i is None:
            i += 1
            continue

        ci = confirm_i
        swing = min(low[ci - SWING_BARS:ci]) if dir_ > 0 else max(high[ci - SWING_BARS:ci])
        risk = dir_ * (close[ci] - swing)
        if risk <= 0.0:
            i = ci + 1
            continue
        fill_i = ci + 1
        if fill_i >= n:
            i = ci + 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
        stop_px = swing
        target_px = entry_px + dir_ * RR * risk
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
            target_hit = (high[j] >= target_px) if dir_ > 0 else (low[j] <= target_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if target_hit:
                exit_i, exit_px, reason = j, target_px, "TARGET"
                break
            if valid[j] and valid[j - 1]:
                opposite = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if opposite:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-STOCH"
                    break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=ci, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - MA-BREAKOUT-CONFIRM entry: cross near MAs, wait up to "
          f"{CONFIRM_BARS} bars for a close past EMA21\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - MA-breakout-confirm entry", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - genuinely new entry construction (cross near")
    print(f"  the MAs, delayed until a confirmed close past EMA21).")
