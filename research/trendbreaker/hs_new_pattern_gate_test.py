"""
Part B (textbook batch): does any fan / LR-channel / pitchfork gate IMPROVE
HeadShoulders_EA's real shipped v1.08 stacked combo? Gate features and the
walk-forward harness: new_pattern_gate_features.py (read its docstring for
the gate list and the fixed selection rule).

Real trade list = hs_stacked_random_baseline_test.eval_pullback_and_runner_pct
(unchanged) on hs_next_round_test.find_breakouts_full() - which is now the
causal, EA-faithful detector (see hs_causal_detection_check.py). The gate is
evaluated ONCE per confirmed breakout, at the confirmation bar - the same bar
HeadShoulders_EA's own existing RSIFilterOk() reads - and a rejected pattern
is simply never traded (so it doesn't occupy the single position slot;
eval_pullback_and_runner_pct's own last_exit sequencing does the rest).

IS  = 2022-07 -> 2026-09 M15 (resampled real M5) - the window H&S was built on.
OOS = native M15 2014-06-13 -> 2022-07-03 (real M15 bars only) - untouched.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
import pattern_rigor_common as R
import new_pattern_gate_features as G
from hs_next_round_test import find_breakouts_full, STOP_BUFFER
import hs_stacked_random_baseline_test as H

CUTOFF = pd.Timestamp("2022-07-04")


def make_runner(df):
    b, h, l, c, atr = find_breakouts_full(df, break_tol=H.BREAK_TOL)
    times = df["time"].values

    def run(gate):
        bb = b if gate is None else [x for x in b if gate(x["brk_q"], -1 if x["top"] else 1)]
        res, _ = H.eval_pullback_and_runner_pct(bb, h, l, c, STOP_BUFFER, H.RETEST_TOL, H.RETEST_WINDOW, H.TRAIL_MULT)
        return [(times[r["brk_q"]], r["pnl_pct"]) for r in res]
    F = G.map_features(df["time"].values, df["close"].values, 15)
    return run, F


if __name__ == "__main__":
    is_df = E.resample_m15_from_m5(E.load_m5())
    m15 = E.load_m15_native()
    oos_df = m15[(m15["time"] >= R.REAL_M15_START) & (m15["time"] < CUTOFF)].reset_index(drop=True)
    run_is, F_is = make_runner(is_df)
    run_oos, F_oos = make_runner(oos_df)
    G.walk_forward("H&S stacked combo v1.08 (M15)", run_is, run_oos, F_is, F_oos,
                   oos_half_split=np.datetime64("2018-07-01"))
