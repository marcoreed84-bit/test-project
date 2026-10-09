"""
DELAY ENTRY BY ONE CANDLE (2026-10-09, user's own idea): instead of
filling at the signal bar's open, wait one more bar - only take the trade
at all if that extra bar's close has already moved in the signal's favor
(confirmation); otherwise skip the setup entirely. Direct test of whether
this screens out the "never even reaches $1" trades found in the real MFE
diagnostic (29.3% of all 393 real trades never reach $1 in favor).

Honest framing up front: every entry-side "wait for confirmation" idea
tested on another EA tonight (Meridian's retest-entry, Vanguard's
retest-entry) made things WORSE, because the strongest trades turn out to
be the ones that run immediately with no pullback - confirmation gating
disproportionately removes exactly those. This test checks whether Fulcrum
behaves the same way or differently; no assumption either way.

Implementation: sim_delay_entry.py is an exact `cp` of sim.py with one
new block right where the position is opened, gated behind
params["use_delay_entry"] so the baseline run (no key) reproduces sim.py
byte-for-byte.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim_delay_entry as S


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def mfe_stats(trades, ctx):
    h, l = ctx["high"], ctx["low"]
    mfe = []
    for t in trades:
        d = t["dir"]
        entry_px = t["entry_px"]
        i0, i1 = t["entry_i"] + 1, t["exit_i"]
        if i1 <= i0:
            m = 0.0
        else:
            m = (h[i0:i1 + 1].max() - entry_px) if d > 0 else (entry_px - l[i0:i1 + 1].min())
        mfe.append(max(m, 0.0))
    mfe = np.array(mfe)
    return mfe


def report(label, trades, ctx=None):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades])
    dd = S.max_dd(pnl)
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  max_dd={dd:8.2f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")
    if ctx is not None:
        mfe = mfe_stats(trades, ctx)
        for thr in (1, 2, 3):
            print(f"      never reached ${thr} in favor: {100*(mfe<thr).mean():.1f}% (n={int((mfe<thr).sum())})")


if __name__ == "__main__":
    df, h4, ctx = E.build_all(E.P15)
    n_bars = ctx["n"]
    cutoff_i = int(n_bars * 0.70)
    print(f"Fulcrum M15 real GOLD M15 data: {n_bars} bars, 70/30 cutoff at bar {cutoff_i}\n")

    p_base = dict(E.P15)
    p_cand = dict(E.P15, use_delay_entry=True)

    base_trades = S.simulate(ctx, params=p_base)
    cand_trades = S.simulate(ctx, params=p_cand)

    print(f"{'='*92}\nBASELINE (shipped, immediate entry)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in base_trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in base_trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", base_trades, ctx)

    print(f"\n{'='*92}\nCANDIDATE: delay entry by 1 candle, skip if not confirmed\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in cand_trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in cand_trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", cand_trades, ctx)

    print(f"\n{'='*92}\nPERMUTATION TEST: candidate full-history net vs random same-size draw\n"
          f"from the baseline's own real trade population\n{'='*92}")
    perm = S.permutation_test(base_trades, cand_trades, n_draws=2000)
    if perm:
        print(f"  candidate real net={perm['real_net']:.2f}  null mean={perm['null_mean']:.2f}  "
              f"null std={perm['null_std']:.2f}  percentile={perm['percentile']:.1f}th")

    print(f"\n  Honest K=1 (single pre-specified 1-candle delay, not swept).")
