"""
Per direct request: test support/resistance bounce, fair-value-gap
(FVG) fill, order-block retest, and Fibonacci-retracement-zone
continuation - four "smart money concepts" style constructions, each
independent, each its own entry trigger. Same exit convention as the
candlestick batch (swing stop + fixed 1:2 R:R, no opposite-signal
exit) for a clean comparison against everything else tested tonight.

Simplified, explicit definitions used (documented per construction so
there's no ambiguity about what was actually tested):

1. SR_BOUNCE: confirmed swing pivots (5-bar-left/right local extrema)
   are kept as S/R levels. When a later bar's wick comes within
   TOL_ATR*ATR of a still-recent level and the bar's CLOSE ends back on
   the far side of it (a rejection, not a clean break), fire a fade
   entry away from the level.

2. FVG_FILL: a 3-bar fair-value-gap (bar i-2's high < bar i's low =
   bullish gap, zone = [high[i-2], low[i]]; mirror for bearish). The
   FIRST time price later trades back into that zone and closes back
   out the favorable side, fire a continuation entry in the gap's own
   original direction (price "defending" the gap, the SMC claim).
   Each gap only triggers once (first fill-and-reject).

3. ORDER_BLOCK: a confirmed swing-high break (close breaks above the
   most recent confirmed pivot high = bullish structure break) marks
   the LAST bearish-close candle in the 10 bars before the break as a
   bullish order block (its [low,high] range). When price later
   retraces back into that range, fire a continuation BUY. Mirror for
   bearish breaks/order blocks.

4. FIB_ZONE: between consecutive opposite-direction confirmed pivots
   (a "leg"), compute the 61.8%-78.6% retracement zone. The first time
   price re-enters that zone after the leg completes and closes back
   toward the leg's original direction, fire a continuation entry in
   that direction.

Tested on GOLD, SILVER, BTCUSD M15. Honest K=4 per instrument (this
batch), ON TOP of the K=15 honest total from the candlestick-pattern
batch run just before this one, and everything else tried tonight -
each batch's K is tracked and reported separately per CLAUDE.md.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from meridian_early_cross_test import DATA_DIR
from dual_stoch_cross_200ema_test import report
from stoch_ma_stack_gap_filter_test import wilder_atr
from rsi_divergence_entry_test import find_pivots

SWING_BARS = 10
RR = 2.0
TIME_CAP_BARS = 300
ATR_PERIOD = 14
PIVOT_LEFT, PIVOT_RIGHT = 5, 5
SR_TOL_ATR = 0.3
SR_LEVEL_MAX_AGE_BARS = 2000
FIB_LOW, FIB_HIGH = 0.618, 0.786
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


def signals_sr_bounce(o, h, l, c, atr, n, pivot_lows, pivot_highs):
    dirs = [0] * n
    levels = []   # (price, created_at, kind) kind: 'S' or 'R'
    piv_idx = {}
    for p in pivot_lows:
        piv_idx.setdefault(p + PIVOT_RIGHT, []).append(('S', l[p]))
    for p in pivot_highs:
        piv_idx.setdefault(p + PIVOT_RIGHT, []).append(('R', h[p]))

    for i in range(max(PIVOT_LEFT, ATR_PERIOD) + 5, n):
        if i in piv_idx:
            for kind, price in piv_idx[i]:
                levels.append([price, i, kind])
        levels[:] = [lv for lv in levels if i - lv[1] <= SR_LEVEL_MAX_AGE_BARS]
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        tol = SR_TOL_ATR * atr[i]
        for price, created, kind in levels:
            if created >= i:
                continue
            if kind == 'R' and h[i] >= price - tol and c[i] < price:
                dirs[i] = -1
                break
            if kind == 'S' and l[i] <= price + tol and c[i] > price:
                dirs[i] = 1
                break
    return dirs


def signals_fvg_fill(o, h, l, c, n):
    dirs = [0] * n
    gaps = []   # (zone_lo, zone_hi, dir, created_at, used)
    for i in range(2, n):
        if h[i - 2] < l[i]:
            gaps.append([h[i - 2], l[i], 1, i, False])
        elif l[i - 2] > h[i]:
            gaps.append([h[i], l[i - 2], -1, i, False])

        for g in gaps:
            zlo, zhi, gdir, created, used = g
            if used or i <= created:
                continue
            touched = l[i] <= zhi and h[i] >= zlo
            if not touched:
                continue
            reject_ok = (gdir > 0 and c[i] >= zlo) or (gdir < 0 and c[i] <= zhi)
            if reject_ok:
                dirs[i] = gdir
                g[4] = True
    return dirs


def signals_order_block(o, h, l, c, n, pivot_highs, pivot_lows):
    dirs = [0] * n
    blocks = []   # (low, high, dir, created_at, used)
    last_piv_high = None
    last_piv_low = None
    ph_set = set(p + PIVOT_RIGHT for p in pivot_highs)
    pl_set = set(p + PIVOT_RIGHT for p in pivot_lows)
    ph_price = {p + PIVOT_RIGHT: h[p] for p in pivot_highs}
    pl_price = {p + PIVOT_RIGHT: l[p] for p in pivot_lows}

    for i in range(max(PIVOT_LEFT, 10) + 5, n):
        if i in ph_set:
            last_piv_high = ph_price[i]
        if i in pl_set:
            last_piv_low = pl_price[i]

        if last_piv_high is not None and c[i] > last_piv_high:
            ob = None
            for j in range(i - 1, max(i - 10, 0) - 1, -1):
                if c[j] < o[j]:
                    ob = j
                    break
            if ob is not None:
                blocks.append([l[ob], h[ob], 1, i, False])
            last_piv_high = None
        if last_piv_low is not None and c[i] < last_piv_low:
            ob = None
            for j in range(i - 1, max(i - 10, 0) - 1, -1):
                if c[j] > o[j]:
                    ob = j
                    break
            if ob is not None:
                blocks.append([l[ob], h[ob], -1, i, False])
            last_piv_low = None

        for b in blocks:
            blo, bhi, bdir, created, used = b
            if used or i <= created:
                continue
            touched = l[i] <= bhi and h[i] >= blo
            if touched:
                dirs[i] = bdir
                b[4] = True
    return dirs


def signals_fib_zone(o, h, l, c, n, pivot_highs, pivot_lows):
    dirs = [0] * n
    all_piv = sorted([(p + PIVOT_RIGHT, 'H', h[p]) for p in pivot_highs] +
                      [(p + PIVOT_RIGHT, 'L', l[p]) for p in pivot_lows])
    legs = []   # (zone_lo, zone_hi, dir, created_at, used)
    prev = None
    for idx, kind, price in all_piv:
        if prev is not None and prev[1] != kind:
            p_idx, p_kind, p_price = prev
            if kind == 'H' and p_kind == 'L':
                leg_lo, leg_hi = p_price, price
                zlo = leg_hi - FIB_HIGH * (leg_hi - leg_lo)
                zhi = leg_hi - FIB_LOW * (leg_hi - leg_lo)
                legs.append([zlo, zhi, 1, idx, False])
            elif kind == 'L' and p_kind == 'H':
                leg_hi, leg_lo = p_price, price
                zlo = leg_lo + FIB_LOW * (leg_hi - leg_lo)
                zhi = leg_lo + FIB_HIGH * (leg_hi - leg_lo)
                legs.append([zlo, zhi, -1, idx, False])
        prev = (idx, kind, price)

    for i in range(n):
        for lg in legs:
            zlo, zhi, ldir, created, used = lg
            if used or i <= created:
                continue
            touched = l[i] <= zhi and h[i] >= zlo
            if not touched:
                continue
            reject_ok = (ldir > 0 and c[i] >= zlo) or (ldir < 0 and c[i] <= zhi)
            if reject_ok:
                dirs[i] = ldir
                lg[4] = True
    return dirs


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
    o, h, l, c = df["open"].values, df["high"].values, df["low"].values, df["close"].values
    atr = wilder_atr(h, l, c, ATR_PERIOD)
    pivot_lows = find_pivots(l, PIVOT_LEFT, PIVOT_RIGHT, is_low=True)
    pivot_highs = find_pivots(h, PIVOT_LEFT, PIVOT_RIGHT, is_low=False)

    print(f"\n{'#'*100}\n{label} M15 - SMC-concepts batch test ({n} bars)\n{'#'*100}")

    dirs1 = signals_sr_bounce(o, h, l, c, atr, n, pivot_lows, pivot_highs)
    report(f"{label} M15 - SR_BOUNCE", build_trades(df, point, dirs1), full_days, split_dir=True)

    dirs2 = signals_fvg_fill(o, h, l, c, n)
    report(f"{label} M15 - FVG_FILL", build_trades(df, point, dirs2), full_days, split_dir=True)

    dirs3 = signals_order_block(o, h, l, c, n, pivot_highs, pivot_lows)
    report(f"{label} M15 - ORDER_BLOCK", build_trades(df, point, dirs3), full_days, split_dir=True)

    dirs4 = signals_fib_zone(o, h, l, c, n, pivot_highs, pivot_lows)
    report(f"{label} M15 - FIB_ZONE", build_trades(df, point, dirs4), full_days, split_dir=True)


if __name__ == "__main__":
    run_instrument("GOLD", "GOLD_M15_native.csv", trim_gold=True)
    run_instrument("SILVER", "SILVER_M15_native.csv", trim_gold=False)
    run_instrument("BTCUSD", "BTCUSD_M15_native.csv", trim_gold=False)
    print(f"\n\n  Honest K=4 per instrument this batch (SR/FVG/order-block/fib).")
