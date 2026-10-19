"""
Per direct request: how does this construction perform when the 21/50
EMAs are moving SIDEWAYS (flat slope, choppy market, price breaking
above and below repeatedly) vs at an ANGLE (trending)? This is the
natural next question given tonight's pattern so far - five separate
trend-alignment/confirmation tests (filter, exclusion, breakout-
confirm, trend-ride entry, leg_efficiency) all found this construction
does WORSE when forced to trade with an established trend. If it's
genuinely a mean-reversion system, it should do BETTER in a flat/choppy
regime and WORSE in a trending one - the opposite filter from
everything tried so far.

Method: classify each real baseline signal bar by EMA21's own slope
over a trailing window (SLOPE_LOOKBACK bars), normalized by ATR so it's
comparable across instruments/price levels. Split into terciles (flat/
mid/sloped) and report %PF for each bucket separately - a breakdown of
the EXISTING unfiltered baseline, not a new filtered construction yet
(if a clear pattern shows up, the flat-regime-only version should then
be built and tested properly with its own honest K, same discipline as
every other result tonight).

Same Stoch(21,5,5)/20-80 zone-cross construction, stop/target enforced,
as the established baseline. Diagnostic/breakdown only for this file;
Honest K: 0 (reuses the existing baseline's own trades, does not fire
a new backtest of a new construction - the regime split itself isn't
"tested" against anything yet, it's descriptive).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from vwap_open_scenarios_test import ema, wilder_atr

K_PERIOD, SLOWING, D_PERIOD = 21, 5, 5
SWING_BARS = 10
RR = 2.0
ZONE_LOW, ZONE_HIGH = 20.0, 80.0
EMA_FAST = 21
SLOPE_LOOKBACK = 20
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


def build_trades_with_slope(df, point):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)
    ema_fast_a = ema(close_a, EMA_FAST)
    atr_a = wilder_atr(high_a, low_a, close_a, 14)

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
    start = max(K_PERIOD + SLOWING + D_PERIOD, EMA_FAST + SLOPE_LOOKBACK, 14) + SWING_BARS + 5
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

        atr_i = atr_a[i]
        slope = np.nan
        if atr_i and atr_i > 0 and not np.isnan(ema_fast_a[i]) and not np.isnan(ema_fast_a[i - SLOPE_LOOKBACK]):
            slope = abs(ema_fast_a[i] - ema_fast_a[i - SLOPE_LOOKBACK]) / atr_i

        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i, ma_slope=slope))
        i = exit_i + 1

    return results


def pct_pf(pnls):
    pnls = np.array(pnls)
    gw = pnls[pnls > 0].sum()
    gl = -pnls[pnls <= 0].sum()
    return gw / gl if gl > 0 else np.inf


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    trades = build_trades_with_slope(df, point)
    slopes = np.array([t["ma_slope"] for t in trades])
    pnls = np.array([t["pnl_pct"] for t in trades])
    valid_mask = ~np.isnan(slopes)
    slopes_v, pnls_v = slopes[valid_mask], pnls[valid_mask]

    print(f"\n{'#'*100}\n{label} M15 - %PF by EMA21 slope regime (flat=sideways/choppy, "
          f"steep=trending), terciles\n{'#'*100}")
    q1, q2 = np.percentile(slopes_v, [33.33, 66.67])
    flat = pnls_v[slopes_v <= q1]
    mid = pnls_v[(slopes_v > q1) & (slopes_v <= q2)]
    steep = pnls_v[slopes_v > q2]
    for name, bucket in [("FLAT (bottom tercile)", flat), ("MID (middle tercile)", mid),
                          ("STEEP (top tercile, trending)", steep)]:
        if len(bucket) == 0:
            continue
        win_pct = 100 * (bucket > 0).mean()
        print(f"  {name:<32} n={len(bucket):6d}  win%={win_pct:5.1f}  %PF={pct_pf(bucket):6.3f}  "
              f"net%={100*bucket.sum():9.2f}")
    corr = np.corrcoef(slopes_v, pnls_v)[0, 1]
    print(f"  (overall slope-vs-pnl correlation: {corr:+.4f}, n={len(slopes_v)})")
    return trades


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Breakdown/diagnostic of the EXISTING unfiltered baseline - no new")
    print(f"  construction tested yet. If flat clearly beats steep, that motivates a")
    print(f"  real flat-regime-only filter test next, with its own honest K.")
