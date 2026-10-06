"""
Same early-exit idea validated on Meridian (research/meridian/
early_exit_break_test.py), checked on Ratchet - per the user's explicit
request to check it across every EA, not just Meridian. Ratchet's own
m21/m50 EMAs (already computed in sim.py's build_ctx) are the same
structure used here, same thresholds, no re-tuning.

RULE (identical construction/thresholds to the Meridian and Aurelius
versions): once price FIRST comes back within 0.30xATR of either the 21
or 50 EMA after entry (no fixed window), every bar after that touch is
checked for resolution - bounce back above/below BOTH EMAs keeps the
trade open (rule never fires again this trade); breaking through BOTH
closes the trade immediately, ahead of whatever Ratchet's own exit chain
would have done.

Implemented via sim.py's own exit_fn research hook (identical mechanism
to msim.py's). Entry, stop, and every other exit rule unchanged - single-
variable swap vs shipped Ratchet defaults. Full real GOLD M5 history
(not the narrow 2026 real-MT5-validation window), walk-forward 70/30
split. Honest K=1 (same pre-specified rule/thresholds as the other two
EAs, no re-tuning for this one).
"""
import sys

import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import numpy as np
import sim as S

RETEST_TOL_ATR = 0.30


def make_early_exit_fn(ctx):
    c, m21, m50, atr = ctx["c"], ctx["m21"], ctx["m50"], ctx["atr"]

    def fn(ctx_, t, pos):
        d = pos["dir"]
        entry_i = pos["entry_i"]
        touched_i = None
        for k in range(entry_i + 1, t + 1):
            a = atr[k]
            if not (a > 0):
                continue
            if touched_i is None:
                tol = RETEST_TOL_ATR * a
                if (abs(c[k] - m21[k]) <= tol) or (abs(c[k] - m50[k]) <= tol):
                    touched_i = k
                continue
            bounced = (c[k] > m21[k] and c[k] > m50[k]) if d > 0 else (c[k] < m21[k] and c[k] < m50[k])
            broke = (c[k] < m21[k] and c[k] < m50[k]) if d > 0 else (c[k] > m21[k] and c[k] > m50[k])
            if bounced:
                return None
            if broke:
                return "EARLY_EXIT_BROKE" if k == t else None
        return None
    return fn


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  avg={pnl.mean():7.3f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


if __name__ == "__main__":
    ctx = S.build_ctx()
    n_bars = len(ctx["t64"])
    cutoff = int(n_bars * 0.70)
    cutoff_time = pd.Timestamp(ctx["t64"][cutoff])
    full_start, full_end = pd.Timestamp(ctx["t64"][0]), pd.Timestamp(ctx["t64"][-1])
    print(f"GOLD M5 real data: {full_start} .. {full_end}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {cutoff_time}\n")

    p_candidate = S.replace(S.SHIPPED, exit_fn=make_early_exit_fn(ctx))

    print(f"{'='*92}\nSHIPPED Ratchet + early-exit-on-break rule (candidate)\n{'='*92}")
    for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        trades = S.simulate(ctx, p_candidate, start=start, end=end)
        report(label, trades)

    print(f"\n{'='*92}\nFor reference: shipped Ratchet (no early-exit rule)\n{'='*92}")
    for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        trades = S.simulate(ctx, S.SHIPPED, start=start, end=end)
        report(label, trades)
