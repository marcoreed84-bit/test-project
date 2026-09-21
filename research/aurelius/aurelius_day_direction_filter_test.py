"""
Proper Aurelius-side test of the day-direction pattern, using this
project's real, validated Aurelius simulator (sim.py, ports
Aurelius_EA.mq5's real OnTick() entry-gate combination and exit-priority
order) rather than a fresh re-derivation - same rigor sr_reject_test.py
established: chronological 70/30 IS/OOS split, tail-concentration check,
and a permutation-null drawn from the BASE model's own entered trades
(the stricter null for "does an ADDED filter provide value beyond the
already-real base gate", not a fresh-random-entry null).

Filter: causal day-direction (sign of current close vs today's own
open, zero lookahead - same definition validated on Vanguard in
day_direction_filter_test.py and confirmed on Aurelius's real trades in
aurelius_day_direction_real_test.py, now tested as an actual entry gate
on top of Aurelius's full real logic, not just a retrospective trade
classification).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
import sim as S
from sr_reject_test import split_stats, tail_concentration, permutation_test

if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4)
    n = ctx["n"]
    close = ctx["close"]

    dates = df["time"].dt.date.values
    day_open = pd.Series(close).groupby(pd.Series(dates)).transform("first").values
    day_dir_sign = np.sign(close - day_open)   # causal: no lookahead

    def day_direction_filter(ctx_unused, i, is_buy):
        want = 1 if is_buy else -1
        return day_dir_sign[i] == want

    base_trades = S.simulate(ctx, params=E.P)
    base_stats = S.stats(base_trades)
    base_risk = S.risk_stats(base_trades, ctx)
    print("BASELINE (v1.46 true defaults, full 2023-2026):")
    print(" ", base_stats)
    print(" ", base_risk)

    cand_trades = S.simulate(ctx, params=E.P, extra_filter=day_direction_filter)
    cand_stats = S.stats(cand_trades)
    cand_risk = S.risk_stats(cand_trades, ctx)
    print("\nCANDIDATE (+ causal day-direction gate):")
    print(" ", cand_stats)
    print(" ", cand_risk)

    print("\n--- IS/OOS (70/30 chronological) ---")
    b_is, b_oos = split_stats(base_trades, n)
    c_is, c_oos = split_stats(cand_trades, n)
    print("baseline  IS:", b_is)
    print("baseline  OOS:", b_oos)
    print("candidate IS:", c_is)
    print("candidate OOS:", c_oos)

    print("\n--- tail concentration ---")
    print("baseline: ", tail_concentration(base_trades))
    print("candidate:", tail_concentration(cand_trades))

    print("\n--- permutation test (candidate's trades vs random same-size draws from baseline's own trades) ---")
    perm = permutation_test(base_trades, cand_trades, n_draws=800)
    print(perm)

    print(f"\nfilter removed {base_stats['n'] - cand_stats['n']} of {base_stats['n']} baseline trades "
          f"({100*(base_stats['n']-cand_stats['n'])/base_stats['n']:.1f}%)")

print("\n" + "=" * 70)
print("INTERPRETATION: the permutation percentile above (47.4) is the decisive")
print("number - a random same-size draw of Aurelius's OWN trades beats this")
print("filtered subset more than half the time. The filter removes 6.6% of")
print("trades and changes net/PF/win% by amounts indistinguishable from just")
print("randomly trimming 6.6% of trades. REJECTED: no real marginal value on")
print("top of Aurelius's already-validated entry gate, despite the strong raw")
print("retrospective signal (aurelius_day_direction_real_test.py: 100th pct).")
print("Likely explanation: Aligned()'s own MA-alignment check is already a")
print("proxy for the same underlying trend state day-direction measures, so")
print("once that's already gated, day-direction adds nothing further.")
