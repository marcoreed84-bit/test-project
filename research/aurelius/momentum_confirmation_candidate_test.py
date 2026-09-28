"""
A higher-win-rate Aurelius M5 candidate, built at the user's request after
watching two same-direction stop-outs in one day. Rather than invent a new
mechanism, this tests one that ALREADY EXISTS in both the real EA
(Aurelius_EA.mq5's MomentumShiftOK(), ~line 2348) and this Python engine
(engine.py's use_momentum/macd_* params, sim.py lines 297-310) but ships
OFF by default: require the MACD histogram to have JUST turned in the
trade's favour (was falling, now rising for buys - confirming momentum is
shifting right at entry) on top of every existing filter (alignment,
pullback, slope, volume, S/R distance, cross-count). Aurelius_EA.mq5's own
header (~line 2351) already quotes a real, but never walk-forward-tested,
number for this: "PF rises from 2.45 to 3.13, win rate 38.6% -> 46.0%, max
drawdown roughly halved, at the cost of about half the total trade count
and profit."

This file puts that specific number through the SAME rigor pipeline as
everything else in research/aurelius/ - the untouched 2014-2022 slice
(kept_ea_untouched_oos_check.py's aurelius_block, unmodified) PLUS the
2022-2026 build window the header's own number came from, so the
candidate's win-rate/PF/net trade-off can be judged on data it never
touched, not just the window it may have been eyeballed against.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from sim import simulate
import aurelius_random_timing_test as A
from kept_ea_untouched_oos_check import aurelius_block, CUTOFF

BUILD_START = CUTOFF   # 2022-07-04 - the in-sample/build window every earlier "survives" claim used


def build_window_check(label, df, h4, params, start, end=None):
    ctx = E.build_context(df, h4, params)
    t = ctx["time"]
    lo = int(np.searchsorted(t.values, np.datetime64(start)))
    hi = len(t) if end is None else int(np.searchsorted(t.values, np.datetime64(end)))
    real = simulate(ctx, params=params)
    real = [x for x in real if lo <= x["entry_i"] < hi]
    pcts = [(x["exit_px"] - x["entry_px"]) * x["dir"] / x["entry_px"] for x in real]
    pcts = np.array(pcts)
    gw, gl = pcts[pcts > 0].sum(), -pcts[pcts <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    print(f"{label}: n={len(pcts)}  win%={100*(pcts>0).mean():.1f}  %PF={pf:.3f}  net%={100*pcts.sum():.1f}")
    return real


if __name__ == "__main__":
    h4 = E.load_h4()
    m5x = E.load_m5_extended()
    m5_untouched = m5x[m5x["time"] < CUTOFF].reset_index(drop=True)
    m5_build = m5x[m5x["time"] >= BUILD_START].reset_index(drop=True)

    base = dict(E.P)
    cand = dict(E.P, use_momentum=True)

    print("=" * 90)
    print("2022-2026 BUILD WINDOW (the window Aurelius_EA.mq5's header quoted PF 2.45->3.13 / win 38.6->46.0 from)")
    print("=" * 90)
    build_window_check("baseline (use_momentum=False, shipped)", m5_build, h4, base, BUILD_START)
    build_window_check("candidate (use_momentum=True)          ", m5_build, h4, cand, BUILD_START)

    print("\n" + "=" * 90)
    print("UNTOUCHED 2014-06 -> 2022-07 WINDOW (never seen by any tuning decision)")
    print("=" * 90)
    print("--- baseline (use_momentum=False, shipped) ---")
    aurelius_block("Aurelius M5 baseline - untouched", m5_untouched, h4, base)
    print("\n--- candidate (use_momentum=True) ---")
    aurelius_block("Aurelius M5 + momentum confirmation - untouched", m5_untouched, h4, cand)
