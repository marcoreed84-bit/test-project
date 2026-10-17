"""
Adds a REAL stop-loss to the grace-period exit idea tested in
classic_stoch_21_5_5_btc_grace_exit_test.py, per direct follow-up
request: "there has to be a stop loss ... like in the instance where
they cross within bars again would have to be moved" - i.e. a genuine
protective stop (swing low/high, same construction the EA's own
overlay already shows), and when the grace window's favorable re-cross
happens, TRAIL the stop up/down to the new swing level instead of just
canceling the pending exit outright.

Construction:
  - Entry: Stochastic(21,5,5) Low/High+SMA cross-in-zone (unchanged).
  - Initial stop: swing low/high of the preceding SWING_BARS closed
    bars (same as the EA's overlay stop).
  - Target: 1:2 R:R off that initial risk (kept as a reference ceiling
    - not the main exit mechanism, matches the EA's displayed TP).
  - STOCH exit with grace+trail: when the SAME 21,5,5 stochastic
    crosses against the position, don't exit yet - watch up to
    grace_bars bars. If a favorable cross happens first, CANCEL the
    pending exit AND move the stop to the new swing low/high at that
    point (only ever tightening, never loosening). If grace_bars pass
    with no favorable cross, exit then at that bar's close.
  - Real stop-loss and target are checked on EVERY bar regardless of
    grace state - a hard stop/target hit always exits immediately,
    grace only applies to the stochastic-cross exit mechanism.
  - Hard time cap (300 bars) as the final fallback.

Tested on BTCUSD M15 full real history, real spread. grace_bars in
{0, 5, 10} (narrower sweep than the no-stop version, since this is a
genuinely new construction layered on top of two already-tried ideas
today - K discipline below).

Honest K: today's BTC stochastic exploration is now at K=11 total
(1 plain signal-to-signal + 5 grace-only values + 5 more here with a
real stop/trail) - all against the SAME BTCUSD M15 history, same day.
That matters for how much to trust any one result that looks decent.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import report, pct_pf
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import load_btc_m15, K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH, RR

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
                    # recovered - cancel the pending exit AND trail the stop
                    # to the new swing level (only ever tightening)
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
    df, point = load_btc_m15()
    n = len(df)
    label = f"grace={grace_bars} bars (stop trails on favorable recross)" if grace_bars > 0 else "grace=0 (immediate exit, no trailing)"
    print(f"\n{'#'*100}\nBTCUSD M15 - Stoch(21,5,5) entry, swing stop + 1:2RR target, STOCH exit WITH {label}\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point, grace_bars)
    report(f"BTCUSD M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point, grace_bars)
    report(f"BTCUSD M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point, grace_bars)
    report(f"BTCUSD M15 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    for gb in (0, 5, 10):
        run(gb)
    print(f"\n\n  Honest K: today's BTC stochastic exploration is now at K=11 total")
    print(f"  (1 plain signal-to-signal + 5 grace-only + 5 more here with a real")
    print(f"  stop/trail) - all against the SAME BTCUSD M15 history, same day.")
