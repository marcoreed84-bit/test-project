"""
Seventh construction - same entry, different exit philosophy, per direct
feedback: every exit tried so far in this research line has been a
"ride it until invalidated or time runs out" rule (50-EMA/200-EMA/VWAP
close-back, or a multi-hour time cap). That optimizes for maximum hold,
not for taking smaller, more consistent profit quickly. This file tests
the opposite: a fixed ATR-based profit target and stop-loss, checked
intrabar (high/low, not just close) so a target or stop can be hit
mid-bar, same as it would be in live trading with a real order. Whichever
is touched first wins; a short time cap is the fallback if neither is hit.

Entry unchanged from vwap_200ema_touch_test.py (the already-debugged,
already-fixed 200-EMA touch/rejection trigger - NOT the VWAP-break entries
that failed earlier in this line). Target/stop are set as ATR multiples AT
ENTRY time (known causally, no lookahead), symmetric and asymmetric
risk:reward ratios both tested.

Same real GOLD_M15_native.csv, real spread, IS/OOS split, honest K
continued (142 before this file).
"""
import numpy as np
import pandas as pd
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, GOLD_POINT


def classify_and_test_fixed_target(df, approach_mult, touch_mult, reject_mult, confirm_bars,
                                    window_bars, target_atr_mult, stop_atr_mult, time_cap_bars,
                                    point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m200 = ema(close, 200)
    atr = wilder_atr(high, low, close, 14)

    day = df["time"].dt.date.values
    n = len(df)
    day_start_idx = {}
    for i in range(n):
        if day[i] not in day_start_idx:
            day_start_idx[day[i]] = i

    results = []
    for d, start_i in day_start_idx.items():
        end_i = min(start_i + window_bars, n) if window_bars else n
        if end_i - start_i < 10:
            continue

        last_side = 0
        i = start_i
        while i < end_i:
            if np.isnan(atr[i]) or atr[i] <= 0 or np.isnan(m200[i]):
                i += 1
                continue
            diff = close[i] - m200[i]
            ap = approach_mult * atr[i]
            if abs(diff) > ap:
                last_side = 1 if diff > 0 else -1

            tol = touch_mult * atr[i]
            if last_side != 0 and abs(diff) <= tol:
                touch_i, prior_side = i, last_side
                resolve_i = None
                for j in range(touch_i + 1, min(touch_i + confirm_bars + 1, end_i, n)):
                    if np.isnan(atr[j]) or atr[j] <= 0:
                        continue
                    rb = reject_mult * atr[j]
                    dj = close[j] - m200[j]
                    if prior_side > 0 and dj > rb:
                        resolve_i = j
                        break
                    if prior_side < 0 and dj < -rb:
                        resolve_i = j
                        break
                if resolve_i is not None:
                    direction = prior_side
                    fill_i = resolve_i + 1
                    if fill_i < n and not np.isnan(atr[fill_i]) and atr[fill_i] > 0:
                        sc = spread[fill_i] * point
                        entry_px = close[fill_i] + (sc if direction > 0 else -sc)

                        entry_atr = atr[fill_i]
                        target_px = entry_px + direction * target_atr_mult * entry_atr
                        stop_px = entry_px - direction * stop_atr_mult * entry_atr

                        exit_i, exit_px, reason = None, None, None
                        hard_limit = min(fill_i + time_cap_bars, n - 1)
                        for k in range(fill_i, hard_limit + 1):
                            if direction > 0:
                                hit_stop = low[k] <= stop_px
                                hit_target = high[k] >= target_px
                            else:
                                hit_stop = high[k] >= stop_px
                                hit_target = low[k] <= target_px
                            # if both touched same bar, assume the worse outcome
                            # (stop) hits first - conservative, no intrabar order info
                            if hit_stop and hit_target:
                                exit_i, exit_px, reason = k, stop_px, "STOP"
                                break
                            if hit_stop:
                                exit_i, exit_px, reason = k, stop_px, "STOP"
                                break
                            if hit_target:
                                exit_i, exit_px, reason = k, target_px, "TARGET"
                                break
                        if exit_i is None:
                            exit_i, exit_px, reason = hard_limit, close[hard_limit], "TIME"

                        pnl_pct = ((exit_px - entry_px) / entry_px) * direction
                        hold_bars = exit_i - fill_i
                        results.append(dict(day=d, entry_i=resolve_i, exit_i=exit_i, pnl_pct=pnl_pct,
                                             dir=direction, reason=reason, hold_bars=hold_bars))
                    last_side = 0
                    i = resolve_i + 1
                    continue
            i += 1

    return results


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
    permonth = f"  (~{len(results)/(n_days/30.44):.1f}/mo)" if n_days else ""
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  "
          f"%PF={pct_pf(results):6.3f}  net%={100*arr.sum():7.2f}  avg%={100*arr.mean():6.3f}  "
          f"avg_hold={holds.mean():5.1f}h  [{rtxt}]{permonth}")
    if split_dir:
        longs = [r for r in results if r["dir"] > 0]
        shorts = [r for r in results if r["dir"] < 0]
        report(f"    -> LONGS only", longs, n_days)
        report(f"    -> SHORTS only", shorts, n_days)


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

    # entry params fixed at a reasonably frequent, already-characterized setting
    # from the prior (corrected) 200-EMA touch/reject run - isolates the exit
    # philosophy as the variable actually being tested here
    APPROACH, TOUCH, REJECT, CONFIRM, WINDOW = 1.0, 0.15, 0.3, 4, 32

    print(f"{'='*100}\nIN-SAMPLE grid search (fixed ATR target/stop, entry params held fixed)\n{'='*100}")
    grid = []
    for target_m in (0.5, 0.75, 1.0, 1.5):
        for stop_m in (0.5, 0.75, 1.0, 1.5):
            for cap_bars in (8, 12):  # 2h, 3h - short, per direct feedback
                res = classify_and_test_fixed_target(df_is, APPROACH, TOUCH, REJECT, CONFIRM, WINDOW,
                                                       target_m, stop_m, cap_bars)
                net = sum(r["pnl_pct"] for r in res) if res else -999
                grid.append((target_m, stop_m, cap_bars, len(res), net, pct_pf(res)))
                print(f"    target={target_m} stop={stop_m} cap={cap_bars*0.25:.0f}h:  "
                      f"n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  ~{len(res)/(is_days/30.44):.1f}/mo",
                      flush=True)

    grid.sort(key=lambda g: g[4], reverse=True)
    print("\n  Top 10 by net%:")
    for g in grid[:10]:
        print(f"    target={g[0]} stop={g[1]} cap={g[2]*0.25:.0f}h:  "
              f"n={g[3]:4d}  net%={100*g[4]:7.2f}  PF={g[5]:5.2f}  ~{g[3]/(is_days/30.44):.1f}/mo")

    best = grid[0]
    print(f"\n  IS winner: target={best[0]} stop={best[1]} cap={best[2]*0.25:.0f}h   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation (pooled, then split long/short)\n{'='*100}")
    oos_res = classify_and_test_fixed_target(df_oos, APPROACH, TOUCH, REJECT, CONFIRM, WINDOW,
                                              best[0], best[1], best[2])
    report("Fixed target/stop - OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_and_test_fixed_target(df, APPROACH, TOUCH, REJECT, CONFIRM, WINDOW,
                                               best[0], best[1], best[2])
    report("Fixed target/stop - FULL", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K note: 4 x 4 x 2 = 32 combinations searched in this file")
    print(f"  (entry params held fixed, not re-searched - only exit mechanics varied here).")
    print(f"  Combined with the 142 already searched earlier in this VWAP-open research")
    print(f"  line, the running total is K=174 if any of these numbers end up reported as a result.")
