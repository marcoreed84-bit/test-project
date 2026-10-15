"""
Corrected entry per direct clarification: the 21/50-EMA cross and the
above-VWAP confirmation are NOT required on the same bar (that was
Scenario A's construction, meridian_cross_pullback_test.py). The real
sequence is:

  1. 21-EMA crosses above 50-EMA while BOTH are still below VWAP (the
     cross happens below VWAP).
  2. Later (not necessarily immediately), BOTH 21 and 50 EMA cross above
     VWAP - THIS is the actual buy entry trigger, not the original cross.

Mirrored for sells: 21-EMA crosses below 50-EMA while both are above
VWAP, then later both cross below VWAP - sell entry.

This is a genuinely different, more sequential construction than Scenario
A's single-bar simultaneous condition. Exit: both the plain ATR trailing
stop (reference/baseline) and the 50-EMA close-back exit (the one exit
that showed a real, consistent positive result on Scenario A tonight -
worth checking whether it holds up on this corrected entry too, pending
its own null test).

Same real GOLD_M15_native.csv, real spread, IS/OOS split. New file -
honest K tracked independently.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, GOLD_POINT

TIME_CAP_BARS = 200
CROSS_SEARCH_WINDOW = 40   # max bars after the below-VWAP cross to wait for the above-VWAP confirmation


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


def _sequential_entries(df):
    """Finds both long and short entries per the sequential cross->VWAP-break construction."""
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)
    n = len(df)
    entries = []   # (cross_i, resolve_i, fill_i, direction)
    i = 60
    while i < n - 1:
        if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(vwap[i])
                or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1])):
            i += 1
            continue
        cross_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
        cross_down = m21[i - 1] >= m50[i - 1] and m21[i] < m50[i]

        if cross_up and m21[i] < vwap[i] and m50[i] < vwap[i]:
            resolve_i = None
            for j in range(i + 1, min(i + CROSS_SEARCH_WINDOW + 1, n)):
                if np.isnan(vwap[j]) or np.isnan(m21[j]) or np.isnan(m50[j]):
                    continue
                if m21[j] > vwap[j] and m50[j] > vwap[j]:
                    resolve_i = j
                    break
                if m21[j] < m50[j]:   # cross undone before confirming - abandon
                    break
            if resolve_i is not None:
                fill_i = resolve_i + 1
                if fill_i < n and not np.isnan(atr[fill_i]) and atr[fill_i] > 0:
                    entries.append((i, resolve_i, fill_i, 1))
                    i = resolve_i + 1
                    continue
        elif cross_down and m21[i] > vwap[i] and m50[i] > vwap[i]:
            resolve_i = None
            for j in range(i + 1, min(i + CROSS_SEARCH_WINDOW + 1, n)):
                if np.isnan(vwap[j]) or np.isnan(m21[j]) or np.isnan(m50[j]):
                    continue
                if m21[j] < vwap[j] and m50[j] < vwap[j]:
                    resolve_i = j
                    break
                if m21[j] > m50[j]:
                    break
            if resolve_i is not None:
                fill_i = resolve_i + 1
                if fill_i < n and not np.isnan(atr[fill_i]) and atr[fill_i] > 0:
                    entries.append((i, resolve_i, fill_i, -1))
                    i = resolve_i + 1
                    continue
        i += 1
    return entries, close, high, low, m21, m50, atr, vwap


def classify_trail_exit(df, trail_atr_mult, point=GOLD_POINT):
    entries, close, high, low, m21, m50, atr, vwap = _sequential_entries(df)
    spread = df["spread"].values
    n = len(df)
    results = []
    for cross_i, resolve_i, fill_i, direction in entries:
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)
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
        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=cross_i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
    return results


def classify_ema_exit(df, which_ma, point=GOLD_POINT):
    entries, close, high, low, m21, m50, atr, vwap = _sequential_entries(df)
    ma = m21 if which_ma == 21 else m50
    spread = df["spread"].values
    n = len(df)
    results = []
    for cross_i, resolve_i, fill_i, direction in entries:
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if direction > 0 else -sc)
        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
        exit_i, exit_px, reason = None, None, None
        for k in range(fill_i + 1, hard_limit + 1):
            if np.isnan(ma[k]):
                continue
            broke = (close[k] < ma[k]) if direction > 0 else (close[k] > ma[k])
            if broke:
                exit_i, exit_px, reason = k, close[k], f"EMA{which_ma}"
                break
        if exit_i is None:
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
        results.append(dict(entry_i=cross_i, exit_i=exit_i, pnl_pct=pnl_pct, dir=direction,
                             reason=reason, hold_bars=exit_i - fill_i))
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

    print(f"{'#'*100}\nSEQUENTIAL ENTRY + ATR TRAILING STOP (reference/baseline)\n{'#'*100}")
    grid = []
    for trail_m in (1.5, 2.0, 2.5):
        res = classify_trail_exit(df_is, trail_m)
        net = sum(r["pnl_pct"] for r in res) if res else -999
        grid.append((trail_m, len(res), net, pct_pf(res)))
        print(f"  trail={trail_m}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  "
              f"~{len(res)/(is_days/30.44):.1f}/mo", flush=True)
    best = max(grid, key=lambda g: g[2])
    print(f"  IS winner: trail={best[0]}  (K={len(grid)})")
    oos_res = classify_trail_exit(df_oos, best[0])
    report("OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_trail_exit(df, best[0])
    report("FULL", full_res, full_days, split_dir=True)

    print(f"\n{'#'*100}\nSEQUENTIAL ENTRY + 50-EMA close-back exit\n{'#'*100}")
    is_res = classify_ema_exit(df_is, 50)
    report("IS", is_res, is_days, split_dir=True)
    oos_res = classify_ema_exit(df_oos, 50)
    report("OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_ema_exit(df, 50)
    report("FULL", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K note: trail-exit grid K={len(grid)}, EMA50-exit has no free params (K=1).")
    print(f"  Total K for this file: {len(grid)+1}. New entry construction, separate from Scenario A.")
