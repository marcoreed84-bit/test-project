"""
Combines the two best-performing ideas tested tonight on BTC: the H1
timeframe (classic_stoch_21_5_5_btc_h1_test.py - full-history %PF
0.201->0.388 just from moving off M15) and the grace+trail exit
mechanism (classic_stoch_21_5_5_btc_stop_trail_test.py - %PF 0.201->
0.399 on M15 at grace=10), now tested TOGETHER on H1 for the first
time.

Construction: Stoch(21,5,5) Low/High+SMA zone-cross entry, swing stop
(SWING_BARS closed H1 bars) + 1:2 R:R target, STOCH exit with
grace_bars window (favorable re-cross cancels the pending exit AND
trails the stop to the new swing level, same 21,5,5 stochastic used
for both entry and exit per the user's original construction).

Tested grace_bars in {0, 5, 10} on BTCUSD H1 full real history, real
(resampled-max) spread. Honest K: this project's BTC stochastic
exploration today is now at K=23 (20 before this file + 3 grace
values here, on H1).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR
from classic_stoch_21_5_5_btc_h1_test import load_btc_h1

TIME_CAP_BARS = 300


def build_trades(df, point, grace_bars):
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

        pending_exit_bar = None
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
                favorable = (dir_ > 0 and crossUp[j]) or (dir_ < 0 and crossDown[j])
                opposite  = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                if pending_exit_bar is not None and favorable:
                    new_swing = min(low[j - SWING_BARS:j]) if dir_ > 0 else max(high[j - SWING_BARS:j])
                    if dir_ > 0 and new_swing > stop_px:
                        stop_px = new_swing
                    elif dir_ < 0 and new_swing < stop_px:
                        stop_px = new_swing
                    pending_exit_bar = None
                if pending_exit_bar is None and opposite:
                    pending_exit_bar = j if grace_bars <= 0 else j + grace_bars
                if pending_exit_bar is not None and j >= pending_exit_bar:
                    scj = spread[j] * point
                    exit_i = j
                    exit_px = close[j] - (scj if dir_ > 0 else -scj)
                    reason = "EXIT-STOCH-GRACE"
                    break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run(grace_bars):
    df, point = load_btc_h1()
    n = len(df)
    label = f"grace={grace_bars} bars (stop trails on favorable recross)" if grace_bars > 0 else "grace=0 (immediate exit)"
    print(f"\n{'#'*100}\nBTCUSD H1 - Stoch(21,5,5) entry, swing stop/1:2RR, STOCH exit WITH {label}\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, grace_bars)
    report(f"BTCUSD H1 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, grace_bars)
    report(f"BTCUSD H1 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, grace_bars)
    report(f"BTCUSD H1 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    for gb in (0, 5, 10):
        run(gb)
    print(f"\n\n  Honest K: this project's BTC stochastic exploration today is now at K=23")
    print(f"  (20 before this file + 3 grace values here, on H1).")
