"""
NEW CANDIDATE (2026-10-06, user's own idea): skip the dead overnight
session on Meridian's entries - "more volume if it happens early morning
or afternoon, skip night session, no trading volume or momentum".

NIGHT_HOURS identified empirically from Meridian's own real GOLD M5 data
(mean tick_volume by hour, broker server time) - not assumed or hand-
picked: hours 23/0/1/2 sit at 270-400 mean tick_volume vs a 600-800+
baseline across the rest of the day and 1000-1360 in the 15-18 peak
(same ~2-3x pattern research/aurelius/session_filter_test.py found
independently on Aurelius's data in September - confirms this isn't a
one-off artifact of either EA's own data slice). This is the data-driven
"dead zone", not a narrow single-window restriction - matches the user's
own framing (early morning AND afternoon both fine, only the night gap
excluded), not just the single best 4-hour block.

Tested on TOP of the already-shipped early-exit-on-break rule (Meridian_
EA.mq5 v1.14 / research/meridian/early_exit_break_test.py - that's the
real baseline going forward, not the bare V102 signal). Honest K=1 for
this filter (single pre-specified, data-identified night-hour set, no
threshold sweep).
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, "/home/user/test-project/research/meridian")
import bars as B      # noqa: E402
import msim as M      # noqa: E402
# msim's own import re-inserts the ratchet sys.path entry - re-insert
# meridian's path after importing msim so the next import finds THIS
# directory's file, not research/ratchet's identically-named one.
sys.path.insert(0, "/home/user/test-project/research/meridian")
from early_exit_break_test import make_early_exit_fn  # noqa: E402

NIGHT_HOURS = {23, 0, 1, 2}   # mean tick_volume 270-400 vs 600-1360 the rest of the day - see header


def make_session_filter(ctx):
    hour = ctx["hour"]

    def fn(ctx_, t, d):
        return int(hour[t]) not in NIGHT_HOURS
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
    print(f"Night hours excluded (data-identified dead zone): {sorted(NIGHT_HOURS)}\n")

    p_baseline = replace(M.V102, exit_fn=make_early_exit_fn(ctx))   # already-shipped v1.14 real baseline
    p_candidate = replace(M.V102, exit_fn=make_early_exit_fn(ctx), entry_filter=make_session_filter(ctx))

    for stage_label, p in (
        ("1. SHIPPED V102 + early-exit-on-break (current real baseline)", p_baseline),
        ("2. + night-session filter (NEW)", p_candidate),
    ):
        print(f"{'='*92}\n{stage_label}\n{'='*92}")
        for label, start, end in (("IN-SAMPLE (first 70%)", full_start, cutoff_time),
                                   ("OUT-OF-SAMPLE (last 30%)", cutoff_time, full_end)):
            trades, _ = M.simulate(ctx, p, start=start, end=end)
            report(label, trades)
        print()

    print(f"{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws - matched trade count/direction, SAME\n"
          f"real exit machinery (early-exit rule + reversal/Friday/hour0 retry + SL), entries\n"
          f"still restricted to non-night hours\n{'='*92}")
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
        hour = ctx["hour"]
        eligible_bars = np.array([t for t in range(i0 + 1, i1)
                                   if ctx["mod"][t] >= M.V102.entry_from_min and int(hour[t]) not in NIGHT_HOURS])
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

    print(f"\n  Honest K for this idea: 1 (single pre-specified, data-identified night-hour set, no sweep).")
