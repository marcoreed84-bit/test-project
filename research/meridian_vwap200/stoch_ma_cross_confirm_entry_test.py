"""
Per direct request, from an annotated live chart: the stochastic cross
at overbought/oversold is still the trigger, but the real confirmation
of trend change is when price CLOSES below (sell) or above (buy) BOTH
the 21 and 50 EMA, happening around/after the 21/50 EMA crossover
itself (not just price being near or past one EMA - the EMA ORDER
itself must also confirm the flip).

Different from stoch_ma_breakout_confirm_entry_test.py (tested
earlier, worse than baseline on all three): that one started from
price being NEAR the MA cluster with no deep-zone requirement and only
checked price vs EMA21. This one keeps the ORIGINAL deep zone-cross
trigger (same as the baseline all night) and adds a stricter two-part
confirmation after it: price must close on the new side of BOTH EMAs,
AND the EMA21/50 order itself must have flipped to match.

Rule: a SELL signal's usual zone-cross trigger (crossDown with
k>ZONE_HIGH) fires at bar i0 as normal. Then wait up to CONFIRM_BARS
bars for the FIRST bar where close < EMA21 AND close < EMA50 AND
EMA21 < EMA50 (both the close and the MA order confirm bearish) -
that confirmation bar is the real entry (filled next bar). If no bar
confirms within the window, the signal is discarded. BUY is the exact
mirror.

Same validated exit (swing stop/1:2RR/opposite-cross, stop/target
enforced every bar). Tested on GOLD, SILVER, BTCUSD M15.

Honest K=1 per instrument - new construction, distinct from the
earlier breakout-confirm entry.
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
from vwap_open_scenarios_test import ema

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_SLOW = 21, 50
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
    e21_a = ema(close_a, EMA_FAST)
    e50_a = ema(close_a, EMA_SLOW)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    e21, e50 = e21_a.tolist(), e50_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW) + SWING_BARS + 5
    i0 = start
    while i0 < n - 1 - CONFIRM_BARS:
        if not valid[i0]:
            i0 += 1
            continue
        trig_dir = 0
        if crossUp[i0] and k[i0] < ZONE_LOW:
            trig_dir = 1
        elif crossDown[i0] and k[i0] > ZONE_HIGH:
            trig_dir = -1
        if trig_dir == 0:
            i0 += 1
            continue

        confirm_i = None
        for j in range(i0 + 1, min(i0 + 1 + CONFIRM_BARS, n)):
            if np.isnan(e21[j]) or np.isnan(e50[j]):
                continue
            if trig_dir > 0:
                confirmed = close[j] > e21[j] and close[j] > e50[j] and e21[j] > e50[j]
            else:
                confirmed = close[j] < e21[j] and close[j] < e50[j] and e21[j] < e50[j]
            if confirmed:
                confirm_i = j
                break
        if confirm_i is None:
            i0 += 1
            continue

        ci = confirm_i
        dir_ = trig_dir
        swing = min(low[ci - SWING_BARS:ci]) if dir_ > 0 else max(high[ci - SWING_BARS:ci])
        risk = dir_ * (close[ci] - swing)
        if risk <= 0.0:
            i0 = ci + 1
            continue
        fill_i = ci + 1
        if fill_i >= n:
            i0 = ci + 1
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
        i0 = exit_i + 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - zone-cross trigger + MA-order-flip confirmation (up to "
          f"{CONFIRM_BARS} bars later)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - MA-cross-confirm entry", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - new construction (stricter confirmation than")
    print(f"  the earlier MA-breakout-confirm test).")
