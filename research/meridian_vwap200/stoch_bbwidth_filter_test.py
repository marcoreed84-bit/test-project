"""
Per direct request, from a live M1 Gold chart: "a good trade is when
the bands are further apart from each other" - i.e. Bollinger Band
WIDTH at the signal bar (bands already expanded/wide) predicts a
clean run from one extreme to the other (oversold stoch cross -> price
reaches the upper band; overbought stoch cross -> price reaches the
lower band), vs. a narrow/squeezed band predicting a weak, failed move.

Filter: require BB width (standard 20-period, 2-std-dev Bollinger,
(upper-lower)/middle) at the signal bar to be >= BBWIDTH_PCTL_MIN
percentile of its own trailing distribution (relative, not a fixed
number - band width scales very differently across Gold/Silver/BTC and
across volatility regimes within one instrument, so a percentile
rank against each bar's own trailing window is the fair comparison,
not a single fixed threshold).

Same baseline zone-cross entry + validated swing-stop/1:2RR/opposite-
stoch-cross exit used throughout tonight. Tested on GOLD, SILVER,
BTCUSD M15.

Honest K=1 per instrument - first Bollinger-Band-based idea tonight,
independent from every EMA/stack/volume construction tried so far.
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
BB_PERIOD = 20
BB_STD = 2.0
BBWIDTH_LOOKBACK = 500    # trailing bars used to rank each bar's own BB width
BBWIDTH_PCTL_MIN = 60.0   # require width in the top 40% of its own trailing history
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


def bollinger_width(close, period, nstd):
    s = pd.Series(close)
    mid = s.rolling(period).mean()
    sd = s.rolling(period).std(ddof=0)
    upper = mid + nstd * sd
    lower = mid - nstd * sd
    width = (upper - lower) / mid
    return width.values


def rolling_percentile_rank(x, lookback):
    """For each i, the percentile rank of x[i] within x[i-lookback:i] (trailing, no lookahead)."""
    n = len(x)
    out = np.full(n, np.nan)
    for i in range(lookback, n):
        window = x[i - lookback:i]
        valid = window[~np.isnan(window)]
        if len(valid) < lookback // 2 or np.isnan(x[i]):
            continue
        out[i] = 100.0 * (valid < x[i]).sum() / len(valid)
    return out


def build_trades(df, point, pctl_rank, use_filter):
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
    n_candidates, n_pass = 0, 0
    start = max(K_PERIOD + SLOWING + D_PERIOD, BB_PERIOD + BBWIDTH_LOOKBACK, SWING_BARS + 5)
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        trig_dir = 0
        if crossUp[i] and k[i] < ZONE_LOW:
            trig_dir = 1
        elif crossDown[i] and k[i] > ZONE_HIGH:
            trig_dir = -1
        if trig_dir == 0:
            i += 1
            continue
        n_candidates += 1

        if use_filter:
            pr = pctl_rank[i]
            if np.isnan(pr) or pr < BBWIDTH_PCTL_MIN:
                i += 1
                continue
        n_pass += 1

        dir_ = trig_dir
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

    print(f"  candidates={n_candidates}  pass={n_pass}  (filter={'ON, BBwidth pctl>='+str(BBWIDTH_PCTL_MIN) if use_filter else 'OFF (baseline)'})")
    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    width = bollinger_width(df["close"].values, BB_PERIOD, BB_STD)
    pctl_rank = rolling_percentile_rank(width, BBWIDTH_LOOKBACK)

    print(f"\n{'#'*100}\n{label} M15 - Bollinger Band WIDTH filter on zone-cross stochastic entry\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")

    print(f"\n  --- BASELINE (no BB-width filter) ---")
    trades_base = build_trades(df, point, pctl_rank, use_filter=False)
    report(f"{label} M15 - baseline zone-cross (no BB-width filter)", trades_base, full_days, split_dir=True)

    print(f"\n  --- WITH BB-width filter (top {100-BBWIDTH_PCTL_MIN:.0f}% widest bands only) ---")
    trades_filt = build_trades(df, point, pctl_rank, use_filter=True)
    report(f"{label} M15 - zone-cross + BB-width filter", trades_filt, full_days, split_dir=True)
    return trades_base, trades_filt


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=1 per instrument - first Bollinger-Band-width construction tonight.")
