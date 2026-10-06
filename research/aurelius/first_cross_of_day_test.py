"""
NEW CANDIDATE (2026-10-06, user's own idea): is the FIRST 21/50-cross-
triggered entry of each calendar day (server time) better than later
ones on the same day? Classifies Aurelius's own REAL, validated entries
(sim.py's real simulate(), v1.46 shipped defaults - no change to entry/
exit logic, purely a descriptive split of the real trade list) by
whether each entry is the first one Aurelius took that calendar day, or
a subsequent one.

Honest framing: this is a DESCRIPTIVE split of the real trade list, not
a new filter construction - no lookahead risk (the trade already
happened; "was this today's first entry" is knowable in real time, since
it only depends on whether a position has already been opened earlier
today). If "first of day" looks meaningfully better, that's a candidate
worth turning into an actual entry filter (block any entry after the
first one each day) and testing properly with its own walk-forward
split; this file only establishes whether the pattern exists at all,
with a permutation test against random same-size draws from the full
trade list (same discipline as sr_reject_test.py).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
import sim as S
from sr_reject_test import permutation_test


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  avg={pnl.mean():7.3f}")


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    print(f"Real GOLD M5: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars)")
    ctx = E.build_context(df, h4, E.P)

    trades = S.simulate(ctx, params=E.P)
    print(f"Real Aurelius v1.46 trades: n={len(trades)}\n")

    date = df["time"].dt.date.values
    # entry_i is a bar index (close[entry_i-1] triggered, filled next open) -
    # the bar index right before fill, same convention sim.py uses elsewhere
    entry_dates = [date[t["entry_i"]] for t in trades]
    seen = set()
    first_of_day, rest_of_day = [], []
    for t, d in zip(trades, entry_dates):
        if d not in seen:
            first_of_day.append(t)
            seen.add(d)
        else:
            rest_of_day.append(t)

    print(f"{'='*92}\nFIRST ENTRY OF EACH DAY vs SUBSEQUENT ENTRIES SAME DAY\n{'='*92}")
    report("first-of-day", first_of_day)
    report("rest-of-day ", rest_of_day)
    report("ALL (reference)", trades)

    NDRAWS = 2000
    perm = permutation_test(trades, first_of_day, n_draws=NDRAWS)
    print(f"\n{'='*92}\nPERMUTATION TEST: is first-of-day's own net better than a random same-size\n"
          f"draw of trades from Aurelius's own full real trade list?\n{'='*92}")
    if perm is None:
        print("  not enough trades to run this")
    else:
        print(f"  first-of-day real net={perm['real_net']:.2f}  null mean={perm['null_mean']:.2f}  "
              f"null std={perm['null_std']:.2f}")
        print(f"  first-of-day sits at the {perm['percentile']:.1f}th percentile of {NDRAWS} random "
              f"same-size draws from the full trade list")
