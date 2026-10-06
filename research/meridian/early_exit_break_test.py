"""
NEW CANDIDATE (2026-10-06, user's own recommendation after seeing the
duration data - winners take a median 8.6h via REVERSAL, losers take a
median 1h mostly via SL, and even the best "never retests" bucket still
has 86/250 trades blow straight through to the stop): instead of trying
to lock in profit early (already tested three ways tonight - breakeven,
giveback-cut, partial-close - all made things worse, because this
system's edge lives in the long 8-16h tail of REVERSAL winners), cut
LOSERS early instead. Same entry as shipped V102, same stop, same
reversal-close - ONE addition only:

EARLY EXIT RULE: once price FIRST comes back within RETEST_TOL_ATR x ATR
of either the 21 or 50 EMA after entry (no fixed window - "whenever this
happens", checked every bar for the life of the trade), the VERY NEXT bar
must close back on the favorable side of BOTH EMAs (a genuine bounce) or
the trade exits immediately at that bar's close - "the trade is likely
fucked" per the user's own words, matching exactly what
research/meridian/retest_entry_test.py's post-entry classification
already found in the real data: the RETESTED_BROKE bucket is a near-total
loss (PF=0.188, 7.7% win rate, 118/196 straight to the stop) regardless
of how the rest of the trade might have played out.

This is a single-variable swap vs shipped V102 - nothing about entry,
stop placement, or the reversal-close mechanism changes. Implemented via
msim.py's own exit_fn hook (checked every bar on an open position, can
force an early close) - not a new simulator, reuses the real EA-faithful
one. Honest K=1 (single pre-specified rule, no threshold sweep). Full
real GOLD M5 history, walk-forward 70/30 split, OOS random-timing null.
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, "/home/user/test-project/research/meridian")
import bars as B      # noqa: E402
import msim as M      # noqa: E402

POINT = B.POINT
RETEST_TOL_ATR = 0.30


def make_early_exit_fn(ctx):
    m21, m50 = M.ma(ctx, 21, "ema"), M.ma(ctx, 50, "ema")
    c, atr = ctx["c"], ctx["atr"]

    def fn(ctx_, t, pos):
        d = pos["dir"]
        a = atr[t]
        if not (a > 0):
            return None
        if not pos.get("retest_touched", False):
            tol = RETEST_TOL_ATR * a
            touch = (abs(c[t] - m21[t]) <= tol) or (abs(c[t] - m50[t]) <= tol)
            if touch:
                pos["retest_touched"] = True
            return None
        if pos.get("retest_resolved", False):
            return None
        bounced = (c[t] > m21[t] and c[t] > m50[t]) if d > 0 else (c[t] < m21[t] and c[t] < m50[t])
        broke = (c[t] < m21[t] and c[t] < m50[t]) if d > 0 else (c[t] > m21[t] and c[t] > m50[t])
        if bounced:
            pos["retest_resolved"] = True
            return None
        if broke:
            pos["retest_resolved"] = True
            return "EARLY_EXIT_BROKE"
        return None   # ambiguous (between the two EMAs) - keep watching next bar

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


def random_dirs_matched(dirs, eligible_bars, seed):
    rng = np.random.default_rng(seed)
    eligible = rng.choice(eligible_bars, size=len(dirs), replace=False)
    order = rng.permutation(len(dirs))
    out = {}
    for bar, idx in zip(eligible, order):
        out[int(bar)] = dirs[idx]
    return out


def make_entry_fn(bar_to_dir):
    def fn(ctx, t):
        return bar_to_dir.get(t, 0)
    return fn


if __name__ == "__main__":
    ctx = M.build_ctx()
    n_bars = len(ctx["t64"])
    cutoff = int(n_bars * 0.70)
    cutoff_time = pd.Timestamp(ctx["t64"][cutoff])
    full_start, full_end = pd.Timestamp(ctx["t64"][0]), pd.Timestamp(ctx["t64"][-1])
    print(f"GOLD M5 real data: {full_start} .. {full_end}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {cutoff_time}")
    print(f"Early exit: on the first post-entry retest of the 21/50 EMA zone ({RETEST_TOL_ATR}xATR), the next "
          f"bar must bounce back above both or the trade exits immediately.\n")

    p_candidate = replace(M.V102, exit_fn=make_early_exit_fn(ctx))

    print(f"{'='*92}\nSHIPPED V102 + EARLY EXIT RULE (new candidate)\n{'='*92}")
    for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        trades, stats = M.simulate(ctx, p_candidate, start=start, end=end)
        report(label, trades)

    print(f"\n{'='*92}\nFor reference: shipped V102 (no early exit) over the SAME splits\n{'='*92}")
    for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                               ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
        trades, stats = M.simulate(ctx, M.V102, start=start, end=end)
        report(label, trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - matched trade count/direction, "
          f"SAME exit machinery\nINCLUDING the early-exit rule, via msim's own entry_fn hook\n{'='*92}")
    oos_trades, _ = M.simulate(ctx, p_candidate, start=cutoff_time, end=full_end)
    n_oos = len(oos_trades)
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few for a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}")
        i0 = int(np.searchsorted(ctx["t64"], np.datetime64(cutoff_time)))
        i1 = int(np.searchsorted(ctx["t64"], np.datetime64(full_end)))
        dirs = [t["dir"] for t in oos_trades]
        eligible_bars = np.array([t for t in range(i0 + 1, i1) if ctx["mod"][t] >= M.V102.entry_from_min])
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            rb = random_dirs_matched(dirs, eligible_bars, seed)
            p_null = replace(M.V102, entry_fn=make_entry_fn(rb), exit_fn=make_early_exit_fn(ctx))
            ntrades, _ = M.simulate(ctx, p_null, start=cutoff_time, end=full_end)
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K for this idea: 1 (single pre-specified construction, no sweep run).")
