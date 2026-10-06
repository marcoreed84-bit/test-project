"""
NEW CANDIDATE (2026-10-06, user's own observation from the same Meridian
chart example): the 21/50 cross that triggered the real entry (top-right
arrow) came out of a "crisscrossing pocket" - the two EMAs tangled
together with no real established trend right before that specific cross
- unlike the earlier bottom-of-leg cross (bottom-left arrow), which came
out of a genuine prior move. Meridian's shipped entry has NO filter for
this at all - it fires on ANY 21/50 cross, chop or clean trend alike.

This is the same "nice running distance before they cross" idea already
built and validated conceptually in research/ema_vwap_pullback/
ema_vwap_pullback_test.py (SEP_LOOKBACK/SEP_MIN_ATR), now applied as an
actual pre-entry filter on Meridian's REAL shipped signal for the first
time - that earlier test built a brand new standalone construction;
this one adds the SAME filter concept directly onto Meridian's existing,
real, bar-matched entry.

FILTER: before the cross confirms (cross bar s = t-1), require that at
some point in the SEP_LOOKBACK bars before s, the 21/50 EMAs were
separated by at least SEP_MIN_ATR x ATR (the MAXIMUM separation in that
window - by definition the EMAs must converge right at the cross, so
requiring separation held all the way up to it would reject every single
crossover, same reasoning as the earlier test). Rejects crosses born out
of a flat/choppy pocket with no real recent trend.

Tested on TOP of the already-validated early-exit-on-break rule
(research/meridian/early_exit_break_test.py, confirmed real: OOS
PF 1.493->1.779, p=0.0005) - this file compares three stages:
  1. shipped V102 (baseline)
  2. V102 + early-exit-on-break (already confirmed)
  3. V102 + early-exit-on-break + crisscross filter (NEW, this file)
so the crisscross filter's own marginal contribution is visible on its
own, not conflated with the already-confirmed early-exit result. Honest
K=1 for the crisscross filter specifically (single pre-specified
threshold, reusing SEP_LOOKBACK=20/SEP_MIN_ATR=0.50 verbatim from the
already-built construction, not re-tuned here).
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, "/home/user/test-project/research/meridian")
import bars as B      # noqa: E402
import msim as M      # noqa: E402
# msim's own import re-inserts the ratchet path at position 0, pushing
# meridian's path behind it - re-insert meridian's path AFTER importing
# msim so the next import below actually finds THIS directory's module,
# not research/ratchet/early_exit_break_test.py (same filename, wrong file).
sys.path.insert(0, "/home/user/test-project/research/meridian")
from early_exit_break_test import make_early_exit_fn  # noqa: E402

SEP_LOOKBACK = 20
SEP_MIN_ATR = 0.50


def make_crisscross_filter(ctx):
    m21, m50, atr = M.ma(ctx, 21, "ema"), M.ma(ctx, 50, "ema"), ctx["atr"]

    def fn(ctx_, t, d):
        s = t - 1   # the cross-confirm bar
        lo, hi = s - SEP_LOOKBACK, s - 1
        if lo < 0:
            return True   # not enough history - let the shipped checks decide, don't block
        win_atr = atr[lo:hi + 1]
        if np.any(np.isnan(win_atr)) or np.any(win_atr <= 0):
            return True
        sep_atr = np.abs(m21[lo:hi + 1] - m50[lo:hi + 1]) / win_atr
        return sep_atr.max() >= SEP_MIN_ATR
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
    ctx = M.build_ctx()
    n_bars = len(ctx["t64"])
    cutoff = int(n_bars * 0.70)
    cutoff_time = pd.Timestamp(ctx["t64"][cutoff])
    full_start, full_end = pd.Timestamp(ctx["t64"][0]), pd.Timestamp(ctx["t64"][-1])
    print(f"GOLD M5 real data: {full_start} .. {full_end}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {cutoff_time}")
    print(f"Crisscross filter: requires max {SEP_MIN_ATR}xATR 21/50 separation in the {SEP_LOOKBACK} bars "
          f"before the cross (same thresholds as ema_vwap_pullback_test.py's SEP filter).\n")

    p_base = M.V102
    p_earlyexit = replace(M.V102, exit_fn=make_early_exit_fn(ctx))
    p_both = replace(M.V102, exit_fn=make_early_exit_fn(ctx), entry_filter=make_crisscross_filter(ctx))

    for stage_label, p in (
        ("1. SHIPPED V102 (baseline)", p_base),
        ("2. V102 + early-exit-on-break (already confirmed)", p_earlyexit),
        ("3. V102 + early-exit-on-break + crisscross filter (NEW)", p_both),
    ):
        print(f"{'='*92}\n{stage_label}\n{'='*92}")
        for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                                   ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
            trades, _ = M.simulate(ctx, p, start=start, end=end)
            report(label, trades)
        print()
