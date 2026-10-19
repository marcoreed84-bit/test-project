"""
User's specific pattern, not yet tested: "in a down trend price riding the
21ema, and making a higher low, before the crossing of the moving averages
to go up" - i.e. BEFORE a bullish cross, look for price hugging EMA21 from
below/near it (not diving away) while making a HIGHER LOW than its prior
swing low. Mirror for bearish crosses: price riding EMA21 from above,
making a LOWER HIGH, before the cross down. This is a pre-cross structure
check, distinct from every filter already tried (gap size, confirm-bars,
angle, pre-cross narrowing/snap, distance-to-200EMA, BB-mid, 200EMA
rejection).

Pivot detection reused from rsi_divergence_entry_test.find_pivots (same
left/right-bar swing-pivot method used throughout this project).

"Riding the EMA21" operationalized as: the two most recent pivot lows (for
a bullish setup) both sit within RIDE_ATR x ATR of EMA21 at their own bar -
i.e. price pulled back to the 21ema, not far past it, each time.
"Higher low" = second pivot low's price > first pivot low's price.

Tested on the RECENT window only, per direct request to stop re-running
the 2014-2020 history - 2025-01-01 onward (631 days) and 2026 YTD alone,
both already used for the rejection-filter re-test. Base construction
unchanged: pure EMA21/50 crossover, hold-to-next-opposite-cross,
confirm_bars=2 (EA's current default).

Honest K: this file's own grid, on top of the running total from this
overlay's filter search (55 configs before this file, all on different
constructions than this one - this is a genuinely new idea, not a
variant of something already tried).
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
from rsi_divergence_entry_test import find_pivots

CONFIRM_BARS = 2


def build_trades(df, point, confirm_bars=CONFIRM_BARS, gate=None):
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
    start = EMA_SLOW + 90
    i = start
    posDir, open_fill_i, open_entry_px = 0, None, None
    pendingDir, pendingElapsed = 0, 0
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

        entry_dir, entry_bar = 0, None
        if posDir == 0:
            if pendingDir != 0:
                pendingElapsed += 1
                if pendingElapsed >= confirm_bars:
                    still_ok = (close[i] > e50[i]) if pendingDir > 0 else (close[i] < e50[i])
                    if still_ok:
                        entry_dir, entry_bar = pendingDir, i
                    pendingDir, pendingElapsed = 0, 0
            if dir_ != 0:
                pendingDir, pendingElapsed = dir_, 0

        if entry_dir != 0 and posDir == 0:
            is_buy = entry_dir > 0
            if gate is None or gate(entry_bar, is_buy):
                fill_i = i + 1
                if fill_i < n:
                    sc = spread[fill_i] * point
                    entry_px = close[fill_i] + (sc if is_buy else -sc)
                    posDir, open_fill_i, open_entry_px = entry_dir, fill_i, entry_px

        i += 1

    return results


def run(label, df, point, gate=None):
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days
    trades = build_trades(df, point, gate=gate)
    report(label, trades, full_days, split_dir=True)
    return trades


def make_riding_higher_low_gate(high_a, low_a, atr, pivot_lows, pivot_highs, lookback, ride_atr):
    """Returns gate(cross_bar, is_buy) -> bool.
    BUY: last two pivot LOWS before cross_bar are both within ride_atr*ATR of... wait, needs e21 too.
    """
    pass  # placeholder, real version built inline below (needs e21 closure)


if __name__ == "__main__":
    df_full, point = load_m15("GOLD_M15_native.csv", trim_gold=True)
    print(f"Full data ends: {df_full['time'].iloc[-1]}\n")

    for start in (pd.Timestamp("2025-01-01"), pd.Timestamp("2026-01-01")):
        d = df_full[df_full["time"] >= start].reset_index(drop=True)
        close_a, high_a, low_a = d["close"].values, d["high"].values, d["low"].values
        n = len(d)
        e21 = ema(close_a, EMA_FAST)
        atr = wilder_atr(high_a, low_a, close_a, 14)
        pivot_lows_mask = find_pivots(low_a, 3, 3, is_low=True)
        pivot_highs_mask = find_pivots(high_a, 3, 3, is_low=False)
        pivot_low_idx = np.where(pivot_lows_mask)[0]
        pivot_high_idx = np.where(pivot_highs_mask)[0]
        full_days = (d["time"].iloc[-1] - d["time"].iloc[0]).days

        print(f"\n{'#'*100}\nwindow start {start.date()}  ({n} bars, {full_days} days)\n{'#'*100}")
        run("BASELINE confirm_bars=2", d, point)

        for lookback in (60, 100, 150):
            for ride_atr in (0.5, 1.0, 1.5):
                def gate_riding(cross_bar, is_buy, lookback=lookback, ride_atr=ride_atr):
                    if is_buy:
                        cand = pivot_low_idx[(pivot_low_idx < cross_bar) & (pivot_low_idx >= cross_bar - lookback)]
                        if len(cand) < 2:
                            return False
                        p1, p2 = cand[-2], cand[-1]
                        higher_low = low_a[p2] > low_a[p1]
                        if not higher_low:
                            return False
                        for p in (p1, p2):
                            if np.isnan(atr[p]) or atr[p] <= 0:
                                return False
                            if abs(low_a[p] - e21[p]) > ride_atr * atr[p]:
                                return False
                        return True
                    else:
                        cand = pivot_high_idx[(pivot_high_idx < cross_bar) & (pivot_high_idx >= cross_bar - lookback)]
                        if len(cand) < 2:
                            return False
                        p1, p2 = cand[-2], cand[-1]
                        lower_high = high_a[p2] < high_a[p1]
                        if not lower_high:
                            return False
                        for p in (p1, p2):
                            if np.isnan(atr[p]) or atr[p] <= 0:
                                return False
                            if abs(high_a[p] - e21[p]) > ride_atr * atr[p]:
                                return False
                        return True
                run(f"riding+higher/lower-low lb={lookback} ride={ride_atr} ATR", d, point, gate=gate_riding)
            print()

    print("Honest K this file: 2 windows x 9 configs each = 18 configs (new construction, not a")
    print("variant of anything tried before). Any survivor still needs a genuine out-of-sample check")
    print("before it goes near the EA - everything else tested tonight that looked good on one window")
    print("either failed walk-forward or just didn't replicate.")
