"""
Fifth construction. Explicit pivot per direct feedback: forget rare,
multi-condition "everything together" patterns - looking for something that
fires a handful of times a month, not once a year. New ingredient never
tested in this research line: the 200-EMA, specifically its relationship to
price/VWAP/the 21-50 EMA cluster AT SESSION OPEN (when VWAP resets).

Hypothesis being tested: at session start, where the 21/50-EMA cluster sits
relative to the 200-EMA (above it or below it, and how close) sets a
directional BIAS for the day. The actual entry trigger is the same simple,
frequent signal already tested (a MA breaking away from VWAP beyond a
buffer) - but now FILTERED to only take trades whose break direction agrees
with the 200-EMA bias. This should cut losers from the earlier unfiltered
MA-cross test (which fired in both directions indiscriminately) while
keeping trade frequency reasonable, not near-zero.

Two separate things grid-searched:
  - bias_mode: "either" (use 21 or 50, whichever breaks first) is the entry
    trigger, same as before - this sets the frequency floor.
  - near_200_atr_mult: optional - require the session-open cluster to be
    within N*ATR of the 200-EMA ("close to the 200EMA" per direct feedback)
    before taking ANY signal that day. None = no such filter (test both).

Entry: first bar after cluster where EITHER the 21-EMA or 50-EMA closes
beyond buffer_atr_mult*ATR from VWAP, in the SAME direction as the 200-EMA
bias (bias = whether the cluster point sits above or below the 200-EMA).
Trades against the bias are simply not taken (filtered, not flipped) -
this is a real-time filter since bias is known at/before the cluster point
and the 200-EMA is already fully formed history, same for the entry trigger
itself - nothing here uses future information.

Exit: real-time rule - 50-EMA close-back, or a time cap, whichever first.
Variable hold per trade, not forced.

Same real GOLD_M15_native.csv (2014-06-13+), real spread, IS/OOS split,
honest K continued (70 before this file).
"""
import numpy as np
import pandas as pd
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, WINDOW_BARS, GOLD_POINT

HOLD_BARS_200 = 32  # 8h cap, variable hold in practice


def classify_and_test_200bias(df, cluster_atr_mult, buffer_atr_mult, near_200_atr_mult, point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
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

        cluster_i = None
        for i in range(start_i, end_i):
            if (np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(vwap[i]) or np.isnan(m21[i])
                    or np.isnan(m50[i]) or np.isnan(m200[i])):
                continue
            tol = cluster_atr_mult * atr[i]
            if (abs(close[i] - vwap[i]) <= tol and abs(m21[i] - vwap[i]) <= tol
                    and abs(m50[i] - vwap[i]) <= tol):
                cluster_i = i
                break
        if cluster_i is None:
            continue

        # 200-EMA bias at the cluster point: above = long bias, below = short bias
        bias = 1 if vwap[cluster_i] > m200[cluster_i] else -1

        if near_200_atr_mult is not None:
            dist = abs(vwap[cluster_i] - m200[cluster_i]) / atr[cluster_i]
            if dist > near_200_atr_mult:
                continue  # too far from 200-EMA, filtered out for this variant

        # entry: either 21 or 50 EMA breaks beyond buffer*ATR from VWAP,
        # only taken if the break direction agrees with the 200-EMA bias
        resolve_i, direction = None, None
        for i in range(cluster_i + 1, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0:
                continue
            buf = buffer_atr_mult * atr[i]
            above = (m21[i] > vwap[i] + buf) or (m50[i] > vwap[i] + buf)
            below = (m21[i] < vwap[i] - buf) or (m50[i] < vwap[i] - buf)
            if above and bias > 0:
                resolve_i, direction = i, 1
                break
            if below and bias < 0:
                resolve_i, direction = i, -1
                break
        if resolve_i is None:
            continue

        fill_i = resolve_i + 1
        if fill_i >= n:
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)

        exit_i, exit_px, reason = None, None, None
        hard_limit = min(fill_i + HOLD_BARS_200, n - 1)
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
    permonth = f"  (~{len(results)/(n_days/30.44):.1f}/mo)" if n_days else ""
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  "
          f"%PF={pct_pf(results):6.3f}  net%={100*arr.sum():7.2f}  avg%={100*arr.mean():6.3f}  "
          f"avg_hold={holds.mean():5.1f}h  [{rtxt}]{permonth}")


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

    print(f"{'='*100}\nIN-SAMPLE grid search (MA-break-from-VWAP, filtered by 200-EMA bias)\n{'='*100}")
    grid = []
    for cluster_m in (0.3, 0.5):
        for buf_m in (0.15, 0.2, 0.25, 0.3):
            for near_m in (None, 1.0, 2.0):
                res = classify_and_test_200bias(df_is, cluster_m, buf_m, near_m)
                net = sum(r["pnl_pct"] for r in res) if res else -999
                grid.append((cluster_m, buf_m, near_m, len(res), net, pct_pf(res)))
                nm_txt = "none" if near_m is None else f"{near_m}"
                print(f"  cluster={cluster_m} buf={buf_m} near200={nm_txt}:  "
                      f"n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  "
                      f"~{len(res)/(is_days/30.44):.1f}/mo")

    best = max(grid, key=lambda g: g[4])
    print(f"\n  IS winner: cluster={best[0]} buf={best[1]} near200={best[2]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_and_test_200bias(df_oos, best[0], best[1], best[2])
    report("200EMA-bias filtered - OOS", oos_res, oos_days)
    full_res = classify_and_test_200bias(df, best[0], best[1], best[2])
    report("200EMA-bias filtered - FULL", full_res, full_days)

    print(f"\n\n  Honest K note: 2 x 4 x 3 = 24 combinations searched in this file.")
    print(f"  Combined with the 70 already searched earlier in this VWAP-open research")
    print(f"  line, the running total is K=94 if any of these numbers end up reported as a result.")
