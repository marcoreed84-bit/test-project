"""
Testing an externally-sourced "rules-based" system pasted in by the
user (source unknown, treated as an unverified claim per this
project's standing rule), combining several ideas already tested
individually tonight - all of which failed - into one more elaborate
system:

  1. STRICT 3-EMA bias: price > EMA21 > EMA50 > EMA200 for longs
     (mirror for shorts) - a stricter/extended version of the 2-EMA
     (21/50) trend+rejection filter already tested tonight (which made
     %PF worse on Gold/Silver, flat on BTC).
  2. Pullback requirement: price must test the EMA21 or EMA50 within a
     recent lookback - same idea as the MA-touch/rejection filter
     already tested tonight (also worse).
  3. Stochastic re-parameterized to 21,7,7 (not yet tried - previous
     tests used 21,5,5 or the table's claimed periods).
  4. Trigger changed from "cross while still below 20" (used
     everywhere else tonight) to "dipped below 20 recently, THEN
     crosses up and closes back ABOVE 20" - a genuinely different
     confirmation-style trigger, similar in spirit to (but distinct
     from) the already-tested breakout-confirm entry (also worse).
  5. Chop filter: skip entirely when the 3-EMA ordering isn't clean
     (implicit - the strict ordering check in #1 already does this).

Given FIVE separate prior tests tonight of individual pieces of this
same idea (trend+rejection filter, trend-ride MA-touch entry,
counter-trend exclusion, MA-breakout-confirm entry, MA-slope regime)
all came back worse or flat, this combined version is tested with
appropriate skepticism but full honesty - stacking multiple already-
failed ideas together does not retroactively validate them, but it
also isn't assumed to fail just because its parts did individually;
tested properly either way.

Same swing stop (10-bar, measured from the trigger bar)/1:2RR/
opposite-cross exit construction as the baseline, stop/target enforced
every bar. Tested on GOLD, SILVER, BTCUSD M15.

Honest K=1 per instrument - genuinely new combined construction (not
identical to any single piece tested before).
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

K_PERIOD, SLOWING, D_PERIOD = 21, 7, 7
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_MID, EMA_SLOW = 21, 50, 200
PULLBACK_LOOKBACK = 10
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
    e50_a = ema(close_a, EMA_MID)
    e200_a = ema(close_a, EMA_SLOW)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    e21, e50, e200 = e21_a.tolist(), e50_a.tolist(), e200_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW) + SWING_BARS + PULLBACK_LOOKBACK + 5
    i = start
    while i < n - 1:
        if not valid[i] or np.isnan(e200[i]):
            i += 1
            continue

        dir_ = 0
        bull_bias = close[i] > e21[i] > e50[i] > e200[i]
        bear_bias = close[i] < e21[i] < e50[i] < e200[i]

        if bull_bias and crossUp[i] and k[i] >= ZONE_LOW:
            dipped = any(k[j] < ZONE_LOW for j in range(i - PULLBACK_LOOKBACK, i) if valid[j])
            pulled_back = any(low[j] <= e21[j] or low[j] <= e50[j] for j in range(i - PULLBACK_LOOKBACK, i + 1))
            if dipped and pulled_back:
                dir_ = 1
        elif bear_bias and crossDown[i] and k[i] <= ZONE_HIGH:
            rallied = any(k[j] > ZONE_HIGH for j in range(i - PULLBACK_LOOKBACK, i) if valid[j])
            pulled_back = any(high[j] >= e21[j] or high[j] >= e50[j] for j in range(i - PULLBACK_LOOKBACK, i + 1))
            if rallied and pulled_back:
                dir_ = -1

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
    print(f"\n{'#'*100}\n{label} M15 - 3-EMA(21/50/200) pullback + Stoch({K_PERIOD},{SLOWING},{D_PERIOD}) "
          f"system\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - 3-EMA pullback system", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - combined construction, genuinely different")
    print(f"  from any single piece already tested tonight.")
