"""
Part B (2026-09-26 textbook batch): does any fan / LR-channel / pitchfork
gate IMPROVE Ratchet (real shipped v3.30, sim.SHIPPED)? Gate features and
the walk-forward harness: research/trendbreaker/new_pattern_gate_features.py.

Wired through sim.simulate()'s own RP.entry_filter hook - the sequential
simulator this directory insists on (a rejected entry changes cooldown,
breaker and single-position state for every later entry). Ratchet enters at
bar t's OPEN from bar t-1's closed-bar signal, so the gate reads the feature
row of bar t-1 (the last closed bar) - never bar t.

IS  = load_m5() 2022-07 -> 2026-09 (contains Ratchet's real-report window).
OOS = engine.load_m5_extended() 2014-06-13 -> 2022-07-03 (untouched real M5).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/ratchet")
from dataclasses import replace
import numpy as np
import pandas as pd
import sim as S          # ratchet's sim/bars - imported BEFORE anything that puts
import bars as B         # research/aurelius (which has its own sim.py) on sys.path
sys.path.insert(1, "/home/user/test-project/research/trendbreaker")
import new_pattern_gate_features as G
import engine as E

CUTOFF = pd.Timestamp("2022-07-04")


def make_runner(df, start, end):
    ctx = S.build_ctx(df)
    F = G.map_features(df["time"].values, df["close"].values, 5)

    def run(gate):
        p = S.SHIPPED if gate is None else replace(S.SHIPPED, entry_filter=lambda ctx_, t, d, kind: gate(t - 1, int(d)))
        tr, _ = S.simulate(ctx, p=p, start=start, end=end)
        return [(x["entry_time"], x["pnl"] / x["entry"]) for x in tr]
    return run, F


if __name__ == "__main__":
    m5 = B.load_m5()
    run_is, F_is = make_runner(m5, pd.Timestamp("2022-07-15"), m5["time"].max() + pd.Timedelta(minutes=5))
    m5x = E.load_m5_extended()
    oos = m5x[m5x["time"] < CUTOFF][["time", "open", "high", "low", "close", "tick_volume", "spread"]].reset_index(drop=True)
    run_oos, F_oos = make_runner(oos, pd.Timestamp("2014-07-01"), CUTOFF)
    G.walk_forward("Ratchet v3.30 (M5, sim.SHIPPED)", run_is, run_oos, F_is, F_oos,
                   oos_half_split=np.datetime64("2018-07-01"))
