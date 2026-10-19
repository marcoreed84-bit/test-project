"""
Follow-up to ema21_50_gap_confirm_filter_test.py (confirm_bars=2 already
implemented in the EA, min-gap rejected). User's next 3 ideas, tested the
same way - layered on top of the SAME validated base construction (pure
EMA21/50 crossover, hold-to-next-opposite-cross, confirm_bars=2 baked in
since that's now the real EA behavior):

1. ANGLE/STEEPNESS of the crossing MA (EMA21) over the last N bars,
   ATR-normalized - "the momentum at which they cross".
2. PRE-CROSS CONVERGENCE - "if they are running parallel together before
   they actually cross" - require the gap to have been NARROWING/flat
   (not already wide and snapping) for N bars before the cross, as a
   proxy for "slow drift-together" vs "sharp snap crossing" - tested both
   directions since it's genuinely unclear which one indicates a real
   trend start.
3. DISTANCE TO 200EMA/VWAP at the cross - require the cross to happen
   away from (not resting on top of) the 200EMA or VWAP, since a cross
   sitting right on a major level is more likely to be deflected/chopped.

Honest K: 3 filter families x several threshold values each, all on the
SAME GOLD M15 full-history window already used for the confirm_bars test.
Running K total for this EMA-cross overlay's filter search is now
22 (prior file) + however many configs below.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from ema21_50_pure_crossover_test import load_m15, EMA_FAST, EMA_SLOW
from dual_stoch_cross_200ema_test import report
from vwap_open_scenarios_test import ema
from stoch_ma_stack_gap_filter_test import wilder_atr

CONFIRM_BARS = 2   # now the EA's real default - base every variant on this, not confirm_bars=0


def build_trades(df, point, confirm_bars=CONFIRM_BARS, gate=None):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    e21 = ema(close_a, EMA_FAST)
    e50 = ema(close_a, EMA_SLOW)
    e200 = ema(close_a, 200)
    atr = wilder_atr(high_a, low_a, close_a, 14)

    close, spread = close_a.tolist(), spread_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(atr[i]) or np.isnan(e200[i])) for i in range(n)]

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
            crossDown[i] = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]

    results = []
    start = EMA_SLOW + 210
    i = start
    posDir, open_fill_i, open_entry_px = 0, None, None
    pendingDir, pendingElapsed, pendingCrossBar = 0, 0, None
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 1 if crossUp[i] else (-1 if crossDown[i] else 0)

        if posDir != 0 and dir_ != 0 and dir_ != posDir:
            fill_i = i + 1
            if fill_i < n:
                sc = spread[fill_i] * point
                exit_px = close[fill_i] - (sc if posDir > 0 else -sc)
                pnl_pct = ((exit_px - open_entry_px) / open_entry_px) * posDir
                results.append(dict(entry_i=open_fill_i, exit_i=fill_i, pnl_pct=pnl_pct, dir=posDir,
                                     reason="EXIT-EMA-CROSS", hold_bars=fill_i - open_fill_i))
            posDir, open_fill_i, open_entry_px = 0, None, None

        entry_dir = 0
        entry_cross_bar = None
        if posDir == 0:
            if pendingDir != 0:
                pendingElapsed += 1
                if pendingElapsed >= confirm_bars:
                    still_ok = (close[i] > e50[i]) if pendingDir > 0 else (close[i] < e50[i])
                    if still_ok:
                        entry_dir = pendingDir
                        entry_cross_bar = pendingCrossBar
                    pendingDir, pendingElapsed = 0, 0
            if dir_ != 0:
                pendingDir, pendingElapsed, pendingCrossBar = dir_, 0, i

        if entry_dir != 0 and posDir == 0:
            is_buy = entry_dir > 0
            if gate is None or gate(entry_cross_bar, is_buy):
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    entry_px = close[fill_i] + (sc if is_buy else -sc)
                    posDir, open_fill_i, open_entry_px = entry_dir, fill_i, entry_px

        i += 1

    return results, e21, e50, e200, atr


def run(label, df, point, gate=None):
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    trades, _, _, _, _ = build_trades(df, point, gate=gate)
    report(label, trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    df, point = load_m15("GOLD_M15_native.csv", trim_gold=True)
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    n = len(df)
    e21 = ema(close_a, EMA_FAST)
    e50 = ema(close_a, EMA_SLOW)
    e200 = ema(close_a, 200)
    atr = wilder_atr(high_a, low_a, close_a, 14)
    print(f"GOLD M15 real-data window: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")

    print("=" * 100)
    print("0. BASELINE - confirm_bars=2, no extra gate (current EA v2.01 behavior)")
    print("=" * 100)
    run("0. BASELINE (confirm_bars=2 only)", df, point)
    print()

    # 1. ANGLE/STEEPNESS: EMA21 slope over last 10 bars, ATR-normalized, at the CROSS bar
    slope21 = np.full(n, np.nan)
    slope21[10:] = (e21[10:] - e21[:-10]) / np.where(atr[10:] > 0, atr[10:], np.nan)

    print("=" * 100)
    print("1. ANGLE/STEEPNESS filter (EMA21 slope over 10 bars, ATR-normalized, at cross bar)")
    print("=" * 100)
    for ms in (0.1, 0.2, 0.3, 0.5):
        def gate_angle(cross_bar, is_buy, ms=ms):
            s = slope21[cross_bar]
            if np.isnan(s):
                return False
            return (s >= ms) if is_buy else (s <= -ms)
        run(f"1. min |slope|>={ms} ATR/10bars", df, point, gate=gate_angle)
    print()

    # 2. PRE-CROSS CONVERGENCE: gap behavior over the N bars BEFORE the cross
    gap = e21 - e50
    print("=" * 100)
    print("2a. PRE-CROSS NARROWING (gap was shrinking into the cross - 'slow drift together')")
    print("=" * 100)
    for lb in (5, 10, 20):
        def gate_narrowing(cross_bar, is_buy, lb=lb):
            if cross_bar - lb < 0:
                return False
            g_now = abs(gap[cross_bar - 1])
            g_before = abs(gap[cross_bar - 1 - lb])
            return g_now < g_before   # gap shrank over the lookback, right up to the cross
        run(f"2a. narrowing over last {lb} bars", df, point, gate=gate_narrowing)
    print()

    print("=" * 100)
    print("2b. SHARP SNAP (gap was WIDE and flipped quickly - opposite hypothesis)")
    print("=" * 100)
    for lb in (5, 10, 20):
        def gate_snap(cross_bar, is_buy, lb=lb):
            if cross_bar - lb < 0 or np.isnan(atr[cross_bar]) or atr[cross_bar] <= 0:
                return False
            g_before = abs(gap[cross_bar - lb])
            return g_before >= 0.3 * atr[cross_bar]   # was already a decent gap just before flipping
        run(f"2b. prior gap>=0.3 ATR, {lb} bars before cross", df, point, gate=gate_snap)
    print()

    # 3. DISTANCE TO 200EMA at the cross (VWAP omitted - no persistent VWAP series in this
    # offline dataset the way the EA computes session VWAP live; 200EMA is the available proxy)
    print("=" * 100)
    print("3. DISTANCE TO 200EMA filter (cross must be N x ATR away from EMA200)")
    print("=" * 100)
    for mult in (0.5, 1.0, 1.5, 2.0):
        def gate_dist200(cross_bar, is_buy, mult=mult):
            if np.isnan(atr[cross_bar]) or atr[cross_bar] <= 0:
                return False
            dist = abs(close_a[cross_bar] - e200[cross_bar])
            return dist >= mult * atr[cross_bar]
        run(f"3. dist(close,EMA200)>={mult} ATR", df, point, gate=gate_dist200)
    print()

    print("Honest K this file: 4 (angle) + 3 (narrowing) + 3 (snap) + 4 (dist200) = 14 configs,")
    print("on top of the 22 already tried in ema21_50_gap_confirm_filter_test.py (running total 36).")
