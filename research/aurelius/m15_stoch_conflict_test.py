"""
User's observation (2026-09-25, live account): Aurelius fires a real M5
sell trigger while the M15 stochastic is already oversold and "ready to go
up" - and the M15 read "usually wins the race" (i.e. price turns up and
the M5 sell loses). This is a genuinely different question from
mtf_stoch_test.py (which tested a *standalone* M5-turn + M15-context
system, aligned in the SAME direction, and was never wired into Aurelius
at all) - here the question is whether Aurelius's OWN real, already-
shipped M5 entries do worse specifically when the M15 stochastic is
already extended AGAINST the trade at the moment of entry.

Method: run the real EA-faithful simulator (sim.py, matches 471/473 real
MT5 entries to the bar) to get Aurelius's actual real M5 trade list, then
tag each entry with the M15 stochastic value as of that moment (same
no-lookahead merge_asof alignment as mtf_stoch_test.py - each M5 bar
matched to the most recently CLOSED M15 bar). Split trades into
"conflict" (M15 %K <= thresh for a sell entry / >= 100-thresh for a buy
entry - i.e. M15 already extended the OTHER way) vs the rest, and compare
real win rate / PF / avg pnl, with a chronological 70/30 walk-forward
split on both groups.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from sim import simulate, stats
from stoch_speed_test import stochastic

np.random.seed(42)


def tag_trades(trades, k15_at_m5):
    for t in trades:
        t["k15"] = k15_at_m5[t["entry_i"]]
    return trades


def report(trades, label):
    if len(trades) < 8:
        print(f"    {label}: only {len(trades)} trades - too few to conclude anything")
        return
    s = stats(trades)
    print(f"    {label}: n={s['n']} net={s['net']:.2f} win%={100*s['win_rate']:.1f} "
          f"pf={s['pf']:.3f} avg_win={s['avg_win']:.2f} avg_loss={s['avg_loss']:.2f}")


def walk_forward(trades, n, label):
    if len(trades) < 8:
        print(f"    {label}: too few for walk-forward")
        return
    order = sorted(trades, key=lambda t: t["entry_i"])
    cutoff = int(n * 0.7)
    is_t = [t for t in order if t["entry_i"] < cutoff]
    oos_t = [t for t in order if t["entry_i"] >= cutoff]
    report(is_t, f"{label} IN-SAMPLE ")
    report(oos_t, f"{label} OUT-OF-SAMPLE")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]

    trades = simulate(ctx, params=E.P)
    print(f"Aurelius real-faithful baseline: {len(trades)} trades\n")

    # M15 stochastic, aligned to each M5 bar via the most recently CLOSED
    # M15 bar (no lookahead) - identical convention to mtf_stoch_test.py
    df15 = E.resample_m15_from_m5(df5)
    c15, h15, l15 = df15["close"].values, df15["high"].values, df15["low"].values
    k15 = stochastic(h15, l15, c15, period=14, smooth=3)
    m15_close_time = df15["time"] + pd.Timedelta(minutes=15)
    m15_lookup = pd.DataFrame({"close_time": m15_close_time, "k15": k15}).sort_values("close_time")
    m5_times = pd.DataFrame({"time": df5["time"].values})
    merged = pd.merge_asof(m5_times, m15_lookup, left_on="time", right_on="close_time", direction="backward")
    k15_at_m5 = merged["k15"].values

    trades = tag_trades(trades, k15_at_m5)

    for thresh in (20.0, 30.0):
        print("=" * 78)
        print(f"M15 conflict threshold: oversold <= {thresh} / overbought >= {100-thresh}")
        conflict = []
        clear = []
        excluded_nan = 0
        for t in trades:
            k = t["k15"]
            if np.isnan(k):
                excluded_nan += 1
                continue
            is_buy = t["dir"] > 0
            is_conflict = (k >= 100 - thresh) if is_buy else (k <= thresh)
            (conflict if is_conflict else clear).append(t)
        print(f"  ({excluded_nan} trades excluded - no valid M15 stochastic at entry)")
        report(conflict, "CONFLICT (M15 extended against the trade)")
        report(clear, "CLEAR    (M15 not extended against the trade)")
        print("  walk-forward, chronological 70/30 by entry bar:")
        walk_forward(conflict, n, "  CONFLICT")
        walk_forward(clear, n, "  CLEAR   ")
        print()
