"""
New construction per uploaded PDF (pulses_jun2007.pdf, "Trading
Strategies Using Stochastic"): classic bullish/bearish DIVERGENCE
between price and the stochastic oscillator - a genuinely different
signal mechanism from every cross-based construction tested tonight.

Bearish divergence (SELL): price makes a HIGHER swing high while the
stochastic makes a LOWER value at that second high (momentum failing
to confirm the new price high) - the article specifies this is most
meaningful when it occurs in overbought territory (>70).
Bullish divergence (BUY): the mirror - price makes a LOWER swing low
while stochastic makes a HIGHER value there, in oversold territory (<30).

Swing detection: a bar is a confirmed swing high/low once PIVOT_W
bars have closed on both sides of it with no higher high / lower low
in that window (standard, causal - a pivot is only knowable PIVOT_W
bars after it happened, which is exactly when this strategy acts on
it, not before).

Single Stochastic(21,5,5), Close/Close+Smoothed, same convention as
every other test tonight. Stop/target: unchanged MA/VWAP stop +
1.0xATR target (nearest_protective_stop, TARGET_ATR from
single_stoch_21_5_5_test.py) - isolates the entry mechanism, not a
different risk framework.

Tested Gold + Silver M15, full rigor. Honest K: 1 per symbol (one
fixed construction, pivot width and divergence threshold taken
directly from the source article's own description, not swept).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from dual_stoch_cross_200ema_test import stoch_close_smoothed, load_m15, report, TIME_CAP_BARS
from vwap_open_scenarios_test import wilder_atr
from single_stoch_21_5_5_test import nearest_protective_stop, TARGET_ATR

PIVOT_W = 5
OB_THRESHOLD = 70.0   # divergence only counted in overbought/oversold territory, per the article
OS_THRESHOLD = 30.0


def find_swings(high, low, w):
    n = len(high)
    swing_high = np.zeros(n, dtype=bool)
    swing_low = np.zeros(n, dtype=bool)
    for i in range(w, n - w):
        window_h = high[i - w:i + w + 1]
        window_l = low[i - w:i + w + 1]
        if high[i] == window_h.max() and np.argmax(window_h) == w:
            swing_high[i] = True
        if low[i] == window_l.min() and np.argmin(window_l) == w:
            swing_low[i] = True
    return swing_high, swing_low


def build_trades(df, point, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    atr = wilder_atr(high, low, close, 14)
    k, _ = stoch_close_smoothed(close, 21, 5, 5)
    swing_high, swing_low = find_swings(high, low, PIVOT_W)

    results = []
    last_high_pivot = None   # (price, stoch_value) of the most recent confirmed swing high
    last_low_pivot = None
    i = 210
    while i < n - 1:
        confirm_i = i - PIVOT_W   # the pivot bar being confirmed THIS bar (i), if any
        if confirm_i >= 0:
            if swing_high[confirm_i] and not np.isnan(k[confirm_i]):
                last_high_pivot_new = (high[confirm_i], k[confirm_i])
                if last_high_pivot is not None:
                    prev_px, prev_k = last_high_pivot
                    cur_px, cur_k = last_high_pivot_new
                    if cur_px > prev_px and cur_k < prev_k and cur_k >= OB_THRESHOLD and not np.isnan(atr[i]) and atr[i] > 0:
                        # bearish divergence confirmed - trade SELL
                        direction = -1
                        fill_i = i + 1
                        if fill_i < n:
                            sc = spread[fill_i] * point
                            entry_px = close[fill_i] - sc
                            hard_limit = min(fill_i + time_cap_bars, n - 1)
                            stop_px = entry_px + 1.5 * atr[i]   # flat ATR stop - no MA reference needed for this entry type
                            target_px = entry_px - TARGET_ATR * atr[i]
                            exit_i, exit_px, reason = None, None, None
                            for j in range(fill_i + 1, hard_limit + 1):
                                if high[j] >= stop_px:
                                    exit_i, exit_px, reason = j, stop_px, "STOP"
                                    break
                                if low[j] <= target_px:
                                    exit_i, exit_px, reason = j, target_px, "TARGET"
                                    break
                            if exit_i is None:
                                exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
                            pnl_pct = ((exit_px - entry_px) / entry_px) * direction
                            results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                                                 reason=reason, hold_bars=exit_i - fill_i))
                last_high_pivot = last_high_pivot_new
            if swing_low[confirm_i] and not np.isnan(k[confirm_i]):
                last_low_pivot_new = (low[confirm_i], k[confirm_i])
                if last_low_pivot is not None:
                    prev_px, prev_k = last_low_pivot
                    cur_px, cur_k = last_low_pivot_new
                    if cur_px < prev_px and cur_k > prev_k and cur_k <= OS_THRESHOLD and not np.isnan(atr[i]) and atr[i] > 0:
                        direction = 1
                        fill_i = i + 1
                        if fill_i < n:
                            sc = spread[fill_i] * point
                            entry_px = close[fill_i] + sc
                            hard_limit = min(fill_i + time_cap_bars, n - 1)
                            stop_px = entry_px - 1.5 * atr[i]
                            target_px = entry_px + TARGET_ATR * atr[i]
                            exit_i, exit_px, reason = None, None, None
                            for j in range(fill_i + 1, hard_limit + 1):
                                if low[j] <= stop_px:
                                    exit_i, exit_px, reason = j, stop_px, "STOP"
                                    break
                                if high[j] >= target_px:
                                    exit_i, exit_px, reason = j, target_px, "TARGET"
                                    break
                            if exit_i is None:
                                exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
                            pnl_pct = ((exit_px - entry_px) / entry_px) * direction
                            results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                                                 reason=reason, hold_bars=exit_i - fill_i))
                last_low_pivot = last_low_pivot_new
        i += 1

    results.sort(key=lambda r: r["entry_i"])
    return results


def run_symbol(symbol):
    df, point = load_m15(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} M15 - price/stochastic divergence (pivot width={PIVOT_W}), flat 1.5xATR stop, 1.0xATR target\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    is_res = build_trades(df_is, point)
    report(f"{symbol} M15 - IN-SAMPLE", is_res, is_days, split_dir=True)
    oos_res = build_trades(df_oos, point)
    report(f"{symbol} M15 - OUT-OF-SAMPLE", oos_res, oos_days, split_dir=True)
    full_res = build_trades(df, point)
    report(f"{symbol} M15 - FULL HISTORY", full_res, full_days, split_dir=True)
    return full_res


if __name__ == "__main__":
    run_symbol("GOLD")
    run_symbol("SILVER")
    print(f"\n\n  Honest K: 1 per symbol (divergence construction per the source article, not swept).")
