"""
Bidirectional version of the pullback-to-MA construction (Scenario B in
meridian_cross_pullback_test.py, which was buy-only). Per direct steer:
the 200-EMA should decide direction - longs only above it, shorts only
below it, with the whole structure mirrored for shorts.

LONG (price above 200-EMA): VWAP > 200-EMA, 21/50 EMA both above VWAP
(uptrend structure) -> price pulls back DOWN to touch the 21 or 50 EMA ->
confirms bounce by closing back ABOVE that MA.

SHORT (price below 200-EMA): VWAP < 200-EMA, 21/50 EMA both below VWAP
(downtrend structure) -> price pulls back UP to touch the 21 or 50 EMA ->
confirms bounce by closing back BELOW that MA.

Exit (both directions): same ATR trailing-stop convention as the rest of
this research line - ratchets in the trade's favor only, long time cap as
fallback.

Same real GOLD_M15_native.csv, real spread, IS/OOS split. New file -
honest K tracked independently; longs and shorts reported both pooled and
split so a one-sided result isn't hidden by averaging.
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


def _run_trailing_exit(close, low, high, atr, fill_i, direction, entry_px, trail_atr_mult, n):
    hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
    best = entry_px
    exit_i, exit_px, reason = None, None, None
    for k in range(fill_i, hard_limit + 1):
        if np.isnan(atr[k]) or atr[k] <= 0:
            continue
        if direction > 0:
            if close[k] > best:
                best = close[k]
            trail = best - trail_atr_mult * atr[k]
            if low[k] <= trail and k > fill_i:
                exit_i, exit_px, reason = k, trail, "TRAIL"
                break
        else:
            if close[k] < best:
                best = close[k]
            trail = best + trail_atr_mult * atr[k]
            if high[k] >= trail and k > fill_i:
                exit_i, exit_px, reason = k, trail, "TRAIL"
                break
    if exit_i is None:
        exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
    return exit_i, exit_px, reason


def classify_pullback_bidir(df, touch_atr_mult, confirm_bars, trail_atr_mult, point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)
    n = len(df)

    results = []
    i = 210
    while i < n - 1:
        if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(m200[i]) or np.isnan(vwap[i])
                or np.isnan(atr[i]) or atr[i] <= 0):
            i += 1
            continue

        above200 = close[i] > m200[i]
        below200 = close[i] < m200[i]
        direction = 0
        if above200 and vwap[i] > m200[i] and m21[i] > vwap[i] and m50[i] > vwap[i]:
            direction = 1
        elif below200 and vwap[i] < m200[i] and m21[i] < vwap[i] and m50[i] < vwap[i]:
            direction = -1
        if direction == 0:
            i += 1
            continue

        tol = touch_atr_mult * atr[i]
        touched_21 = abs(close[i] - m21[i]) <= tol
        touched_50 = abs(close[i] - m50[i]) <= tol
        if touched_21 or touched_50:
            ref_ma = m21 if touched_21 else m50
            resolve_i = None
            for j in range(i + 1, min(i + confirm_bars + 1, n)):
                if np.isnan(atr[j]) or atr[j] <= 0:
                    continue
                if direction > 0 and close[j] > ref_ma[j] + 0.1 * atr[j]:
                    resolve_i = j
                    break
                if direction < 0 and close[j] < ref_ma[j] - 0.1 * atr[j]:
                    resolve_i = j
                    break
            if resolve_i is not None:
                fill_i = resolve_i + 1
                if fill_i < n and not np.isnan(atr[fill_i]) and atr[fill_i] > 0:
                    sc = spread[fill_i] * point
                    entry_px = close[fill_i] + (sc if direction > 0 else -sc)
                    exit_i, exit_px, reason = _run_trailing_exit(close, low, high, atr, fill_i, direction,
                                                                   entry_px, trail_atr_mult, n)
                    pnl_pct = ((exit_px - entry_px) / entry_px) * direction
                    results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                                         reason=reason, hold_bars=exit_i - fill_i))
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

    print(f"{'='*100}\nIN-SAMPLE grid: bidirectional pullback-to-MA, 200-EMA decides direction\n{'='*100}")
    grid = []
    for touch_m in (0.15, 0.25, 0.35):
        for confirm_b in (3, 5):
            for trail_m in (1.5, 2.0, 2.5):
                res = classify_pullback_bidir(df_is, touch_m, confirm_b, trail_m)
                net = sum(r["pnl_pct"] for r in res) if res else -999
                grid.append((touch_m, confirm_b, trail_m, len(res), net, pct_pf(res)))
                print(f"  touch={touch_m} confirm={confirm_b} trail={trail_m}:  n={len(res):4d}  "
                      f"net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  ~{len(res)/(is_days/30.44):.1f}/mo", flush=True)

    best = max(grid, key=lambda g: g[4])
    print(f"\n  IS winner: touch={best[0]} confirm={best[1]} trail={best[2]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation (pooled, then split long/short)\n{'='*100}")
    oos_res = classify_pullback_bidir(df_oos, best[0], best[1], best[2])
    report("Bidir pullback - OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_pullback_bidir(df, best[0], best[1], best[2])
    report("Bidir pullback - FULL", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K note: {len(grid)} combinations searched in this file. New, separate")
    print(f"  construction from tonight's other research lines - tracked independently.")
