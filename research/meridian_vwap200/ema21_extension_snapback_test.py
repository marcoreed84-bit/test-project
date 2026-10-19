"""
Per direct request: "when price is pulled far away from the moving
averages, the snap back" - a MEAN-REVERSION construction, the opposite
family from everything else tried tonight (which was all trend-
following: trade WITH the cross/stack direction). This bets AGAINST
the extension: when price first stretches EXT_ATR_MIN*ATR away from
EMA21 (a fresh event, not "every bar while extended"), enter counter-
trend, betting on reversion back toward the EMA.

Entry: close[i] first crosses >= EXT_ATR_MIN*ATR above EMA21 (was below
that on bar i-1) -> SELL (bet on pullback). Mirror for a fresh
extension below -> BUY. No stochastic in this first pass (isolate the
extension idea on its own first, per the plan to test one piece before
re-adding the stochastic as a filter).

Exit: the FIRST of - the natural mean-reversion target (price touches
EMA21 again, i.e. the snap-back actually completing), a hard swing
stop beyond the extension's own recent extreme, or a time cap. No
fixed R:R target - "reverts to the mean" IS the target, not an
arbitrary multiple.

Honest K=1 per instrument - new, independent construction (first
mean-reversion idea tonight, everything before this was trend-following).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report
from vwap_open_scenarios_test import ema
from stoch_ma_stack_gap_filter_test import wilder_atr

EMA_FAST = 21
ATR_PERIOD = 14
EXT_ATR_MIN = 2.0
SWING_BARS = 10
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
    e21_a = ema(close_a, EMA_FAST)
    atr_a = wilder_atr(high_a, low_a, close_a, ATR_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    e21 = e21_a.tolist()
    atr = atr_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(atr[i]) or atr[i] <= 0.0) for i in range(n)]

    def ext_state(i):
        if not valid[i]:
            return 0
        gap_atr = (close[i] - e21[i]) / atr[i]
        if gap_atr >= EXT_ATR_MIN:
            return 1    # extended ABOVE -> mean-reversion bet is SELL
        if gap_atr <= -EXT_ATR_MIN:
            return -1   # extended BELOW -> mean-reversion bet is BUY
        return 0

    results = []
    start = max(EMA_FAST, ATR_PERIOD + 1) + SWING_BARS + 5
    i = start
    while i < n - 1:
        es_prev = ext_state(i - 1)
        es_cur = ext_state(i)
        fresh = (es_cur != 0 and es_cur != es_prev)
        if not fresh:
            i += 1
            continue

        dir_ = -es_cur   # bet AGAINST the extension direction
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
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if valid[j]:
                touched_ema = (high[j] >= e21[j]) if dir_ > 0 else (low[j] <= e21[j])
                if touched_ema:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = e21[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-SNAPBACK"
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
    print(f"\n{'#'*100}\n{label} M15 - mean-reversion: fresh {EXT_ATR_MIN}ATR extension from EMA21, "
          f"bet on snap-back to EMA21\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    trades = build_trades(df, point)
    report(f"{label} M15 - EMA21 extension snap-back", trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - first MEAN-REVERSION construction tonight,")
    print(f"  everything before this was trend-following.")
