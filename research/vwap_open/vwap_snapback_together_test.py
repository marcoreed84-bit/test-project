"""
Fourth construction - the one piece of the user's original description not
yet isolated as its own test: "...other times it pulls away slight then
comes back and both 21 and 50 cross the vwap and price goes in that
direction for hours."

This is NOT the same as vwap_ma_cross_test.py (single MA crossing VWAP after
a cluster). This requires a specific THREE-PHASE sequence, causally:
  1. Cluster near VWAP at session start (same precondition as before).
  2. Both 21-EMA and 50-EMA pull away from VWAP together, to the SAME side,
     beyond a divergence threshold ("pulls away").
  3. Both MAs then cross back through VWAP to the OTHER side, within
     `together_tol_bars` of each other ("comes back ... both cross the vwap
     ... together"). Entry direction = the direction of this snap-back
     (opposite of the original divergence), at the bar the SECOND of the two
     MAs confirms the cross (the "together" requirement - if only one MA has
     crossed, this is not the pattern).

Entry fills at close of the next bar after the second MA confirms, same
spread convention as the rest of this research line.

Exit: real-time rule, not a filter. Price closing back through the 50-EMA
(established earlier in this research line as the more stable trail/exit
reference between 21/50), or an 8-hour hard time limit, whichever comes
first - this gives a genuinely variable hold per trade, not a forced
duration, consistent with the user's clarification that trades should hold
as long as the move lasts, not a fixed window.

Same real GOLD_M15_native.csv (2014-06-13+ clean window), real spread,
IS/OOS split (70/30 by date), honest K tracking continued from this
research line's running total (34 before this file).
"""
import numpy as np
import pandas as pd
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, WINDOW_BARS, GOLD_POINT

HOLD_BARS_SNAPBACK = 32  # 8h on M15, longer cap since this pattern is described as running "for hours"


