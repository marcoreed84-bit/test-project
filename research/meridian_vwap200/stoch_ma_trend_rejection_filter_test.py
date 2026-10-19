"""
Direct request: does requiring the Stoch(21,5,5) zone-cross to happen
WITH the trend (price above EMA21 AND EMA50 for a buy, below both for
a sell) AND specifically on a REJECTION of those MAs (price dipped to
or through one of them in the last few bars, then closed back on the
trend side by the signal bar - a bounce, not just "already far above")
tests better than the unfiltered construction - on GOLD, SILVER, and
BTCUSD.

CORRECTED construction, per the project's own validated H1 pattern
(classic_stoch_21_5_5_btc_h1_stop_trail_test.py), NOT the BTC M15
reference file (classic_stoch_21_5_5_btc_test.py) this was originally
copied from - that file has two real bugs, found while investigating
why this filter's first-pass numbers looked far worse than anything
else tested in this project:
  1. It computes a swing stop and 1:2 R:R target on every entry but
     NEVER checks subsequent bars' highs/lows against them - trades
     only ever exit on the opposite stochastic cross, with ZERO stop-
     loss protection, which alone explains catastrophic win rates.
  2. Its main loop only increments `i` inside the NaN-skip branch -
     every other path (a live cross, an open position) leaves `i`
     unchanged, which is a literal infinite loop; it cannot finish
     running as currently written (confirmed - a run attempt timed
     out at 120s with no output).
A position flip (opposite entry while one is already open, no
intervening exit) is now also explicitly resolved and scored as a real
closed trade at the flip bar's fill price, instead of silently
vanishing from the results uncounted.

Stop/target/opposite-cross exit, grace=0 (immediate exit on opposite
cross, matching this construction's original "textbook, no grace"
intent - grace is a separate, already-tested idea on BTC H1, not
reintroduced here).

Data: GOLD_M15_native.csv (trimmed to the real-data window starting
2014-06-13 - known gotcha), SILVER_M15_native.csv (no such
contamination, full history), BTCUSD_M15_native.csv (full history).
Point size read from each CSV's own header line, never hardcoded.

Honest K=1 per instrument for this filter (new line each - first time
this corrected baseline + MA-rejection filter has run on any of the
three).
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
MA_REJECT_LOOKBACK = 5
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


def build_trades(df, point, use_ma_filter):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    ema_fast_a = ema(close_a, EMA_FAST)
    ema_slow_a = ema(close_a, EMA_SLOW)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    ema_fast, ema_slow = ema_fast_a.tolist(), ema_slow_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    results = []
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_SLOW) + SWING_BARS + MA_REJECT_LOOKBACK + 5
    i = start
    while i < n - 1:
        if not valid[i]:
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

        if use_ma_filter:
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
    print(f"\n{'#'*100}\n{label} M15 - Stoch(21,5,5) zone-cross, swing stop/1:2RR, opposite-cross exit "
          f"(stop/target enforced)\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    base = build_trades(df, point, use_ma_filter=False)
    report(f"{label} M15 - BASELINE (no filter)", base, full_days, split_dir=True)

    filt = build_trades(df, point, use_ma_filter=True)
    report(f"{label} M15 - MA21/50 trend+rejection FILTER", filt, full_days, split_dir=True)

    return base, filt


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K: FIRST test of this MA21/50 trend+rejection filter on all three")
    print(f"  instruments, on a CORRECTED (stop/target-enforced) baseline construction -")
    print(f"  K=1 per instrument for this filter.")
