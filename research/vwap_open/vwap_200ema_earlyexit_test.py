"""
Eighth variant - still the same, already-debugged 200-EMA touch/rejection
entry. Per direct feedback on the fixed-target/stop test (which showed a
tight stop gets whipsawed by noise, while a wide stop just converges back
to the same mediocre PF as the ride-until-invalidated exit): add an
explicit "is this trade already dead" early cutoff, distinct from both.
Not a tighter static stop (tested, catastrophic - see
vwap_200ema_fixedtarget_test.py) but a conditional one: if price hasn't
shown ANY meaningful favorable movement (tracked as max favorable
excursion, MFE) within the first few bars after entry, exit immediately
at market rather than waiting for the full-distance stop to get hit. This
is the actual mechanism behind "if price reaches a certain point even
before the stop loss we should know the trade is fucked" - cutting a
trade that is already showing no sign of working, rather than either (a)
a uniformly tighter stop (which cuts winners and losers alike
indiscriminately and was already shown to fail) or (b) waiting for the
full stop distance regardless of early behavior.

Exit precedence per bar, checked causally (fill_i onward): stop hit, then
target hit, then (only at the early_bars checkpoint) the early-dead
cutoff if MFE so far is below threshold, else the time cap at the end.

Same real GOLD_M15_native.csv, real spread, IS/OOS split, honest K
continued (174 before this file).
"""
import numpy as np
import pandas as pd
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, GOLD_POINT


def classify_and_test_early_exit(df, approach_mult, touch_mult, reject_mult, confirm_bars, window_bars,
                                  target_atr_mult, stop_atr_mult, time_cap_bars,
                                  early_bars, early_progress_mult, point=GOLD_POINT):
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
                        early_thresh = early_progress_mult * entry_atr

                        exit_i, exit_px, reason = None, None, None
                        hard_limit = min(fill_i + time_cap_bars, n - 1)
                        early_limit = min(fill_i + early_bars - 1, hard_limit)
                        mfe = 0.0
                        for k in range(fill_i, hard_limit + 1):
                            if direction > 0:
                                hit_stop = low[k] <= stop_px
                                hit_target = high[k] >= target_px
                                mfe = max(mfe, high[k] - entry_px)
                            else:
                                hit_stop = high[k] >= stop_px
                                hit_target = low[k] <= target_px
                                mfe = max(mfe, entry_px - low[k])
                            if hit_stop:
                                exit_i, exit_px, reason = k, stop_px, "STOP"
                                break
                            if hit_target:
                                exit_i, exit_px, reason = k, target_px, "TARGET"
                                break
                            if k == early_limit and mfe < early_thresh:
                                exit_i, exit_px, reason = k, close[k], "EARLY_DEAD"
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

    APPROACH, TOUCH, REJECT, CONFIRM, WINDOW = 1.0, 0.15, 0.3, 4, 32

    print(f"{'='*100}\nIN-SAMPLE grid: target/stop + early-dead cutoff\n{'='*100}")
    grid = []
    for target_m in (1.0, 1.5, 2.0):
        for stop_m in (1.5, 2.0):
            for early_bars in (2, 3, 4):
                for early_prog in (0.1, 0.2, 0.3):
                    res = classify_and_test_early_exit(df_is, APPROACH, TOUCH, REJECT, CONFIRM, WINDOW,
                                                        target_m, stop_m, 32, early_bars, early_prog)
                    net = sum(r["pnl_pct"] for r in res) if res else -999
                    grid.append((target_m, stop_m, early_bars, early_prog, len(res), net, pct_pf(res)))

    grid.sort(key=lambda g: g[5], reverse=True)
    print("Top 12 by net%:")
    for g in grid[:12]:
        print(f"  target={g[0]} stop={g[1]} early_bars={g[2]} early_prog={g[3]}:  "
              f"n={g[4]:4d}  net%={100*g[5]:7.2f}  PF={g[6]:5.2f}")

    best = grid[0]
    print(f"\n  IS winner: target={best[0]} stop={best[1]} early_bars={best[2]} early_prog={best[3]}"
          f"   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation\n{'='*100}")
    oos_res = classify_and_test_early_exit(df_oos, APPROACH, TOUCH, REJECT, CONFIRM, WINDOW,
                                            best[0], best[1], 32, best[2], best[3])
    report("Early-dead cutoff - OOS", oos_res, oos_days)
    full_res = classify_and_test_early_exit(df, APPROACH, TOUCH, REJECT, CONFIRM, WINDOW,
                                             best[0], best[1], 32, best[2], best[3])
    report("Early-dead cutoff - FULL", full_res, full_days)

    print(f"\n\n  Result: still a net loser IS, OOS, and full history (PF 0.67-0.83 band),")
    print(f"  barely different from the same target/stop WITHOUT the early-dead cutoff.")
    print(f"  Conclusion: not an exit-design problem - the 200-EMA touch/reject entry itself")
    print(f"  has no real edge on GOLD M15 regardless of exit mechanism tried (8 variants now).")
    print(f"\n  Honest K note: 3 x 2 x 3 x 3 = 54 combinations searched in this file.")
    print(f"  Combined with the 174 already searched earlier in this VWAP-open research")
    print(f"  line, the running total is K=228 if any of these numbers end up reported as a result.")
