"""
Third construction, per user's direct steer: entry trigger is the MOVING
AVERAGE itself crossing session VWAP (not price crossing VWAP) - a slower,
more deliberate signal. Exit CAN legitimately be price closing back through
VWAP this time (unlike the rejected Pattern 1 construction) because by the
time price itself re-crosses VWAP against an MA-cross entry, that's already
a real adverse move, not the noise-level wiggle VWAP does constantly on its
own.

Two separate scenarios tested independently, not assumed which one works:
  - 21-EMA crosses VWAP
  - 50-EMA crosses VWAP

Same "cluster" precondition as before (the whole system starts the session
near VWAP, so this isn't just picking up a trend already in progress at
session start), same early-morning window, same real-time-valid
construction (entry known causally, exit is a live rule not a filter),
same GOLD_M15_native.csv clean window, real spread, same IS/OOS discipline.
"""
import numpy as np
import pandas as pd
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, WINDOW_BARS, HOLD_BARS, GOLD_POINT


def classify_and_test_ma_cross(df, which_ma, cluster_atr_mult, buffer_atr_mult, point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    ma = m21 if which_ma == 21 else m50
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
            if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(vwap[i]) or np.isnan(m21[i]) or np.isnan(m50[i]):
                continue
            tol = cluster_atr_mult * atr[i]
            if (abs(close[i] - vwap[i]) <= tol and abs(m21[i] - vwap[i]) <= tol
                    and abs(m50[i] - vwap[i]) <= tol):
                cluster_i = i
                break
        if cluster_i is None:
            continue

        # entry: the MA itself crosses beyond buffer*ATR of VWAP after the
        # cluster point (price not required to confirm - that's the whole
        # point of this construction)
        resolve_i, direction = None, None
        for i in range(cluster_i + 1, end_i):
            if np.isnan(atr[i]) or atr[i] <= 0:
                continue
            buf = buffer_atr_mult * atr[i]
            if ma[i] > vwap[i] + buf:
                resolve_i, direction = i, 1
                break
            if ma[i] < vwap[i] - buf:
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
        hard_limit = min(fill_i + HOLD_BARS, n - 1)
        for j in range(fill_i, hard_limit + 1):
            if np.isnan(vwap[j]):
                continue
            broke = (close[j] < vwap[j]) if direction > 0 else (close[j] > vwap[j])
            if broke:
                exit_i, exit_px, reason = j, close[j], "VWAP"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(day=d, entry_i=resolve_i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction, reason=reason))

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
    reasons = {}
    for r in results:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    rtxt = ", ".join(f"{k}:{v}" for k, v in reasons.items())
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  "
          f"%PF={pct_pf(results):6.3f}  net%={100*arr.sum():7.2f}  avg%={100*arr.mean():6.3f}  [{rtxt}]")


def run_for_ma(df, df_is, df_oos, which_ma):
    print(f"\n{'#'*100}\n{which_ma}-EMA crosses VWAP\n{'#'*100}")
    print(f"{'='*100}\nIN-SAMPLE grid search\n{'='*100}")
    grid = []
    for cluster_m in (0.3, 0.5, 0.7):
        for buf_m in (0.1, 0.2, 0.3):
            res = classify_and_test_ma_cross(df_is, which_ma, cluster_m, buf_m)
            net = sum(r["pnl_pct"] for r in res) if res else -999
            grid.append((cluster_m, buf_m, len(res), net, pct_pf(res)))
            print(f"  cluster={cluster_m} buf={buf_m}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}")

    best = max(grid, key=lambda g: g[3])
    print(f"\n  IS winner: cluster={best[0]} buf={best[1]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_and_test_ma_cross(df_oos, which_ma, best[0], best[1])
    report(f"{which_ma}-EMA cross VWAP - OOS", oos_res)
    full_res = classify_and_test_ma_cross(df, which_ma, best[0], best[1])
    report(f"{which_ma}-EMA cross VWAP - FULL", full_res)
    return best, oos_res, full_res


if __name__ == "__main__":
    df = load_gold_m15()
    n = len(df)
    print(f"GOLD M15 real: {df['time'].iloc[0]} .. {df['time'].iloc[-1]} ({n} bars)")
    cutoff_i = int(n * 0.70)
    cutoff_date = df["time"].iloc[cutoff_i].date()
    df_is = df[df["time"].dt.date < cutoff_date].reset_index(drop=True)
    df_oos = df[df["time"].dt.date >= cutoff_date].reset_index(drop=True)

    run_for_ma(df, df_is, df_oos, 21)
    run_for_ma(df, df_is, df_oos, 50)

    print(f"\n\n  Honest K note: 2 MA choices x 9 threshold combos each = 18 total combinations")
    print(f"  searched in this file. Combined with the 16 already searched for the rejected")
    print(f"  Pattern 1/2 constructions, the running total for this whole VWAP-open research")
    print(f"  line is K=34 if any of these numbers end up reported as a result.")
