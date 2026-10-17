"""
Grace-period exit variant of classic_stoch_21_5_5_btc_test.py, per
direct request from a live BTC M15 chart screenshot: the first
oversold %K/%D cross-up triggered a BUY; a SECOND cross (back down)
would have exited it per the plain "exit on opposite cross" rule, but
price then recovered and kept rising - the request is to test NOT
exiting on that first opposite cross, instead waiting up to
GRACE_BARS bars to see if the stochastic crosses back in the trade's
favor before actually closing.

Rule (own construction, not from any uploaded article - built exactly
to the request's spec): when the exit-stochastic crosses against the
open position, don't exit yet. Watch the next GRACE_BARS bars:
  - if a FAVORABLE cross (same direction as the open position) happens
    first, CANCEL the pending exit - stay in the trade, keep watching
    for the next real opposite cross as normal.
  - if GRACE_BARS pass with no favorable cross, exit THEN (at that
    bar's price - you genuinely stayed in the trade through the grace
    window, so the exit price reflects wherever price actually is at
    the end of it, not the original signal bar).
  - if a THIRD cross (another opposite one) happens before the grace
    window ends, it does not reset or extend the window - the
    original deadline still applies.

Same entry/exit stochastic (21,5,5, Low/High+SMA) and zone-cross entry
as the baseline file, same real spread, same BTCUSD M15 full history.
Tests GRACE_BARS in {3, 5, 8, 12} plus GRACE_BARS=0 (= the plain
baseline rule, for a same-run comparison) - honest K: 5 (five grace
values tried against the same data in this file).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import report
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import load_btc_m15, K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, ZONE_LOW, ZONE_HIGH


def build_trades(df, point, grace_bars):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)

    # plain Python lists - much faster than numpy scalar indexing in a tight loop
    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()

    results = []
    posDir = 0
    open_i = open_fill_i = None
    open_entry_px = None
    open_dir = 0
    pending_exit_bar = None   # bar index where the grace window expires, or None if no pending exit

    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    last = n - 1
    for i in range(start, last):
        if not valid[i] or not valid[i - 1]:
            continue
        ki, ki1, di, di1 = k[i], k[i - 1], d[i], d[i - 1]
        crossUp = ki1 <= di1 and ki > di
        crossDown = ki1 >= di1 and ki < di

        # ENTRY
        dir_ = 0
        if crossUp and ki < ZONE_LOW:
            dir_ = 1
        elif crossDown and ki > ZONE_HIGH:
            dir_ = -1
        if dir_ != 0:
            swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
            risk = dir_ * (close[i] - swing)
            if risk > 0.0:
                posDir = dir_
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    open_entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
                    open_i, open_fill_i, open_dir = i, fill_i, dir_
                    pending_exit_bar = None

        # EXIT (with grace period)
        if posDir != 0 and open_fill_i is not None and i > open_fill_i:
            favorable_cross = (posDir > 0 and crossUp) or (posDir < 0 and crossDown)
            opposite_cross  = (posDir > 0 and crossDown) or (posDir < 0 and crossUp)

            if pending_exit_bar is not None and favorable_cross:
                pending_exit_bar = None   # recovered - cancel the pending exit

            if pending_exit_bar is None and opposite_cross:
                pending_exit_bar = i if grace_bars <= 0 else i + grace_bars

            if pending_exit_bar is not None and i >= pending_exit_bar:
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    exit_px = close[fill_i] - (sc if open_dir > 0 else -sc)
                    pnl_pct = ((exit_px - open_entry_px) / open_entry_px) * open_dir
                    results.append(dict(entry_i=open_i, exit_i=i, pnl_pct=pnl_pct, dir=open_dir,
                                         reason="EXIT-STOCH-GRACE", hold_bars=i - open_fill_i))
                posDir = 0
                open_fill_i = None
                pending_exit_bar = None

    return results


def run(grace_bars):
    df, point = load_btc_m15()
    n = len(df)
    label = f"grace={grace_bars} bars" if grace_bars > 0 else "grace=0 (plain baseline)"
    print(f"\n{'#'*100}\nBTCUSD M15 - classic Stoch(21,5,5) entry, SAME 21,5,5 exit WITH {label}\n{'#'*100}")
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
    for gb in (0, 3, 5, 8, 12):
        run(gb)
    print(f"\n\n  Honest K: 5 (grace_bars in {{0,3,5,8,12}} all tried against the same")
    print(f"  BTCUSD M15 history in this one file).")
