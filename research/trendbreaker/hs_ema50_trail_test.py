"""
User's real idea, properly grounded this time: both chart examples shown
tonight were H&S patterns specifically, not a context-free cross anywhere
- meaning the 21/50 cross in those screenshots is happening WITHIN an
already-validated H&S setup (real edge, bar-matched, survives random-
timing on Silver, p=0.01). This takes H&S's own real, validated ENTRY
(the pullback/retest-to-neckline logic in eval_pullback_and_runner_pct,
UNCHANGED) and replaces ONLY the exit: instead of the fixed target +
ATR-trail-after-target, exit when price closes back through the 50-EMA
by a small buffer, active from bar one (not gated behind first reaching
the target) - exactly the "trail the 50-EMA, allow a brief push through,
real close beyond it" mechanism already tested elsewhere tonight.

Restricted to the clean 2014-2025 Silver M15 window (2026 portion has a
known data-quality problem, confirmed earlier this session).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
from hs_next_round_test import find_breakouts_full
from hs_stacked_random_baseline_test import RETEST_TOL, RETEST_WINDOW, BREAK_TOL

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
CLEAN_END = pd.Timestamp("2025-12-31")
STOP_BUFFER = 0.35
TRAIL_BUFFER_ATR = 0.15


def load_m15_silver():
    df = pd.read_csv(f"{DATA_DIR}/SILVER_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    df = df[df["time"] <= CLEAN_END].reset_index(drop=True)
    return df


def ema(arr, period):
    out = np.full(len(arr), np.nan)
    alpha = 2.0 / (period + 1)
    out[period - 1] = np.mean(arr[:period])
    for i in range(period, len(arr)):
        out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
    return out


def eval_ema50_trail(breakouts, h, l, c, m50, stop_buffer, retest_tol_atr, retest_window, trail_buffer_atr):
    results, last_exit, missed = [], -1, 0
    for b in breakouts:
        top, brk_q = b["top"], b["brk_q"]
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
        stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        atrv = b["atr_at_brk"]
        exit_bar, exit_px = None, None
        for k in range(entry_bar + 1, b["max_horizon"] + 1):
            hit_stop = (h[k] >= stop) if top else (l[k] <= stop)
            if hit_stop:
                exit_bar, exit_px = k, stop
                break
            if np.isnan(m50[k]):
                continue
            buf = trail_buffer_atr * atrv
            cl = c[k]
            broke = (cl > m50[k] + buf) if top else (cl < m50[k] - buf)
            if broke:
                exit_bar, exit_px = k, cl
                break
        if exit_bar is None:
            exit_bar, exit_px = b["max_horizon"], c[min(b["max_horizon"], len(c) - 1)]
        pnl = (entry - exit_px) if top else (exit_px - entry)
        pnl_pct = pnl / entry
        results.append(dict(brk_q=entry_bar, top=top, pnl=pnl, pnl_pct=pnl_pct))
        last_exit = exit_bar
    return results, missed


def pct_pf(results):
    arr = np.array([r["pnl_pct"] for r in results])
    gw = arr[arr > 0].sum()
    gl = -arr[arr <= 0].sum()
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
    print(f"SILVER M15, clean window: {m15['time'].iloc[0]} .. {m15['time'].iloc[-1]} ({len(m15)} bars)\n")

    breakouts, h, l, c, atr = find_breakouts_full(m15, break_tol=BREAK_TOL)
    m50 = ema(c, 50)
    n = len(c)
    cutoff_q = int(n * 0.70)

    from hs_next_round_test import eval_pullback_and_runner
    real, missed_real = eval_pullback_and_runner(breakouts, h, l, c, STOP_BUFFER, RETEST_TOL, RETEST_WINDOW, 0.5)
    real_pct = [dict(brk_q=r["brk_q"], pnl_pct=r["pnl"] / c[max(0, r["brk_q"]-1)]) for r in real]

    cand, missed_cand = eval_ema50_trail(breakouts, h, l, c, m50, STOP_BUFFER, RETEST_TOL, RETEST_WINDOW, TRAIL_BUFFER_ATR)

    print(f"{'='*92}\nBASELINE: real H&S stacked combo (target + ATR-trail-after-target)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [r for r in real_pct if r["brk_q"] < cutoff_q])
    report("OUT-OF-SAMPLE (last 30%)", [r for r in real_pct if r["brk_q"] >= cutoff_q])
    report("FULL HISTORY", real_pct)

    print(f"\n{'='*92}\nCANDIDATE: same entry, 50-EMA trail exit from bar one (buffer={TRAIL_BUFFER_ATR} ATR)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [r for r in cand if r["brk_q"] < cutoff_q])
    report("OUT-OF-SAMPLE (last 30%)", [r for r in cand if r["brk_q"] >= cutoff_q])
    report("FULL HISTORY", cand)

    print(f"\n  Honest K=1 (single pre-specified construction, buffer not swept).")
