"""
User's direct question after seeing TradePanel_EA's new EMA21/50 crossover
overlay: "there is no way to determine if the 21 and 50 cross is going to
be a good move to the upside or downside, and not a small criss-cross start
of a sideways market?" - confirmed true (Opus audit of the EA code: zero
chop filtering, fires on every sign flip no matter how small).

This tests the two filters picked to add: (1) MINIMUM GAP - require
|EMA21-EMA50| to reach some ATR multiple before the entry counts as taken,
and (2) CONFIRMATION BARS - require N bars to pass after the cross with
price still on the new side before entry. Layered on top of the exact
validated base construction (ema21_50_pure_crossover_test.py, pure
crossover, hold-to-next-opposite-cross, GOLD M15, real-data window only).

Honest K: this is testing 2 filter TYPES x multiple threshold values each
(grid search) + their combination = effectively a parameter search, so
whatever wins here must still be reported as "best of K tried", with the
usual walk-forward check before calling it validated - not assumed safe
just because the parent construction (K=1, no filter) already passed.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from ema21_50_pure_crossover_test import load_m15, EMA_FAST, EMA_SLOW, GOLD_M15_REAL_START
from dual_stoch_cross_200ema_test import report
from vwap_open_scenarios_test import ema
from stoch_ma_stack_gap_filter_test import wilder_atr

SPLIT_DATE = pd.Timestamp("2021-01-01")   # same walk-forward split used for SR_BOUNCE


def build_trades_filtered(df, point, min_gap_atr=0.0, confirm_bars=0):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    e21 = ema(close_a, EMA_FAST)
    e50 = ema(close_a, EMA_SLOW)
    atr = wilder_atr(high_a, low_a, close_a, 14)

    close, spread = close_a.tolist(), spread_a.tolist()
    valid = [not (np.isnan(e21[i]) or np.isnan(e50[i]) or np.isnan(atr[i])) for i in range(n)]

    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = e21[i - 1] <= e50[i - 1] and e21[i] > e50[i]
            crossDown[i] = e21[i - 1] >= e50[i - 1] and e21[i] < e50[i]

    results = []
    start = EMA_SLOW + 5
    i = start
    posDir, open_fill_i, open_entry_px = 0, None, None
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 1 if crossUp[i] else (-1 if crossDown[i] else 0)

        # EXIT on next opposite cross - unaffected by entry filters (same as EA: exit is unconditional)
        if posDir != 0 and dir_ != 0 and dir_ != posDir:
            fill_i = i + 1
            if fill_i < n:
                sc = spread[fill_i] * point
                exit_px = close[fill_i] - (sc if posDir > 0 else -sc)
                pnl_pct = ((exit_px - open_entry_px) / open_entry_px) * posDir
                results.append(dict(entry_i=open_fill_i, exit_i=fill_i, pnl_pct=pnl_pct, dir=posDir,
                                     reason="EXIT-EMA-CROSS", hold_bars=fill_i - open_fill_i))
            posDir, open_fill_i, open_entry_px = 0, None, None

        if dir_ != 0 and posDir == 0:
            # --- CONFIRMATION BARS: require price still on the new side N bars later
            if confirm_bars > 0:
                chk = i + confirm_bars
                if chk >= n or not valid[chk]:
                    i += 1
                    continue
                still_ok = (close[chk] > e50[chk]) if dir_ > 0 else (close[chk] < e50[chk])
                if not still_ok:
                    i += 1
                    continue
                entry_bar = chk
            else:
                entry_bar = i

            # --- MIN GAP: require |e21-e50| at entry_bar to reach threshold
            if min_gap_atr > 0.0:
                gap = abs(e21[entry_bar] - e50[entry_bar])
                if gap < min_gap_atr * atr[entry_bar]:
                    i += 1
                    continue

            fill_i = entry_bar + 1
            if fill_i < n:
                sc = spread[fill_i] * point
                entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
                posDir, open_fill_i, open_entry_px = dir_, fill_i, entry_px

        i += 1

    return results


def run_window(label, df, point, min_gap_atr=0.0, confirm_bars=0):
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    trades = build_trades_filtered(df, point, min_gap_atr, confirm_bars)
    report(label, trades, full_days, split_dir=True)
    return trades


if __name__ == "__main__":
    df, point = load_m15("GOLD_M15_native.csv", trim_gold=True)
    print(f"GOLD M15 real-data window: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({len(df)} bars)\n")

    print("=" * 100)
    print("0. BASELINE - no filter (already validated K=1, for reference)")
    print("=" * 100)
    run_window("0. BASELINE (no filter)", df, point)
    print()

    print("=" * 100)
    print("1. MIN-GAP filter only (grid)")
    print("=" * 100)
    for g in (0.0, 0.1, 0.2, 0.3, 0.5, 0.75, 1.0):
        run_window(f"1. min_gap={g} ATR", df, point, min_gap_atr=g)
    print()

    print("=" * 100)
    print("2. CONFIRMATION BARS filter only (grid)")
    print("=" * 100)
    for cb in (0, 1, 2, 3, 5, 8):
        run_window(f"2. confirm_bars={cb}", df, point, confirm_bars=cb)
    print()

    print("=" * 100)
    print("3. COMBINED (best-looking single-filter values x each other, small grid)")
    print("=" * 100)
    for g in (0.2, 0.3, 0.5):
        for cb in (1, 2, 3):
            run_window(f"3. min_gap={g} ATR + confirm_bars={cb}", df, point, min_gap_atr=g, confirm_bars=cb)
    print()
    print(f"Honest K this file: 7 (min-gap grid) + 6 (confirm grid) + 9 (combo grid) = 22 configs")
    print(f"tried against the SAME GOLD M15 full-history window used for the already-reported baseline.")
