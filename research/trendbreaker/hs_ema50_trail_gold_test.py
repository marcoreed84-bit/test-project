"""
Gold version of hs_ema50_trail_test.py - the 50-EMA trail exit found a
real, consistent trade-off on Silver (win% 43.9->52.9, PF 1.882->2.985,
but net% 361.62->295.99 lower) on H&S's own real validated entries. This
checks whether the same trade-off shape holds on Gold, or whether it's
Silver-specific - no assumption either way.

Real GOLD M15 data, 2014-06-13 onward only (real M15 data gotcha - before
that it's daily/hourly bars mislabeled as M15, per this project's own
known data gotcha). Same construction as the Silver version: H&S's real
pullback/retest entry unchanged, only the exit replaced.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
from hs_next_round_test import find_breakouts_full, eval_pullback_and_runner
from hs_stacked_random_baseline_test import RETEST_TOL, RETEST_WINDOW, BREAK_TOL
from hs_ema50_trail_test import ema, eval_ema50_trail, pct_pf, report

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
GOLD_M15_REAL_START = pd.Timestamp("2014-06-13")
STOP_BUFFER = 0.35
TRAIL_BUFFER_ATR = 0.15


def load_gold_m15():
    df = pd.read_csv(f"{DATA_DIR}/GOLD_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df.sort_values("time").reset_index(drop=True)
    df = df[df["time"] >= GOLD_M15_REAL_START].reset_index(drop=True)
    return df


if __name__ == "__main__":
    m15 = load_gold_m15()
    print(f"GOLD M15 real: {m15['time'].iloc[0]} .. {m15['time'].iloc[-1]} ({len(m15)} bars)\n")

    breakouts, h, l, c, atr = find_breakouts_full(m15, break_tol=BREAK_TOL)
    m50 = ema(c, 50)
    n = len(c)
    cutoff_q = int(n * 0.70)

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
