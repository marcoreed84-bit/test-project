"""
Diagnostic (not a filter/backtest) per direct request: "how many times
when price is below the 21 and 50 EMA, does the stochastic cross to go
up, only for it again to cross and go back into oversold?"

For every real BUY zone-cross signal, measure:
  - Was price below BOTH EMA21 and EMA50 at the signal bar (counter-
    trend) or above BOTH (with-trend) or mixed (one above, one below)?
  - Did %K go back below ZONE_LOW within the next FAIL_LOOKAHEAD bars
    (a "failed" signal - back into oversold shortly after) or not
    (escaped cleanly)?
Mirrored for SELL signals (above both EMAs = counter-trend for a sell,
failure = %K back above ZONE_HIGH).

This is a plain count/percentage, not a trading construction - no
stop/target/spread/P&L involved. It directly answers the question with
real numbers instead of more guessing, and is MUCH cheaper to compute
than a full backtest (no per-trade exit simulation), so it covers all
three instruments in one run.

Tested on GOLD, SILVER, BTCUSD M15 (21,5,5, 20/80 zone - this project's
most-used construction). GOLD trimmed to its real-data window
(2014-06-13+). Point size not needed here (no P&L computed).

This supplements, not replaces, the MA21/50 trend+rejection FILTER test
already run earlier tonight (which found no edge, in some cases worse)
- that tested whether FORCING trend-alignment improves %PF net of
costs. This measures the raw failure-rate pattern itself, which is a
more direct answer to the specific question asked.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from vwap_open_scenarios_test import ema

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST, EMA_SLOW = 21, 50
FAIL_LOOKAHEAD = 20
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")


def load_m15(symbol_file, trim_gold=False):
    path = os.path.join(DATA_DIR, symbol_file)
    df = pd.read_csv(path, skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    if trim_gold:
        df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df


def diagnose(df):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    ema_fast_a = ema(close_a, EMA_FAST)
    ema_slow_a = ema(close_a, EMA_SLOW)

    k = k_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k_a[i - 1] <= d_a[i - 1] and k_a[i] > d_a[i]
            crossDown[i] = k_a[i - 1] >= d_a[i - 1] and k_a[i] < d_a[i]

    buckets = {
        "buy_below_both_ema":  {"total": 0, "failed": 0},
        "buy_above_both_ema":  {"total": 0, "failed": 0},
        "buy_mixed_ema":       {"total": 0, "failed": 0},
        "sell_above_both_ema": {"total": 0, "failed": 0},
        "sell_below_both_ema": {"total": 0, "failed": 0},
        "sell_mixed_ema":      {"total": 0, "failed": 0},
    }

    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW) + 5
    for i in range(start, n - FAIL_LOOKAHEAD - 1):
        if not valid[i]:
            continue
        ef, es = ema_fast_a[i], ema_slow_a[i]
        if np.isnan(ef) or np.isnan(es):
            continue

        if crossUp[i] and k[i] < ZONE_LOW:
            above_fast, above_slow = close_a[i] > ef, close_a[i] > es
            bucket = "buy_above_both_ema" if (above_fast and above_slow) else \
                     "buy_below_both_ema" if (not above_fast and not above_slow) else "buy_mixed_ema"
            failed = any(valid[j] and k[j] < ZONE_LOW for j in range(i + 1, i + 1 + FAIL_LOOKAHEAD))
            buckets[bucket]["total"] += 1
            buckets[bucket]["failed"] += int(failed)

        elif crossDown[i] and k[i] > ZONE_HIGH:
            above_fast, above_slow = close_a[i] > ef, close_a[i] > es
            bucket = "sell_above_both_ema" if (above_fast and above_slow) else \
                     "sell_below_both_ema" if (not above_fast and not above_slow) else "sell_mixed_ema"
            failed = any(valid[j] and k[j] > ZONE_HIGH for j in range(i + 1, i + 1 + FAIL_LOOKAHEAD))
            buckets[bucket]["total"] += 1
            buckets[bucket]["failed"] += int(failed)

    return buckets


def run_instrument(label, symbol_file, trim_gold):
    df = load_m15(symbol_file, trim_gold=trim_gold)
    buckets = diagnose(df)
    print(f"\n{'#'*100}\n{label} M15 - signal failure rate by MA side (fail = %K back in the opposite\n"
          f"extreme zone within {FAIL_LOOKAHEAD} bars)\n{'#'*100}")
    for name, b in buckets.items():
        if b["total"] == 0:
            print(f"  {name:<22} n=0")
            continue
        rate = 100 * b["failed"] / b["total"]
        print(f"  {name:<22} n={b['total']:6d}   failed={b['failed']:6d}   fail-rate={rate:5.1f}%")
    return buckets


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Diagnostic only - no P&L/spread/stop-target involved, not a backtest.")
    print(f"  Honest K: this is a measurement, not a tested filter - if the pattern here")
    print(f"  motivates a new filter construction, that filter needs its own honest K and")
    print(f"  full backtest+null test before being trusted (per this project's standing rule).")