def classify_and_test_together(df, cluster_atr_mult, diverge_atr_mult, together_tol_bars,
                                resolve_window_bars, point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)

    day = df["time"].dt.date.values
    n = len(df)
    day_start_idx = {}
    for i in range(n):
        if day[i] not in day_start_idx:
            day_start_idx[day[i]] = i

    results = []
    for d, start_i in day_start_idx.items():
        end_i = min(start_i + WINDOW_BARS, n)
        if end_i - start_i < 10:
            continue

        # phase 1: cluster near VWAP
        cluster_i = None
        for i in range(start_i, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(vwap[i]) or np.isnan(m21[i]) or np.isnan(m50[i]):
                continue
            tol = cluster_atr_mult * atr[i]
            if (abs(close[i] - vwap[i]) <= tol and abs(m21[i] - vwap[i]) <= tol
                    and abs(m50[i] - vwap[i]) <= tol):
                cluster_i = i
                break
        if cluster_i is None:
            continue

        # phase 2+3 must both resolve within resolve_window_bars of the
        # cluster point - per user's observation that price picks a
        # direction within the first couple hours, not spread across the
        # whole early-morning window
        resolve_end = min(cluster_i + resolve_window_bars, end_i)

        # phase 2: both MAs diverge to the SAME side beyond threshold
        diverge_i, away_dir = None, None
        for i in range(cluster_i + 1, resolve_end):
            if np.isnan(atr[i]) or atr[i] <= 0:
                continue
            dv = diverge_atr_mult * atr[i]
            if m21[i] > vwap[i] + dv and m50[i] > vwap[i] + dv:
                diverge_i, away_dir = i, 1
                break
            if m21[i] < vwap[i] - dv and m50[i] < vwap[i] - dv:
                diverge_i, away_dir = i, -1
                break
        if diverge_i is None:
            continue

        # phase 3: both MAs cross back to the OTHER side, within tol bars of
        # each other. Track each MA's own first-crossback bar independently,
        # entry confirmed when the SECOND one crosses, provided that's within
        # together_tol_bars of the first.
        search_end = resolve_end
        m21_cross_i, m50_cross_i = None, None
        for i in range(diverge_i + 1, search_end):
            if m21_cross_i is None:
                if away_dir > 0 and m21[i] < vwap[i]:
                    m21_cross_i = i
                elif away_dir < 0 and m21[i] > vwap[i]:
                    m21_cross_i = i
            if m50_cross_i is None:
                if away_dir > 0 and m50[i] < vwap[i]:
                    m50_cross_i = i
                elif away_dir < 0 and m50[i] > vwap[i]:
                    m50_cross_i = i
            if m21_cross_i is not None and m50_cross_i is not None:
                break

        if m21_cross_i is None or m50_cross_i is None:
            continue
        if abs(m21_cross_i - m50_cross_i) > together_tol_bars:
            continue

        resolve_i = max(m21_cross_i, m50_cross_i)
        direction = -away_dir  # snap-back direction, opposite of original divergence

        fill_i = resolve_i + 1
        if fill_i >= n:
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)

        exit_i, exit_px, reason = None, None, None
        hard_limit = min(fill_i + HOLD_BARS_SNAPBACK, n - 1)
        for j in range(fill_i, hard_limit + 1):
            if np.isnan(m50[j]):
                continue
            broke = (close[j] < m50[j]) if direction > 0 else (close[j] > m50[j])
            if broke:
                exit_i, exit_px, reason = j, close[j], "EMA50"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        hold_bars = exit_i - fill_i
        results.append(dict(day=d, entry_i=resolve_i, exit_i=exit_i, pnl_pct=pnl_pct,
                             dir=direction, reason=reason, hold_bars=hold_bars))

    return results


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    holds = np.array([r["hold_bars"] for r in results]) * 0.25  # M15 bars -> hours
    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    rtxt = ", ".join(f"{k}:{v}" for k, v in reasons.items())
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  "
          f"%PF={pct_pf(results):6.3f}  net%={100*arr.sum():7.2f}  avg%={100*arr.mean():6.3f}  "
          f"avg_hold={holds.mean():5.1f}h  [{rtxt}]")


if __name__ == "__main__":
    df = load_gold_m15()
    n = len(df)
    print(f"GOLD M15 real: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)\n")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)

    print(f"{'='*100}\nIN-SAMPLE grid search (both MAs snap back and cross VWAP together,")
    print(f"resolving within the first couple hours after the cluster point)\n{'='*100}")
    grid = []
    for resolve_bars in (8, 12):  # 2h, 3h after cluster point
        for cluster_m in (0.3, 0.5):
            for diverge_m in (0.4, 0.6, 0.8):
                for tol_bars in (2, 4, 6):
                    res = classify_and_test_together(df_is, cluster_m, diverge_m, tol_bars, resolve_bars)
                    net = sum(r["pnl_pct"] for r in res) if res else -999
                    grid.append((cluster_m, diverge_m, tol_bars, resolve_bars, len(res), net, pct_pf(res)))
                    print(f"  resolve<={resolve_bars*0.25:.1f}h cluster={cluster_m} diverge={diverge_m} tol={tol_bars}:  "
                          f"n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}")

    best = max(grid, key=lambda g: g[5])
    print(f"\n  IS winner: cluster={best[0]} diverge={best[1]} tol={best[2]} resolve<={best[3]*0.25:.1f}h"
          f"   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_and_test_together(df_oos, best[0], best[1], best[2], best[3])
    report("Snap-back-together - OOS", oos_res)
    full_res = classify_and_test_together(df, best[0], best[1], best[2], best[3])
    report("Snap-back-together - FULL", full_res)

    print(f"\n\n  Honest K note: 2 x 2 x 3 x 3 = 36 combinations searched in this file.")
    print(f"  Combined with the 34 already searched earlier in this VWAP-open research")
    print(f"  line, the running total is K=70 if any of these numbers end up reported as a result.")
