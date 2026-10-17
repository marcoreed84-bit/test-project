"""
"Criss-crossing" / chop filter for the BTC classic Stoch(21,5,5)
construction, per direct request: skip an entry signal if the
stochastic has been whipsawing (multiple crosses close together)
right before it, and only take a "clean" cross - one with no other
cross in the preceding LOOKBACK bars.

Rule: count how many crosses (either direction) happened in the
LOOKBACK bars immediately before the signal bar. If that count is
above MAX_RECENT_CROSSES, treat the signal as noise/chop and skip it
entirely (no trade). A truly clean, decisive cross should have the
stochastic sitting still beforehand, not flipping back and forth.

Entry/stop/target/exit otherwise identical to the no-filter baseline
(classic_stoch_21_5_5_btc_h4_trend_test.py's unfiltered case).

Tested LOOKBACK=15 with MAX_RECENT_CROSSES in {0, 1, 2} on BTCUSD M15
full real history, real spread. Honest K: this project's BTC
stochastic exploration today is now at K=19 (16 before this file + 3
chop-filter threshold values here).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import load_btc_m15, K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR

TIME_CAP_BARS = 300
LOOKBACK = 15


def build_trades(df, point, max_recent_crosses):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    anyCross = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]
            anyCross[i] = crossUp[i] or crossDown[i]

    # rolling count of crosses in the preceding LOOKBACK bars (EXCLUDING
    # the signal bar itself, which is naturally a cross)
    recent_cross_count = [0] * n
    window_sum = 0
    for i in range(n):
        if i - LOOKBACK >= 0 and anyCross[i - LOOKBACK]:
            window_sum -= 1
        # bars strictly before i, i.e. up to i-1
        if i >= 1 and anyCross[i - 1]:
            window_sum += 1
        recent_cross_count[i] = window_sum

    results = []
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
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

        if recent_cross_count[i] > max_recent_crosses:
            i += 1
            continue   # choppy run-up to this cross - skip as noise

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


def run(max_recent_crosses):
    df, point = load_btc_m15()
    n = len(df)
    label = (f"chop filter: skip if >{max_recent_crosses} cross(es) in preceding {LOOKBACK} bars"
              if max_recent_crosses < 99 else "NO filter (baseline)")
    print(f"\n{'#'*100}\nBTCUSD M15 - Stoch(21,5,5) entry + swing stop/1:2RR, {label}\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, max_recent_crosses)
    report(f"BTCUSD M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, max_recent_crosses)
    report(f"BTCUSD M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, max_recent_crosses)
    report(f"BTCUSD M15 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    for mrc in (99, 2, 1, 0):   # 99 = effectively no filter (baseline)
        run(mrc)
    print(f"\n\n  Honest K: this project's BTC stochastic exploration today is now at K=19")
    print(f"  (16 before this file + 3 chop-filter threshold values here).")
