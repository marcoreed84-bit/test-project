"""
NEW CANDIDATE (2026-10-09, user's own observation from live platform testing):
some EAs "test better" with a max-spread filter around 50-55 points. Real
historical GOLD M5 spread (research/aurelius/engine.py's own data): p50=30,
p90=43, p95=51, p99=53, max=248 - so a 50/55 threshold cuts only the worst
~5-10% tail of highest-spread bars, not a routine condition. Plausible on
its face (avoid trading in the worst-liquidity moments), but "tests better"
on its own isn't enough per this project's standard - needs the same honest
walk-forward + random-timing-null check as every other filter tonight,
since several filters that "looked" like they should help (crisscross,
session, retest-gating) turned out to just be noise or genuine losers once
checked properly.

Tested on Meridian (real shipped V102 + already-shipped early-exit rule,
the current real baseline) at both thresholds the user mentioned (50 and
55), each its own honest construction - K=2 for this test alone, not
combined with K already spent on other Meridian ideas tonight (those are
separate ideas, not part of the same search).
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, "/home/user/test-project/research/meridian")
import msim as M      # noqa: E402
sys.path.insert(0, "/home/user/test-project/research/meridian")
from early_exit_break_test import make_early_exit_fn  # noqa: E402


def make_spread_filter(ctx, max_spread):
    spread = ctx["spread"]

    def fn(ctx_, t, d):
        return spread[t] <= max_spread
    return fn


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def max_drawdown(pnl):
    equity = np.cumsum(pnl)
    peak = np.maximum.accumulate(equity)
    dd = peak - equity
    return dd.max() if len(dd) else 0.0


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  max_dd={max_drawdown(pnl):9.2f}  avg={pnl.mean():7.3f}")


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
    spread = ctx["spread"]
    print(f"GOLD M5 real data: {full_start} .. {full_end}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {cutoff_time}")
    print(f"Real spread: median={np.median(spread):.0f}  p90={np.percentile(spread,90):.0f}  "
          f"p95={np.percentile(spread,95):.0f}  p99={np.percentile(spread,99):.0f}  max={spread.max():.0f}\n")

    p_baseline = replace(M.V102, exit_fn=make_early_exit_fn(ctx))

    configs = [("1. SHIPPED V102 + early-exit (current real baseline, no spread filter)", p_baseline, None)]
    for max_spread in (50, 55):
        p = replace(M.V102, exit_fn=make_early_exit_fn(ctx), entry_filter=make_spread_filter(ctx, max_spread))
        configs.append((f"2. + max-spread filter <= {max_spread}", p, max_spread))

    results = {}
    for stage_label, p, max_spread in configs:
        print(f"{'='*92}\n{stage_label}\n{'='*92}")
        for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                                   ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
            trades, _ = M.simulate(ctx, p, start=start, end=end)
            report(label, trades)
            if label.startswith("OUT"):
                results[stage_label] = trades
        print()

    print(f"{'='*92}\nRANDOM-TIMING NULLS (OOS only), 2000 draws each - matched trade count/direction,\n"
          f"SAME real exit machinery (early-exit rule + reversal/Friday/hour0 retry + SL), entries\n"
          f"still restricted to the same max-spread threshold where applicable\n{'='*92}")
    for stage_label, p, max_spread in configs:
        oos_trades = results[stage_label]
        n_oos = len(oos_trades)
        if n_oos < 5:
            print(f"  {stage_label}: only {n_oos} OOS trades - too few for a meaningful null")
            continue
        real_pf = pf([t["pnl"] for t in oos_trades])
        i0 = int(np.searchsorted(ctx["t64"], np.datetime64(cutoff_time)))
        i1 = int(np.searchsorted(ctx["t64"], np.datetime64(full_end)))
        dirs = [t["dir"] for t in oos_trades]
        if max_spread is not None:
            eligible_bars = np.array([t for t in range(i0 + 1, i1)
                                       if ctx["mod"][t] >= M.V102.entry_from_min and spread[t] <= max_spread])
        else:
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
        print(f"  {stage_label}")
        print(f"    real: n={n_oos}, PF={real_pf:.3f}  |  null median={np.median(null_pfs):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}  |  percentile={100*(null_pfs < real_pf).mean():.1f}th  "
              f"p={p_value:.4f}  {'[SURVIVES]' if p_value < 0.05 else '[does not beat random timing]'}")

    print(f"\n  Honest K=2 for this test (two thresholds, both user-specified, no sweep beyond that).")
