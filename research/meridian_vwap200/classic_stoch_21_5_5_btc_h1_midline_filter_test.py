"""
"Must cross the 50 midline" filter, per direct request from a live
chart: require the stochastic to have actually swung through 50 at
some point in the recent bars before the signal cross - filtering out
a shallow wiggle/bounce that stays on one side of 50 and never
genuinely round-trips, like the one circled on the user's chart (the
line dipped toward ~55-60 then turned back up without ever reaching
50).

Rule: at the signal bar, require %K to have touched <=50 (for a BUY)
or >=50 (for a SELL) at least once within the preceding MIDLINE_LOOKBACK
bars - i.e. a genuine swing through the middle, not a shallow bounce
confined to one side.

Same H1 Stoch(21,5,5) entry + swing stop/1:2RR + grace=10 stop-trail
construction as the best result found tonight. Tested
MIDLINE_LOOKBACK in {5, 10, 20} plus "off" (no filter, baseline) on
BTCUSD H1 full real history.

Honest K: this project's BTC stochastic exploration is now at K=31
(27 before this file + 3 midline-lookback values + implicit baseline
re-confirmation here).
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
GRACE_BARS = 10
MIDLINE = 50.0


def build_trades(df, point, midline_lookback):
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
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + max(midline_lookback, 1) + 5
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

        if midline_lookback > 0:
            window = k[i - midline_lookback:i]
            touched_midline = (min(w for w in window if not np.isnan(w)) <= MIDLINE) if dir_ > 0 else \
                               (max(w for w in window if not np.isnan(w)) >= MIDLINE)
            if not touched_midline:
                i += 1
                continue   # shallow wiggle - never swung through 50, skip

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
                    pending_exit_bar = j + GRACE_BARS
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


def run(midline_lookback):
    df, point = load_btc_h1()
    n = len(df)
    label = (f"require %K touched 50 within the preceding {midline_lookback} bars"
              if midline_lookback > 0 else "NO midline filter (baseline)")
    print(f"\n{'#'*100}\nBTCUSD H1 - Stoch(21,5,5) entry + swing stop/1:2RR + grace=10 trail, {label}\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, midline_lookback)
    report(f"BTCUSD H1 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, midline_lookback)
    report(f"BTCUSD H1 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, midline_lookback)
    report(f"BTCUSD H1 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    for mlb in (0, 5, 10, 20):
        run(mlb)
    print(f"\n\n  Honest K: this project's BTC stochastic exploration is now at K=31")
    print(f"  (27 before this file + ~3-4 midline-lookback values here).")
