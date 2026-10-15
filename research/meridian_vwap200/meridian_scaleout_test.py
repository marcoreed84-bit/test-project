"""
Tests a different exit mechanism on the SAME entry as Scenario A
(meridian_cross_pullback_test.py - 21/50 cross confirmed above VWAP and
200-EMA, buy only - the least-bad of the four Meridian-framed constructions
tried tonight: full-history PF=0.943, closest to breakeven). Per direct
request: fixed-R scale-out instead of a pure trailing stop from entry.

Mechanism:
  1. Initial protective stop at entry - risk_atr_mult * ATR(entry) below
     entry (a conventional fixed-R stop, defining "1R" for this trade).
  2. Scale target at entry + scale_r_mult * (risk_atr_mult * ATR(entry))
     above entry (e.g. scale_r_mult=1.0 means take partial profit at 1R).
  3. Walk forward bar by bar (intrabar high/low, matching how real stop/
     limit orders fill): if the INITIAL stop is touched before the scale
     target, the full position exits there (standard R-multiple loss).
     If the scale target is touched first, scale_pct of the position exits
     there at a locked-in profit, and the remainder switches to the SAME
     ATR trailing-stop convention used elsewhere in this research line
     (ratchets in favor only) from that point forward.
  4. Long time cap as ultimate fallback, same as the rest of this line.

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


def classify_scaleout(df, risk_atr_mult, scale_r_mult, scale_pct, trail_atr_mult, point=GOLD_POINT):
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
                or np.isnan(m21[i - 1]) or np.isnan(m50[i - 1])):
            i += 1
            continue
        crossed_up = m21[i - 1] <= m50[i - 1] and m21[i] > m50[i]
        if not (crossed_up and close[i] > vwap[i] and m21[i] > vwap[i] and m50[i] > vwap[i] and close[i] > m200[i]):
            i += 1
            continue

        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[fill_i]) or atr[fill_i] <= 0:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + sc
        R = risk_atr_mult * atr[fill_i]
        stop_px = entry_px - R
        scale_px = entry_px + scale_r_mult * R

        hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)
        exit_i, exit_px, reason, pnl_pct = None, None, None, None

        # phase 1: race between initial stop and scale target
        scaled = False
        scale_bar = None
        for k in range(fill_i, hard_limit + 1):
            if k == fill_i:
                continue   # no stop/target check on the entry bar itself
            hit_stop = low[k] <= stop_px
            hit_scale = high[k] >= scale_px
            if hit_stop and hit_scale:
                # conservative - assume the worse outcome (stop) wins when both touch same bar
                exit_i, exit_px, reason = k, stop_px, "STOP"
                pnl_pct = (exit_px - entry_px) / entry_px
                break
            if hit_stop:
                exit_i, exit_px, reason = k, stop_px, "STOP"
                pnl_pct = (exit_px - entry_px) / entry_px
                break
            if hit_scale:
                scaled = True
                scale_bar = k
                break
        if exit_i is not None:
            results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, reason=reason,
                                 hold_bars=exit_i - fill_i))
            i = exit_i + 1
            continue
        if not scaled:
            # hit the time cap without ever touching stop or scale
            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"
            pnl_pct = (exit_px - entry_px) / entry_px
            results.append(dict(entry_i=i, exit_i=exit_i, pnl_pct=pnl_pct, reason=reason,
                                 hold_bars=exit_i - fill_i))
            i = exit_i + 1
            continue

        # phase 2: scaled out scale_pct at scale_px (locked-in profit), remainder trails
        remainder_entry_ref = scale_px   # trail starts ratcheting from the scale point forward
        best = remainder_entry_ref
        rem_exit_i, rem_exit_px, rem_reason = None, None, None
        for k in range(scale_bar + 1, hard_limit + 1):
            if np.isnan(atr[k]) or atr[k] <= 0:
                continue
            if close[k] > best:
                best = close[k]
            trail = best - trail_atr_mult * atr[k]
            if low[k] <= trail:
                rem_exit_i, rem_exit_px, rem_reason = k, trail, "TRAIL"
                break
        if rem_exit_i is None:
            rem_exit_i, rem_exit_px, rem_reason = hard_limit, close[hard_limit], "TIME"

        scaled_leg_pnl = (scale_px - entry_px) / entry_px
        remainder_leg_pnl = (rem_exit_px - entry_px) / entry_px
        pnl_pct = scale_pct * scaled_leg_pnl + (1 - scale_pct) * remainder_leg_pnl
        results.append(dict(entry_i=i, exit_i=rem_exit_i, pnl_pct=pnl_pct, reason=f"SCALE+{rem_reason}",
                             hold_bars=rem_exit_i - fill_i))
        i = rem_exit_i + 1

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

    print(f"{'='*100}\nIN-SAMPLE grid: fixed-R scale-out then trail remainder (scale_pct=0.5 fixed)\n{'='*100}")
    grid = []
    SCALE_PCT = 0.5
    for risk_m in (1.0, 1.5):
        for scale_r in (1.0, 1.5, 2.0):
            for trail_m in (1.5, 2.0, 2.5):
                res = classify_scaleout(df_is, risk_m, scale_r, SCALE_PCT, trail_m)
                net = sum(r["pnl_pct"] for r in res) if res else -999
                grid.append((risk_m, scale_r, trail_m, len(res), net, pct_pf(res)))
                print(f"  risk={risk_m}R scale_at={scale_r}R trail={trail_m}:  n={len(res):4d}  "
                      f"net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  ~{len(res)/(is_days/30.44):.1f}/mo", flush=True)

    best = max(grid, key=lambda g: g[4])
    print(f"\n  IS winner: risk={best[0]}R scale_at={best[1]}R trail={best[2]}   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_scaleout(df_oos, best[0], best[1], SCALE_PCT, best[2])
    report("Scale-out - OOS", oos_res, oos_days)
    full_res = classify_scaleout(df, best[0], best[1], SCALE_PCT, best[2])
    report("Scale-out - FULL", full_res, full_days)

    print(f"\n\n  Honest K note: {len(grid)} combinations searched in this file (scale_pct held fixed at 0.5,")
    print(f"  not grid-searched). Same entry as Scenario A (already the least-bad of four Meridian")
    print(f"  constructions tried tonight) - only the exit mechanism changed here.")
