"""
Per direct request: test every remaining common candlestick pattern as
its own entry (not a filter on anything else), same exit convention as
the one validated candlestick construction tonight
(candlestick_engulfing_reversal_test.py: swing stop + fixed 1:2 R:R,
no opposite-signal exit - that construction never defined one).

Five patterns, each its own independent construction:
  1. PIN BAR / HAMMER (bullish) / SHOOTING STAR (bearish) at a swing
     extreme - long wick rejection, small body, little wick on the
     opposite side, pattern bar is the N-bar swing low/high itself.
  2. DOJI at a swing extreme - near-zero body relative to the bar's
     own range, at the N-bar swing low (bullish) or high (bearish).
  3. MORNING STAR (bullish) / EVENING STAR (bearish) - classic 3-bar
     reversal: large opposite-colored bar, small-bodied "star", then a
     large same-colored bar closing back past the first bar's midpoint
     - at a swing extreme.
  4. INSIDE BAR BREAKOUT - a bar fully contained within the prior
     bar's range, entry on the breakout bar closing beyond the mother
     bar's own high/low. NOT swing-extreme-gated (a continuation/
     compression pattern, not a reversal one).
  5. THREE WHITE SOLDIERS (bullish) / THREE BLACK CROWS (bearish) -
     three consecutive same-direction bars, each closing beyond the
     prior close, each opening within the prior body (no large gaps).
     NOT swing-extreme-gated (a momentum-continuation pattern).

Tested on GOLD, SILVER, BTCUSD M15. Honest K=5 per instrument (5
independent pattern constructions tried in this one batch).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report

SWING_BARS = 10
RR = 2.0
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


def swing_low_high(low, high, i, n_bars):
    lo = min(low[i - n_bars + 1:i + 1])
    hi = max(high[i - n_bars + 1:i + 1])
    return lo, hi


def signals_pinbar(o, h, l, c, n):
    dirs = [0] * n
    for i in range(SWING_BARS, n):
        rng = h[i] - l[i]
        if rng <= 0:
            continue
        body = abs(c[i] - o[i])
        lowerWick = min(o[i], c[i]) - l[i]
        upperWick = h[i] - max(o[i], c[i])
        swLow, swHigh = swing_low_high(l, h, i, SWING_BARS)
        if lowerWick >= 2.0 * body and upperWick <= 0.3 * rng and l[i] <= swLow:
            dirs[i] = 1
        elif upperWick >= 2.0 * body and lowerWick <= 0.3 * rng and h[i] >= swHigh:
            dirs[i] = -1
    return dirs


def signals_doji(o, h, l, c, n):
    dirs = [0] * n
    for i in range(SWING_BARS, n):
        rng = h[i] - l[i]
        if rng <= 0:
            continue
        body = abs(c[i] - o[i])
        if body > 0.1 * rng:
            continue
        swLow, swHigh = swing_low_high(l, h, i, SWING_BARS)
        if l[i] <= swLow:
            dirs[i] = 1
        elif h[i] >= swHigh:
            dirs[i] = -1
    return dirs


def signals_star(o, h, l, c, n):
    dirs = [0] * n
    for i in range(SWING_BARS + 2, n):
        b1, b2, b3 = i - 2, i - 1, i
        body1 = abs(c[b1] - o[b1])
        body2 = abs(c[b2] - o[b2])
        body3 = abs(c[b3] - o[b3])
        if body1 <= 0 or body3 <= 0:
            continue
        small_star = body2 <= 0.3 * min(body1, body3)
        mid1 = (o[b1] + c[b1]) / 2.0
        swLow, swHigh = swing_low_high(l, h, b1, SWING_BARS)

        # morning star: bar1 bearish, bar3 bullish closing above bar1 midpoint
        if c[b1] < o[b1] and c[b3] > o[b3] and small_star and c[b3] > mid1 and l[b1] <= swLow:
            dirs[i] = 1
        # evening star: bar1 bullish, bar3 bearish closing below bar1 midpoint
        elif c[b1] > o[b1] and c[b3] < o[b3] and small_star and c[b3] < mid1 and h[b1] >= swHigh:
            dirs[i] = -1
    return dirs


def signals_inside_breakout(o, h, l, c, n):
    dirs = [0] * n
    for i in range(2, n):
        mother, inside, brk = i - 2, i - 1, i
        is_inside = h[inside] <= h[mother] and l[inside] >= l[mother]
        if not is_inside:
            continue
        if c[brk] > h[mother]:
            dirs[i] = 1
        elif c[brk] < l[mother]:
            dirs[i] = -1
    return dirs


def signals_three_soldiers_crows(o, h, l, c, n):
    dirs = [0] * n
    for i in range(2, n):
        b1, b2, b3 = i - 2, i - 1, i
        bull = (c[b1] > o[b1] and c[b2] > o[b2] and c[b3] > o[b3] and
                c[b2] > c[b1] and c[b3] > c[b2] and
                o[b2] >= min(o[b1], c[b1]) and o[b2] <= max(o[b1], c[b1]) and
                o[b3] >= min(o[b2], c[b2]) and o[b3] <= max(o[b2], c[b2]))
        bear = (c[b1] < o[b1] and c[b2] < o[b2] and c[b3] < o[b3] and
                c[b2] < c[b1] and c[b3] < c[b2] and
                o[b2] >= min(o[b1], c[b1]) and o[b2] <= max(o[b1], c[b1]) and
                o[b3] >= min(o[b2], c[b2]) and o[b3] <= max(o[b2], c[b2]))
        if bull:
            dirs[i] = 1
        elif bear:
            dirs[i] = -1
    return dirs


PATTERNS = {
    "PINBAR":           signals_pinbar,
    "DOJI":             signals_doji,
    "STAR":             signals_star,
    "INSIDE_BREAKOUT":  signals_inside_breakout,
    "3SOLDIERS_CROWS":  signals_three_soldiers_crows,
}


def build_trades(df, point, dirs):
    o_a, h_a, l_a, c_a = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    spread_a = df["spread"].values
    n = len(df)
    h, l, c, spread = h_a.tolist(), l_a.tolist(), c_a.tolist(), spread_a.tolist()

    results = []
    next_free = SWING_BARS + 5
    for i in range(n - 1):
        dir_ = dirs[i]
        if dir_ == 0 or i < next_free:
            continue
        swing = min(l[i - SWING_BARS:i]) if dir_ > 0 else max(h[i - SWING_BARS:i])
        risk = dir_ * (c[i] - swing)
        if risk <= 0.0:
            continue
        fill_i = i + 1
        if fill_i >= n:
            continue
        sc = spread[fill_i] * point
        entry_px = c[fill_i] + (sc if dir_ > 0 else -sc)
        stop_px = swing
        target_px = entry_px + dir_ * RR * risk
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            stop_hit = (l[j] <= stop_px) if dir_ > 0 else (h[j] >= stop_px)
            target_hit = (h[j] >= target_px) if dir_ > 0 else (l[j] <= target_px)
            if stop_hit:
                exit_i, exit_px, reason = j, stop_px, "STOP"
                break
            if target_hit:
                exit_i, exit_px, reason = j, target_px, "TARGET"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, c[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * dir_
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=dir_,
                             reason=reason, hold_bars=exit_i - fill_i))
        next_free = exit_i + 1

    return results


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    n = len(df)
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    o, h, l, c = df["open"].tolist(), df["high"].tolist(), df["low"].tolist(), df["close"].tolist()
    print(f"\n{'#'*100}\n{label} M15 - batch candlestick pattern test ({n} bars)\n{'#'*100}")

    for name, fn in PATTERNS.items():
        dirs = fn(o, h, l, c, n)
        trades = build_trades(df, point, dirs)
        report(f"{label} M15 - {name}", trades, full_days, split_dir=True)


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=5 per instrument (5 independent pattern constructions this batch).")
