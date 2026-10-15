"""
New, specific construction for Meridian's framing (Gold M15) - two distinct
buy-only scenarios, per direct instruction. Genuinely different from the
VWAP-open discretionary research line done earlier tonight: this uses the
200-EMA as a hard trend filter AND the 21/50-EMA cross itself as the entry
trigger (not a VWAP break), with a real trailing-stop exit ("ride the leg
until it loses momentum") rather than a fixed target or invalidation level.

SCENARIO A - "cross and confirm above VWAP/200":
  21-EMA crosses above 50-EMA, AND at that same bar: close > VWAP, 21-EMA >
  VWAP, 50-EMA > VWAP, AND close > 200-EMA. All conditions checked at the
  cross bar itself (causal - only uses that bar's own closed values).
  Entry fills next bar. Buy-only, per direct instruction.

SCENARIO B - "pullback to 21/50 in an established uptrend":
  Context: VWAP > 200-EMA (session VWAP running above the longer trend
  average), AND 21-EMA > VWAP, AND 50-EMA > VWAP (already in an uptrend
  structure). Within that context, price pulls back down to touch the
  21-EMA or 50-EMA (approaches from above, comes within touch_atr_mult*ATR),
  then confirms the bounce by closing back above that MA within a few bars.
  Entry fills next bar after confirmation. Buy-only.

EXIT (both scenarios, real-time valid): ATR-based trailing stop that only
ever ratchets in the trade's favor (never loosens) - "ride until it loses
momentum" per direct instruction. Trail = highest close since entry minus
trail_atr_mult * current ATR. Exit when a bar's LOW touches the trail level
(intrabar, matching how a real stop order fills) or a long time cap as an
ultimate fallback (this is meant to ride a trending leg, not a quick scalp).

Same real GOLD_M15_native.csv (2014-06-13+ clean window), real spread,
IS/OOS split (70/30 by date). This is a new, separate research line from
tonight's VWAP-open discretionary idea - honest K tracked independently,
starting fresh at 0 for this file.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, session_vwap, GOLD_POINT

TIME_CAP_BARS = 200   # 50h hard fallback cap - this construction is meant to ride a trending leg


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


def _run_trailing_exit(close, high, low, atr, fill_i, direction, entry_px, trail_atr_mult, n):
    hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
    highest_close = entry_px
    exit_i, exit_px, reason = None, None, None
    for k in range(fill_i, hard_limit + 1):
        if np.isnan(atr[k]) or atr[k] <= 0:
            continue
        if close[k] > highest_close:
            highest_close = close[k]
        trail = highest_close - trail_atr_mult * atr[k]
        if low[k] <= trail and k > fill_i:   # give the entry bar itself a pass - no stop on bar 0
            exit_i, exit_px, reason = k, trail, "TRAIL"
            break
    if exit_i is None:
        exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
    return exit_i, exit_px, reason


def classify_scenario_a(df, trail_atr_mult, point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m21 = ema(close, 21)
    m50 = ema(close, 50)
    m200 = ema(close, 200)
    atr = wilder_atr(high, low, close, 14)
    vwap = session_vwap(df)
    n = len(df)

    results = []
    i = 210   # past the 200-EMA warmup
    while i < n - 1:
        if (np.isnan(m21[i]) or np.isnan(m50[i]) or np.isnan(m200[i]) or np.isnan(vwap[i])
                or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1])):
            i += 1
            continue
        crossed_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
        if crossed_up and close[i] > vwap[i] and m21[i] > vwap[i] and m50[i] > vwap[i] and close[i] > m200[i]:
            fill_i = i + 1
            if fill_i < n and not np.isnan(atr[fill_i]) and atr[fill_i] > 0:
                sc = spread[fill_i] * point
                entry_px = close[fill_i] + sc
                exit_i, exit_px, reason = _run_trailing_exit(close, high, low, atr, fill_i, 1, entry_px,
                                                               trail_atr_mult, n)
                pnl_pct = (exit_px - entry_px) / entry_px
                results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, reason=reason,
                                     hold_bars=exit_i - fill_i))
                i = exit_i + 1
                continue
        i += 1
    return results


def classify_scenario_b(df, touch_atr_mult, confirm_bars, trail_atr_mult, point=GOLD_POINT):
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
        # uptrend context: VWAP above 200-EMA, both MAs above VWAP
        uptrend = vwap[i] > m200[i] and m21[i] > vwap[i] and m50[i] > vwap[i]
        if not uptrend:
            i += 1
            continue
        # pullback: close comes within touch distance of EITHER the 21 or 50 EMA
        tol = touch_atr_mult * atr[i]
        touched_21 = abs(close[i] - m21[i]) <= tol
        touched_50 = abs(close[i] - m50[i]) <= tol
        if touched_21 or touched_50:
            ref_ma = m21 if touched_21 else m50
            resolve_i = None
            for j in range(i + 1, min(i + confirm_bars + 1, n)):
                if np.isnan(atr[j]) or atr[j] <= 0:
                    continue
                if close[j] > ref_ma[j] + 0.1 * atr[j]:   # confirms the bounce resumed
                    resolve_i = j
                    break
            if resolve_i is not None:
                fill_i = resolve_i + 1
                if fill_i < n and not np.isnan(atr[fill_i]) and atr[fill_i] > 0:
                    sc = spread[fill_i] * point
                    entry_px = close[fill_i] + sc
                    exit_i, exit_px, reason = _run_trailing_exit(close, high, low, atr, fill_i, 1, entry_px,
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

    print(f"{'#'*100}\nSCENARIO A - 21/50 cross above VWAP & 200-EMA, buy only\n{'#'*100}")
    print(f"{'='*100}\nIN-SAMPLE grid search (trailing ATR stop only)\n{'='*100}")
    gridA = []
    for trail_m in (1.0, 1.5, 2.0, 2.5, 3.0):
        res = classify_scenario_a(df_is, trail_m)
        net = sum(r["pnl_pct"] for r in res) if res else -999
        gridA.append((trail_m, len(res), net, pct_pf(res)))
        print(f"  trail={trail_m}:  n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  "
              f"~{len(res)/(is_days/30.44):.1f}/mo", flush=True)
    bestA = max(gridA, key=lambda g: g[2])
    print(f"\n  IS winner: trail={bestA[0]}   (K={len(gridA)} combinations searched)")
    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oosA = classify_scenario_a(df_oos, bestA[0])
    report("Scenario A - OOS", oosA, oos_days)
    fullA = classify_scenario_a(df, bestA[0])
    report("Scenario A - FULL", fullA, full_days)

    print(f"\n\n{'#'*100}\nSCENARIO B - pullback to 21/50 EMA in VWAP>200EMA uptrend, buy only\n{'#'*100}")
    print(f"{'='*100}\nIN-SAMPLE grid search\n{'='*100}")
    gridB = []
    for touch_m in (0.15, 0.25, 0.35):
        for confirm_b in (3, 5):
            for trail_m in (1.5, 2.0, 2.5):
                res = classify_scenario_b(df_is, touch_m, confirm_b, trail_m)
                net = sum(r["pnl_pct"] for r in res) if res else -999
                gridB.append((touch_m, confirm_b, trail_m, len(res), net, pct_pf(res)))
                print(f"  touch={touch_m} confirm={confirm_b} trail={trail_m}:  n={len(res):4d}  "
                      f"net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  ~{len(res)/(is_days/30.44):.1f}/mo", flush=True)
    bestB = max(gridB, key=lambda g: g[4])
    print(f"\n  IS winner: touch={bestB[0]} confirm={bestB[1]} trail={bestB[2]}   (K={len(gridB)} combinations searched)")
    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oosB = classify_scenario_b(df_oos, bestB[0], bestB[1], bestB[2])
    report("Scenario B - OOS", oosB, oos_days)
    fullB = classify_scenario_b(df, bestB[0], bestB[1], bestB[2])
    report("Scenario B - FULL", fullB, full_days)

    print(f"\n\n  Honest K note: Scenario A searched {len(gridA)} combinations, Scenario B searched")
    print(f"  {len(gridB)} combinations. This is a NEW, separate research line from tonight's")
    print(f"  VWAP-open discretionary idea (K=228 there) - tracked independently here, starting")
    print(f"  fresh. Combined K for THIS file if either result is reported: {len(gridA) + len(gridB)}.")
