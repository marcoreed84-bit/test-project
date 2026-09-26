"""
Part B (2026-09-26 textbook batch): does any fan / LR-channel / pitchfork
gate IMPROVE Meridian (real shipped construction, M5)? Gate features and the
walk-forward harness: research/trendbreaker/new_pattern_gate_features.py.

Real trade list = meridian_random_timing_test.build_real()'s exact
construction (21/50 EMA cross + close vs SMA250 + VWAP agreement + S/R
distance >= 0.50xATR, 2.5xATR safety stop, hold to the next opposite cross),
re-built here with ONE extra line: the gate is ANDed into the entry mask at
the cross bar. sim_filtered_entries() is unchanged - a gated-out cross is
simply not entered while it still serves as the exit boundary of whatever
position precedes it, exactly like the shipped filters. Ungated output is
checked identical to build_real() before anything else runs.

IS  = load_m5() 2022-07 -> 2026-09 (Meridian's build window).
OOS = load_m5_extended() 2014-06-13 -> 2022-07-03 (untouched real M5).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from m5_stack_variants_fixed_test import sim_filtered_entries
import meridian_random_timing_test as M
import new_pattern_gate_features as G

CUTOFF = pd.Timestamp("2022-07-04")


def make_runner(df5, h4):
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap, m150 = ctx["vwap"], ctx["m150"]
    sr_b, sr_s = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    m21 = E.ma(close, 21, "ema"); m50 = E.ma(close, 50, "ema")
    above = m21 > m50
    valid = ~np.isnan(m21) & ~np.isnan(m50)
    above_prev = np.concatenate(([False], above[:-1])); valid_prev = np.concatenate(([False], valid[:-1]))
    cross_up = above & ~above_prev & valid & valid_prev
    cross_dn = (~above) & above_prev & valid & valid_prev
    raw = sorted([(i, 1.0) for i in np.where(cross_up)[0]] + [(i, -1.0) for i in np.where(cross_dn)[0]],
                 key=lambda e: e[0])
    base_ok = np.zeros(n, dtype=bool)
    for i, d in raw:
        c150 = (close[i] > m150[i]) if d > 0 else not (close[i] > m150[i])
        cv = (close[i] > vwap[i]) if d > 0 else not (close[i] > vwap[i])
        if not (c150 and cv) or np.isnan(m150[i]):
            continue
        sr = sr_b[i] if d > 0 else sr_s[i]
        base_ok[i] = not (sr >= 0.0 and sr < M.MIN_SR)
    t = df5["time"].values

    def run(gate):
        ok = base_ok
        if gate is not None:
            ok = base_ok.copy()
            for i, d in raw:
                if ok[i] and not gate(i, int(d)):
                    ok[i] = False
        tr = sim_filtered_entries(raw, ok, close, high, low, spread, atr, n, M.SAFETY_SL)
        out = []
        for (i, exit_bar, pnl, is_buy) in tr:
            sc = spread[i + 1] * E.POINT
            entry = close[i] + sc if is_buy else close[i] - sc
            out.append((t[i], pnl / entry))
        return out, tr
    F = G.map_features(df5["time"].values, close, 5)
    return run, F


if __name__ == "__main__":
    h4 = E.load_h4()
    m5 = E.load_m5()
    run_is, F_is = make_runner(m5, h4)
    ref, *_ = M.build_real(m5, h4)
    mine = run_is(None)[1]
    assert mine == ref, "ungated rebuild differs from meridian_random_timing_test.build_real()"
    print(f"ungated rebuild == build_real() ({len(ref)} trades)")
    m5x = E.load_m5_extended()
    m5_oos = m5x[m5x["time"] < CUTOFF].reset_index(drop=True)
    run_oos, F_oos = make_runner(m5_oos, h4)
    G.walk_forward("Meridian (M5)", lambda g: run_is(g)[0], lambda g: run_oos(g)[0], F_is, F_oos,
                   oos_half_split=np.datetime64("2018-07-01"))
