"""
Per direct request: "try a different entry construction entirely...
something must tell us which trades are likely to reverse after the
stochastic cross." Genuinely different construction from every zone-
cross variant tested tonight: classic regular bullish/bearish
DIVERGENCE, not a filter on the plain cross.

Rule: track successive oversold EXCURSIONS (consecutive runs where %K
stays below ZONE_LOW) and overbought excursions (above ZONE_HIGH)
separately. Each excursion's "low point" is recorded as (min %K during
the excursion, the price low at that same bar). A BUY fires on the
%K/%D cross-up that ends an oversold excursion ONLY IF this excursion's
price low is LOWER than the PREVIOUS oversold excursion's price low
(price made a genuine new low) WHILE this excursion's %K low is HIGHER
than the previous excursion's %K low (the stochastic did NOT confirm
the new low - momentum weakening even as price pushes lower - the
textbook definition of bullish divergence). SELL is the exact mirror
on overbought excursions/swing highs.

This is NOT the same as the zone-cross construction tested all night -
it requires TWO successive excursions into the zone with a specific
price/stoch relationship between them, which most single crosses never
satisfy, so trade count will be much lower by construction (a genuine
different, rarer setup, not a filter cutting an existing population).

Same validated exit (swing stop/1:2RR/opposite-cross, stop/target
enforced every bar - confirmed tonight to add real value over a
random-duration exit) kept unchanged, since the question is purely
about the ENTRY now.

Tested on GOLD, SILVER, BTCUSD M15. Honest K=1 per instrument - first
test of this entry construction, genuinely new (not a filter on an
already-tested one).
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

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
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

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    i = start

    prev_os_exc, cur_os_exc = None, None  # oversold: [min_k, price_low]
    prev_ob_exc, cur_ob_exc = None, None  # overbought: [max_k, price_high]

    while i < n - 1:
        if not valid[i]:
            i += 1
            continue

        if k[i] < ZONE_LOW:
            if cur_os_exc is None:
                cur_os_exc = [k[i], low[i]]
            elif k[i] < cur_os_exc[0]:
                cur_os_exc[0], cur_os_exc[1] = k[i], low[i]
        if k[i] > ZONE_HIGH:
            if cur_ob_exc is None:
                cur_ob_exc = [k[i], high[i]]
            elif k[i] > cur_ob_exc[0]:
                cur_ob_exc[0], cur_ob_exc[1] = k[i], high[i]

        dir_ = 0
        if crossUp[i] and k[i] < ZONE_LOW and cur_os_exc is not None and prev_os_exc is not None:
            if cur_os_exc[1] < prev_os_exc[1] and cur_os_exc[0] > prev_os_exc[0]:
                dir_ = 1
        elif crossDown[i] and k[i] > ZONE_HIGH and cur_ob_exc is not None and prev_ob_exc is not None:
            if cur_ob_exc[1] > prev_ob_exc[1] and cur_ob_exc[0] < prev_ob_exc[0]:
                dir_ = -1

        if k[i] >= ZONE_LOW and cur_os_exc is not None:
            prev_os_exc = cur_os_exc
            cur_os_exc = None
        if k[i] <= ZONE_HIGH and cur_ob_exc is not None:
            prev_ob_exc = cur_ob_exc
            cur_ob_exc = None

        if dir_ == 0:
            i += 1
            continue

        swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
        risk = dir_ * (close[i] - swing)
        if risk <= 0.0:
            i += 1
            continue
        fill_i = i + 1
        if fill_i >= n:
            i += 1
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
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    print(f"\n{'#'*100}\n{label} M15 - STOCHASTIC DIVERGENCE entry (price new extreme, %K does NOT "
          f"confirm)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - Divergence entry", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - genuinely NEW entry construction (regular")
    print(f"  bullish/bearish divergence, not a filter on the plain zone-cross).")
