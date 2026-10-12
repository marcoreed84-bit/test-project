"""
Silver-specific InpMaxSpreadPoints search for H&S, since Silver's real
spread regime shifted hard in 2026 (median 33->60, 82% of 2026 bars >50,
confirmed directly from SILVER_M15_native.csv) - the 50-point threshold
set earlier tonight was validated on GOLD data only and would reject the
vast majority of Silver entries right now. This fixes that properly:
search thresholds on IN-SAMPLE ONLY, confirm the winner on untouched OOS,
same discipline as the volume-threshold search done earlier tonight for
Fulcrum.

Tests against H&S's REAL SHIPPED exit mechanism (target + ATR-trail-
after-target via eval_pullback_and_runner, UNCHANGED) - this is about
the entry-side spread gate, not the new trail-50 exit idea (that's a
separate, still-unconfirmed-on-Gold experiment).

Spread filter added at the entry bar (pullback/retest touch bar) since
hs_next_round_test.py's real construction doesn't model one - the real
MQL5 EA checks live spread at the moment it would place the order, which
corresponds to the touch/confirm bar here.

Full real Silver history (2014-06-12 onward, no 2026 exclusion this time
- the shifted spread level is exactly what we need to search over, this
isn't a data-corruption issue like the earlier bar-range one).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
from hs_next_round_test import find_breakouts_full
from hs_stacked_random_baseline_test import RETEST_TOL, RETEST_WINDOW, BREAK_TOL

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
STOP_BUFFER = 0.35
TRAIL_MULT = 0.5


def load_m15_silver():
    df = pd.read_csv(f"{DATA_DIR}/SILVER_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True)


def eval_with_spread(breakouts, h, l, c, spread_col, stop_buffer, retest_tol_atr, retest_window,
                      trail_atr_mult, max_spread):
    results, last_exit, missed, spread_blocked = [], -1, 0, 0
    for b in breakouts:
        top, brk_q, target = b["top"], b["brk_q"], b["target"]
        if brk_q < last_exit:
            continue
        tol = retest_tol_atr * b["atr_at_brk"]
        entry_bar, entry = None, None
        for q in range(brk_q + 1, min(brk_q + 1 + retest_window, b["max_horizon"])):
            nl = b["neckline_at"](q)
            touched = (h[q] >= nl - tol) if top else (l[q] <= nl + tol)
            if touched:
                entry_bar, entry = q, nl
                break
        if entry_bar is None:
            missed += 1
            continue
        if max_spread > 0 and spread_col[entry_bar] > max_spread:
            spread_blocked += 1
            continue
        stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        atrv = b["atr_at_brk"]
        cur_stop = stop
        exit_bar, exit_px = None, None
        reached_target = False
        peak = entry
        for k in range(entry_bar + 1, b["max_horizon"] + 1):
            hit_stop = (h[k] >= cur_stop) if top else (l[k] <= cur_stop)
            if hit_stop:
                exit_bar, exit_px = k, cur_stop
                break
            hit_target = (l[k] <= target) if top else (h[k] >= target)
            if hit_target and not reached_target:
                reached_target = True
                peak = target
            if reached_target:
                if top:
                    peak = min(peak, l[k])
                    cur_stop = min(cur_stop, peak + trail_atr_mult * atrv)
                else:
                    peak = max(peak, h[k])
                    cur_stop = max(cur_stop, peak - trail_atr_mult * atrv)
        if exit_bar is None:
            exit_bar, exit_px = b["max_horizon"], c[min(b["max_horizon"], len(c) - 1)]
        pnl = (entry - exit_px) if top else (exit_px - entry)
        results.append(dict(brk_q=entry_bar, pnl_pct=pnl / entry))
        last_exit = exit_bar
    return results, missed, spread_blocked


def pct_pf(results):
    arr = np.array([r["pnl_pct"] for r in results])
    gw, gl = arr[arr > 0].sum(), -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, results):
    if not results:
        print(f"  {label}: n=0")
        return
    arr = np.array([r["pnl_pct"] for r in results])
    print(f"  {label}: n={len(results):4d}  win%={100*(arr>0).mean():5.1f}  %PF={pct_pf(results):6.3f}  "
          f"net%={100*arr.sum():7.2f}")


if __name__ == "__main__":
    m15 = load_m15_silver()
    print(f"SILVER M15 real: {m15['time'].iloc[0]} .. {m15['time'].iloc[-1]} ({len(m15)} bars)\n")
    breakouts, h, l, c, atr = find_breakouts_full(m15, break_tol=BREAK_TOL)
    spread_col = m15["spread"].values
    n = len(c)
    cutoff_q = int(n * 0.70)

    print(f"{'='*92}\nIN-SAMPLE-ONLY SEARCH over max-spread thresholds\n{'='*92}")
    is_results = {}
    for thr in (0, 50, 55, 60, 65, 70, 75, 80, 90, 100):
        res, missed, blocked = eval_with_spread(breakouts, h, l, c, spread_col, STOP_BUFFER,
                                                   RETEST_TOL, RETEST_WINDOW, TRAIL_MULT, thr)
        is_res = [r for r in res if r["brk_q"] < cutoff_q]
        is_results[thr] = is_res
        label = f"thr={thr if thr>0 else 'OFF':>4}"
        print(f"  {label}: IS n={len(is_res):4d}  %PF={pct_pf(is_res):6.3f}  "
              f"net%={100*sum(r['pnl_pct'] for r in is_res):7.2f}  (blocked {blocked} total)")

    best_thr = max(is_results, key=lambda t: sum(r["pnl_pct"] for r in is_results[t]) if is_results[t] else -1e9)
    print(f"\n  IS winner (by net%): threshold={best_thr}\n")

    print(f"{'='*92}\nCONFIRM on untouched OOS: shipped (no filter) vs IS-winning threshold vs original 60\n{'='*92}")
    for thr, label in [(0, "no filter (shipped default)"), (60, "original 60"), (best_thr, f"IS-winner {best_thr}")]:
        res, missed, blocked = eval_with_spread(breakouts, h, l, c, spread_col, STOP_BUFFER,
                                                   RETEST_TOL, RETEST_WINDOW, TRAIL_MULT, thr)
        report(f"{label} - IS ", [r for r in res if r["brk_q"] < cutoff_q])
        report(f"{label} - OOS", [r for r in res if r["brk_q"] >= cutoff_q])
        report(f"{label} - ALL", res)
        print()
