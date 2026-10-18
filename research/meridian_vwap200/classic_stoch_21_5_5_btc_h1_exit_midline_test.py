"""
Correction of classic_stoch_21_5_5_btc_h1_midline_filter_test.py: that
file applied the "must swing through 50" requirement to the ENTRY,
where it's a no-op (an entry's own zone-cross condition already
requires the stochastic to have passed through 50 to reach 20/80 in
the first place - confirmed empirically, that file's filter changed
essentially nothing).

The user's actual chart point was about the EXIT: the opposite-cross
exit currently fires on ANY cross against the position, however
shallow - including a small wiggle that never even reaches the 50
midline before turning back. This file applies the midline
requirement to the EXIT trigger instead: an opposite cross only counts
as a real exit signal if %K has touched/crossed 50 at some point in
the preceding EXIT_MIDLINE_LOOKBACK bars - i.e. a genuine round-trip
through the middle, not a shallow bounce near the position's own side.
A cross that doesn't qualify is simply ignored (position stays open,
watching for the next cross) - still subject to the stop/target either
way.

Same H1 Stoch(21,5,5) entry + swing stop/1:2RR + grace=10 stop-trail
construction otherwise. Tested EXIT_MIDLINE_LOOKBACK in {0 (off,
baseline), 3, 5, 10} on BTCUSD H1 full real history.

Honest K: this project's BTC stochastic exploration is now at K=35
(31 before this file + 4 values here, including the no-op entry-side
attempt already counted).
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


def build_trades(df, point, exit_midline_lookback):
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

    def exit_cross_touched_midline(j, dir_):
        """For an exit cross AGAINST a position of direction dir_: the
        exit direction is opposite dir_, so touching midline means the
        stochastic reached 50 from the position's favorable side before
        reversing against it."""
        if exit_midline_lookback <= 0:
            return True
        lo = max(0, j - exit_midline_lookback)
        window = [w for w in k[lo:j] if not np.isnan(w)]
        if not window:
            return True
        # the exit (against dir_) needs %K to have been on dir_'s favorable
        # side of 50 recently, i.e. actually swung back toward/through the
        # midline before this reversal - not stayed shallow near the zone
        return (max(window) >= MIDLINE) if dir_ > 0 else (min(window) <= MIDLINE)

    results = []
    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + max(exit_midline_lookback, 1) + 5
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
                if pending_exit_bar is None and opposite and exit_cross_touched_midline(j, dir_):
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


def run(exit_midline_lookback):
    df, point = load_btc_h1()
    n = len(df)
    label = (f"EXIT requires %K touched 50 within the preceding {exit_midline_lookback} bars"
              if exit_midline_lookback > 0 else "NO exit-midline filter (baseline)")
    print(f"\n{'#'*100}\nBTCUSD H1 - Stoch(21,5,5) entry + swing stop/1:2RR + grace=10 trail, {label}\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, exit_midline_lookback)
    report(f"BTCUSD H1 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, exit_midline_lookback)
    report(f"BTCUSD H1 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, exit_midline_lookback)
    report(f"BTCUSD H1 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    for emlb in (0, 3, 5, 10):
        run(emlb)
    print(f"\n\n  Honest K: this project's BTC stochastic exploration is now at K=35")
    print(f"  (31 before this file + 4 values here).")
