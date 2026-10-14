"""
Sixth construction. Direct steer: the 200-EMA ITSELF is the entry trigger -
price approaches the 200-EMA from one side, touches it, then rejects back
to the side it came from. Entry = the rejection bounce, direction = the
side price came from (continuation of the pre-touch trend). VWAP is no
longer part of the entry condition at all in this construction - dropped
per the explicit redirect to "200ema touch/rejection as the entry trigger
itself".

Sequence, all causal (no future information used):
  1. "Approach": price sits on one side of the 200-EMA, beyond
     approach_atr_mult*ATR, for at least one bar (establishes which side it
     came from).
  2. "Touch": price closes within touch_atr_mult*ATR of the 200-EMA.
  3. "Reject": within confirm_bars bars of the touch, price closes back to
     the ORIGINAL side, beyond reject_atr_mult*ATR - this confirms the
     bounce. Entry direction = the original (pre-touch) side.

Exit: real-time rule - 50-EMA close-back (opposite direction), or a time
cap, whichever first. Variable hold, not forced.

Per direct instruction, long and short trades are reported SEPARATELY, not
just pooled - if one direction is a net loser while the other is a net
winner, that is itself the finding (take the winning side only / fade the
losing side), not something to average away.

Early-morning window kept (same as rest of this research line) since the
original observation was about session-open behavior specifically, but this
file's grid also tests the full trading day (not just the first 8h) since
a 200-EMA touch/reject is not inherently a session-open-only event - worth
knowing whether restricting to the open actually helps or just cuts sample.

Same real GOLD_M15_native.csv (2014-06-13+), real spread, IS/OOS split,
honest K continued (94 before this file).
"""
import numpy as np
import pandas as pd
from vwap_open_scenarios_test import load_gold_m15, ema, wilder_atr, GOLD_POINT

HOLD_BARS_TOUCH = 32  # 8h cap, variable hold in practice


def classify_and_test_touch(df, approach_mult, touch_mult, reject_mult, confirm_bars,
                             window_bars, point=GOLD_POINT):
    close, high, low = df["close"].values, df["high"].values, df["low"].values
    spread = df["spread"].values
    m50 = ema(close, 50)
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
                    if fill_i < n:
                        sc = spread[fill_i] * point
                        entry_px = close[fill_i] + (sc if direction > 0 else -sc)

                        exit_i, exit_px, reason = None, None, None
                        hard_limit = min(fill_i + HOLD_BARS_TOUCH, n - 1)
                        for k in range(fill_i, hard_limit + 1):
                            if np.isnan(m50[k]):
                                continue
                            broke = (close[k] < m50[k]) if direction > 0 else (close[k] > m50[k])
                            if broke:
                                exit_i, exit_px, reason = k, close[k], "EMA50"
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

    print(f"{'='*100}\nIN-SAMPLE grid search (200-EMA touch + rejection, early-window only)\n{'='*100}")
    grid = []
    for window_bars in (32,):  # early 8h window only - dropped full-day variant, too slow in pure python at this bar count, and the original observation was about session open anyway
        for approach_m in (0.5, 1.0):
            for touch_m in (0.15, 0.25):
                for reject_m in (0.2, 0.3, 0.4):
                    for confirm_b in (4, 8):
                        res = classify_and_test_touch(df_is, approach_m, touch_m, reject_m, confirm_b, window_bars)
                        net = sum(r["pnl_pct"] for r in res) if res else -999
                        grid.append((approach_m, touch_m, reject_m, confirm_b, window_bars, len(res), net, pct_pf(res)))
                        print(f"    approach={approach_m} touch={touch_m} reject={reject_m} confirm={confirm_b}:  "
                              f"n={len(res):4d}  net%={100*net:7.2f}  PF={pct_pf(res):5.2f}  ~{len(res)/(is_days/30.44):.1f}/mo",
                              flush=True)

    grid.sort(key=lambda g: g[6], reverse=True)
    print("\n  Top 10 by net%:")
    for g in grid[:10]:
        print(f"    approach={g[0]} touch={g[1]} reject={g[2]} confirm={g[3]}:  "
              f"n={g[5]:4d}  net%={100*g[6]:7.2f}  PF={g[7]:5.2f}  ~{g[5]/(is_days/30.44):.1f}/mo")

    best = grid[0]
    print(f"\n  IS winner: approach={best[0]} touch={best[1]} reject={best[2]} confirm={best[3]} window={best[4]}"
          f"   (K={len(grid)} combinations searched)")

    print(f"\n{'='*100}\nOUT-OF-SAMPLE confirmation (pooled, then split long/short)\n{'='*100}")
    oos_res = classify_and_test_touch(df_oos, best[0], best[1], best[2], best[3], best[4])
    report("200EMA touch/reject - OOS", oos_res, oos_days, split_dir=True)
    full_res = classify_and_test_touch(df, best[0], best[1], best[2], best[3], best[4])
    report("200EMA touch/reject - FULL", full_res, full_days, split_dir=True)

    print(f"\n\n  Honest K note: 2 x 2 x 3 x 2 = 24 combinations searched in this file")
    print(f"  (early-window only - the full-day variant was dropped, too slow in pure python).")
    print(f"  Combined with the 94 already searched earlier in this VWAP-open research")
    print(f"  line, the running total is K=142 if any of these numbers end up reported as a result.")
