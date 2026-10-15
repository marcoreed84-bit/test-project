"""
Precise construction from a hand-drawn chart annotation: price crosses
BELOW VWAP first (a dip/shakeout), then closes back ABOVE VWAP (the
reclaim) - THAT close is the long entry trigger, not a break away from
VWAP (already tested and failed earlier tonight) and not the 21/50 cross
itself (also already tested). Buy-only, matching the picture.

Sequence, causal:
  1. Find a bar where close crosses from above-or-at VWAP to below VWAP
     (the dip below).
  2. Within reclaim_window bars after that, find the first bar where close
     crosses back above VWAP (the reclaim) - THIS is the entry trigger.
  3. Optional filter (tested both ways): require the 21/50 EMA to be
     reasonably close together at the dip bar (a "clustered" structure,
     same idea used earlier tonight) rather than firing on every random
     VWAP dip-and-reclaim regardless of MA structure.

Entry fills next bar after the reclaim close. Exit: ATR trailing stop,
same convention as meridian_cross_pullback_test.py - rides the leg until
it loses momentum, ratchets in favor only, long time cap as fallback.

Same real GOLD_M15_native.csv, real spread, IS/OOS split. New, separate
construction - honest K tracked independently from both the VWAP-open line
(K=228) and meridian_cross_pullback_test.py (K=23).
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, GOLD_POINT

TIME_CAP_BARS = 200


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results, n_days=None):
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


def _run_trailing_exit(close, low, atr, fill_i, entry_px, trail_atr_mult, n):
    hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
    highest_close = entry_px
    exit_i, exit_px, reason = None, None, None
    for k in range(fill_i, hard_limit + 1):
        if np.isnan(atr[k]) or atr[k] <= 0:
            continue
        if close[k] > highest_close:
            highest_close = close[k]
        trail = highest_close - trail_atr_mult * atr[k]
        if low[k] <= trail and k > fill_i:
            exit_i, exit_px, reason = k, trail, "TRAIL"
            break
    if exit_i is None:
        exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
    return exit_i, exit_px, reason


def classify_reclaim(df, reclaim_window, require_cluster, cluster_atr_mult, trail_atr_mult, point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)
    n = len(df)

    results = []
    i = 60
    while i < n - 1:
        if np.isnan(vwap[i]) or np.isnan(vwap[i - 1]) or np.isnan(atr[i]) or atr[i] <= 0:
            i += 1
            continue
        dipped_below = close[i - 1] >= vwap[i - 1] and close[i] < vwap[i]
        if dipped_below:
            if require_cluster:
                if np.isnan(m21[i]) or np.isnan(m50[i]):
                    i += 1
                    continue
                tol = cluster_atr_mult * atr[i]
                clustered = abs(m21[i] - vwap[i]) <= tol and abs(m50[i] - vwap[i]) <= tol
                if not clustered:
                    i += 1
                    continue

            resolve_i = None
            for j in range(i + 1, min(i + reclaim_window + 1, n)):
                if np.isnan(vwap[j]):
                    continue
                if close[j] > vwap[j]:
                    resolve_i = j
                    break
            if resolve_i is not None:
                fill_i = resolve_i + 1
                if fill_i < n and not np.isnan(atr[fill_i]) and atr[fill_i] > 0:
                    sc = spread[fill_i] * point
                    entry_px = close[fill_i] + sc
                    exit_i, exit_px, reason = _run_trailing_exit(close, low, atr, fill_i, entry_px,
                                                                   trail_atr_mult, n)
                    pnl_pct = (exit_px - entry_px) / entry_px
                    results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, reason=reason,
                                         hold_bars=exit_i - fill_i))
                    i = exit_i + 1
                    continue
        i += 1
    return results


if __name__ == "__main__":
    df = load_gold_m15()
    n = len(df)
    print(f"GOLD M15 real: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)
    is_days = (df_is["time"].iloc[-1] - df_is["time"].iloc[0]).days
    oos_days = (df_oos["time"].iloc[-1] - df_oos["time"].iloc[0]).days
    full_days = (df["time"].iloc[-1] - df["time"].iloc[0]).days

    print(f"{'='*100}\nIN-SAMPLE grid: VWAP dip-and-reclaim, buy only (with/without 21-50 cluster filter)\n{'='*100}")
    grid = []
    for require_cluster in (False, True):
        for reclaim_w in (4, 8, 16):
            for cluster_m in ((0.5,) if require_cluster else (None,)):
                for trail_m in (1.5, 2.0, 2.5, 3.0):
                    res = classify_reclaim(df_is, reclaim_w, require_cluster, cluster_m or 0.5, trail_m)
                    net = sum(r["pnl_pct"] for r in res) if res else -999
                    grid.append((require_cluster, reclaim_w, cluster_m, trail_m, len(res), net, pct_pf(res)))
                    print(f"  cluster_filter={require_cluster} reclaim_w={reclaim_w} trail={trail_m}:  "
                          f"n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  "
                          f"~{len(res)/(is_days/30.44):.1f}/mo", flush=True)

    best = max(grid, key=lambda g: g[5])
    print(f"\n  IS winner: cluster_filter={best[0]} reclaim_w={best[1]} trail={best[3]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_reclaim(df_oos, best[1], best[0], best[2] or 0.5, best[3])
    report("VWAP reclaim - OOS", oos_res, oos_days)
    full_res = classify_reclaim(df, best[1], best[0], best[2] or 0.5, best[3])
    report("VWAP reclaim - FULL", full_res, full_days)

    print(f"\n\n  Honest K note: {len(grid)} combinations searched in this file. New, separate")
    print(f"  construction from tonight's other research lines - tracked independently.")
