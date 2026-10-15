"""
New, specific construction per direct instruction: Stochastic(21,5,5) on
M15. Entry when the stochastic crosses UP out of oversold (%K crosses
above the oversold threshold, having been below it - confirms the
reversal is starting, not just "currently oversold"). Ride the full move
through to overbought - exit when %K reaches the overbought threshold, or
a long time cap as fallback. Mirrored for shorts (cross down out of
overbought, ride to oversold).

This is a genuinely different entry mechanism from everything else tested
tonight - no VWAP, no 200-EMA, no 21/50 cross at all. Tested fairly, same
rigor: real spread, real fills, IS/OOS split, Gold AND Silver together
from the start (per the hard lesson from H4-alignment/first-cross, where
Gold-only results looked good and then failed on Silver).

Honest K tracked independently, starting fresh for this file.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import ema, wilder_atr
from meridian_early_cross_test import load_m15

TIME_CAP_BARS = 200


def stochastic(high, low, close, k_period=21, k_slow=5, d_period=5):
    n = len(close)
    lowest = pd.Series(low).rolling(k_period, min_periods=k_period).min().values
    highest = pd.Series(high).rolling(k_period, min_periods=k_period).max().values
    raw_k = np.full(n, np.nan)
    rng = highest - lowest
    valid = rng > 0
    raw_k[valid] = 100.0 * (close[valid] - lowest[valid]) / rng[valid]
    k_smoothed = pd.Series(raw_k).rolling(k_slow, min_periods=k_slow).mean().values
    d = pd.Series(k_smoothed).rolling(d_period, min_periods=d_period).mean().values
    return k_smoothed, d


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results, n_days=None, split_dir=False):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    holds = np.array([r["hold_bars"] for r in results]) * 0.25
    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    rtxt = ", ".join(f"{k}:{v}" for k, v in reasons.items())
    pm = f"  (~{len(results)/(n_days/30.44):.1f}/mo)" if n_days else ""
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  %PF={pct_pf(results):6.3f}  "
          f"net%={100*arr.sum():7.2f}  avg_hold={holds.mean():5.1f}h  [{rtxt}]{pm}")
    if split_dir:
        longs = [r for r in results if r["dir"] > 0]
        shorts = [r for r in results if r["dir"] < 0]
        report("    -> LONGS only", longs, n_days)
        report("    -> SHORTS only", shorts, n_days)


def classify_stoch_swing(df, point, oversold, overbought, time_cap_bars=TIME_CAP_BARS):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    n = len(df)
    k, d = stochastic(high, low, close, 21, 5, 5)

    results = []
    i = 30
    while i < n - 1:
        if np.isnan(k[i]) or np.isnan(k[i - 1]):
            i += 1
            continue
        cross_up_oversold = k[i - 1] <= oversold and k[i] > oversold
        cross_down_overbought = k[i - 1] >= overbought and k[i] < overbought

        direction = 0
        if cross_up_oversold:
            direction = 1
        elif cross_down_overbought:
            direction = -1
        if direction == 0:
            i += 1
            continue

        fill_i = i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)
        hard_limit = min(fill_i + time_cap_bars, n - 1)

        exit_i, exit_px, reason = None, None, None
        for j in range(fill_i + 1, hard_limit + 1):
            if np.isnan(k[j]):
                continue
            if direction > 0 and k[j] >= overbought:
                exit_i, exit_px, reason = j, close[j], "OVERBOUGHT"
                break
            if direction < 0 and k[j] <= oversold:
                exit_i, exit_px, reason = j, close[j], "OVERSOLD"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
        i = exit_i + 1

    return results


def run_symbol(symbol):
    df, point = load_m15(symbol)
    n = len(df)
    print(f"\n{'#'*100}\n{symbol} M15 - Stochastic(21,5,5) oversold->overbought swing\n{'#'*100}")
    print(f"  {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars, point={point})")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    print(f"\n{'='*100}\nIN-SAMPLE grid (oversold/overbought thresholds)\n{'='*100}")
    grid = []
    for os_level, ob_level in ((15, 85), (20, 80), (25, 75), (30, 70)):
        res = classify_stoch_swing(df_is, point, os_level, ob_level)
        net = sum(r["pnl_pct"] for r in res) if res else -999
        grid.append((os_level, ob_level, len(res), net, pct_pf(res)))
        print(f"  oversold={os_level} overbought={ob_level}:  n={len(res):4d}  net%={100*net:7.2f}  "
              f"PF={pct_pf(res):5.2f}  ~{len(res)/(is_days/30.44):.1f}/mo", flush=True)

    best = max(grid, key=lambda g: g[3])
    print(f"\n  IS winner: oversold={best[0]} overbought={best[1]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation (pooled, then split long/short)\n{'='*100}")
    oos_res = classify_stoch_swing(df_oos, point, best[0], best[1])
    report(f"{symbol} - OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_stoch_swing(df, point, best[0], best[1])
    report(f"{symbol} - FULL", full_res, full_days, split_dir=True)
    return best, grid


if __name__ == "__main__":
    bestG, gridG = run_symbol("GOLD")
    bestS, gridS = run_symbol("SILVER")
    print(f"\n\n  Honest K note: GOLD searched {len(gridG)}, SILVER searched {len(gridS)}.")
    print(f"  New construction - tracked independently from everything else tonight.")
