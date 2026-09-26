"""
Part B (2026-09-26 textbook batch): does any fan / LR-channel / pitchfork
gate IMPROVE Aurelius M5 (engine.P) or Aurelius M15 (engine.P15)? Gate
features and the walk-forward harness live in
research/trendbreaker/new_pattern_gate_features.py (gate list, causal H4
mapping, fixed IS-selection rule, count-matched random-rejection null).

Wired through sim.simulate()'s own extra_filter hook (decision bar i, same
place every earlier Aurelius filter candidate was tested), so a rejected
entry genuinely frees the single position slot for a different later entry
- never a row-deletion on a finished trade list.

IS  = the window both variants were built/tuned on:
      M5  -> load_m5() 2022-07 -> 2026-09
      M15 -> resample_m15_from_m5(load_m5()) 2022-07 -> 2026-09
OOS = genuinely untouched real bars:
      M5  -> load_m5_extended() 2014-06-13 -> 2022-07-03
      M15 -> load_m15_native() 2014-06-13 01:30 -> 2022-07-03 (real M15 only)
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from sim import simulate
import pattern_rigor_common as R
import new_pattern_gate_features as G

CUTOFF = pd.Timestamp("2022-07-04")


def make_runner(df, h4, params, bar_minutes):
    ctx = E.build_context(df, h4, params)
    t = ctx["time"]
    F = G.map_features(df["time"].values, df["close"].values, bar_minutes)

    def run(gate):
        f = None if gate is None else (lambda ctx_, i, is_buy: gate(i, 1 if is_buy else -1))
        tr = simulate(ctx, extra_filter=f, params=params)
        return [(t[x["entry_i"]], (x["exit_px"] - x["entry_px"]) * x["dir"] / x["entry_px"]) for x in tr]
    return run, F


if __name__ == "__main__":
    h4 = E.load_h4()
    m5 = E.load_m5()
    m5x = E.load_m5_extended()
    m5_oos = m5x[m5x["time"] < CUTOFF].reset_index(drop=True)
    run_is, F_is = make_runner(m5, h4, E.P, 5)
    run_oos, F_oos = make_runner(m5_oos, h4, E.P, 5)
    s5 = G.walk_forward("Aurelius M5 (engine.P)", run_is, run_oos, F_is, F_oos,
                        oos_half_split=np.datetime64("2018-07-01"))

    m15_is = E.resample_m15_from_m5(m5)
    m15n = E.load_m15_native()
    m15_oos = m15n[(m15n["time"] >= R.REAL_M15_START) & (m15n["time"] < CUTOFF)].reset_index(drop=True)
    run_is, F_is = make_runner(m15_is, h4, E.P15, 15)
    run_oos, F_oos = make_runner(m15_oos, h4, E.P15, 15)
    s15 = G.walk_forward("Aurelius M15 (engine.P15)", run_is, run_oos, F_is, F_oos,
                         oos_half_split=np.datetime64("2018-07-01"))
