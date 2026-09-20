"""
Three indicators the user asked to be tested against Aurelius's real M5
gold data, as a "step away from moving averages" idea (forwarded from a
message that predates the data-loss incident): Supertrend, Parabolic SAR,
and Volume Profile / Point of Control.

Real-data caveat (checked directly against GOLD_M5.csv before writing this):
`real_volume` is 100% zero for the whole 2023-2026 GOLD dataset - only
`tick_volume` (quote count, not traded size) is populated. volume_poc()
below is therefore a TICK-COUNT proxy for volume profile, not a genuine
traded-size profile - flagged again at every call site that uses it.
"""
import numpy as np
import pandas as pd


def supertrend(high, low, close, atr, period_unused, mult):
    """Standard Supertrend. Uses the SAME Wilder ATR array Aurelius's own
    engine already computes (engine.wilder_atr), not a re-derived one, so
    `period_unused` is accepted only for interface symmetry with a caller
    that might want to label runs by (period, mult) - the ATR passed in
    already reflects whatever period the caller built it with.

    Returns (trend, line): trend[i] in {+1,-1} (nan until warm), line[i]
    the active stop level (the "barrier" - lower band while trend=+1,
    upper band while trend=-1).
    """
    n = len(close)
    hl2 = (high + low) / 2.0
    basic_ub = hl2 + mult * atr
    basic_lb = hl2 - mult * atr

    final_ub = np.full(n, np.nan)
    final_lb = np.full(n, np.nan)
    trend = np.full(n, np.nan)
    line = np.full(n, np.nan)

    start = np.argmax(~np.isnan(atr))  # first bar with a real ATR reading
    final_ub[start] = basic_ub[start]
    final_lb[start] = basic_lb[start]
    trend[start] = 1.0
    line[start] = final_lb[start]

    for i in range(start + 1, n):
        if np.isnan(atr[i]):
            continue
        final_ub[i] = basic_ub[i] if (basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]) else final_ub[i - 1]
        final_lb[i] = basic_lb[i] if (basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]) else final_lb[i - 1]

        prev_t = trend[i - 1]
        if prev_t == 1.0:
            trend[i] = -1.0 if close[i] < final_lb[i] else 1.0
        else:
            trend[i] = 1.0 if close[i] > final_ub[i] else -1.0

        line[i] = final_lb[i] if trend[i] == 1.0 else final_ub[i]

    return trend, line


def parabolic_sar(high, low, close, step=0.02, max_step=0.2):
    """Standard Wilder PSAR. Returns (trend, sar): trend[i] in {+1,-1}
    (nan until warm), sar[i] the dot price."""
    n = len(close)
    trend = np.full(n, np.nan)
    sar = np.full(n, np.nan)
    if n < 2:
        return trend, sar

    up = close[1] >= close[0]
    trend[1] = 1.0 if up else -1.0
    ep = high[0] if up else low[0]
    af = step
    sar[1] = low[0] if up else high[0]

    for i in range(2, n):
        prev_sar = sar[i - 1]
        prev_trend = trend[i - 1]
        cand = prev_sar + af * (ep - prev_sar)

        if prev_trend == 1.0:
            cand = min(cand, low[i - 1], low[i - 2])
            if low[i] < cand:
                trend[i] = -1.0
                sar[i] = ep
                ep = low[i]
                af = step
            else:
                trend[i] = 1.0
                sar[i] = cand
                if high[i] > ep:
                    ep = high[i]
                    af = min(af + step, max_step)
        else:
            cand = max(cand, high[i - 1], high[i - 2])
            if high[i] > cand:
                trend[i] = 1.0
                sar[i] = ep
                ep = high[i]
                af = step
            else:
                trend[i] = -1.0
                sar[i] = cand
                if low[i] < ep:
                    ep = low[i]
                    af = min(af + step, max_step)

    return trend, sar


def volume_poc(high, low, close, tick_volume, window_bars, refresh_bars, nbins=40):
    """TICK-COUNT proxy volume profile (see module docstring - real_volume
    is unavailable for GOLD in this dataset). One representative price per
    bar (typical price = (H+L+C)/3), weighted by that bar's tick_volume,
    binned into `nbins` bins spanning the window's own [min low, max high].
    POC = bin-center of the max-weight bin. Recomputed every `refresh_bars`
    bars and held constant in between (this is a regime/structure level,
    not something that needs bar-by-bar precision) - keeps this O(n/refresh
    * window) instead of O(n * window).

    Returns poc array (nan until the first full window)."""
    n = len(close)
    typical = (high + low + close) / 3.0
    poc = np.full(n, np.nan)

    last_poc = np.nan
    for i in range(window_bars, n):
        if (i - window_bars) % refresh_bars == 0 or np.isnan(last_poc):
            lo_i = i - window_bars
            tp_win = typical[lo_i:i]
            vw = tick_volume[lo_i:i]
            lo_edge, hi_edge = tp_win.min(), tp_win.max()
            if hi_edge > lo_edge:
                hist, edges = np.histogram(tp_win, bins=nbins, range=(lo_edge, hi_edge), weights=vw)
                b = int(np.argmax(hist))
                last_poc = (edges[b] + edges[b + 1]) / 2.0
        poc[i] = last_poc

    return poc
