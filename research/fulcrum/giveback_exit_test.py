"""
GIVEBACK EXIT test for Fulcrum M15 (2026-10-09, user's refined framing):
NOT an immediate breakeven/trail from the start of a trade (already tested
and rejected - see Fulcrum_M15_EA.mq5 v2.13 changelog, 42/42 R/ATR arm-trail
combos worse). This only protects trades ALREADY substantially in profit:
once a trade's favorable excursion first reaches ARM_R x its own initial
risk, the exit arms; from then on, if the close gives back GIVEBACK_FRAC of
the peak profit reached, it exits now instead of waiting for a full reversal
to the stop. Directly informed by the real MFE diagnostic just run
(research/fulcrum/roundtrip_diagnostic.py): 27.1% of real losers gave back
at least 1R, 14.9% gave back 2R+, median initial risk ~$5.87, target ~10.7R.
ARM_R=5.0 (about half way to the ~10.7R target - genuinely "substantial")
and GIVEBACK_FRAC=0.5 are sensible, not swept, defaults - K=1 for this one
construction. Implementation: research/fulcrum/sim_giveback_exit.py is an
exact `cp` of sim.py with one new block added right after the native SL/TP
check, gated behind params["use_giveback_exit"] so the baseline run (no key)
reproduces sim.py byte-for-byte.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim_giveback_exit as S


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
    dd = S.max_dd(pnl)
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  max_dd={dd:8.2f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


if __name__ == "__main__":
    df, h4, ctx = E.build_all(E.P15)
    n_bars = ctx["n"]
    cutoff_i = int(n_bars * 0.70)
    print(f"Fulcrum M15 real GOLD M15 data: {n_bars} bars, 70/30 cutoff at bar {cutoff_i}\n")

    p_base = dict(E.P15)
    p_cand = dict(E.P15, use_giveback_exit=True, giveback_arm_r=5.0, giveback_frac=0.5)

    base_trades = S.simulate(ctx, params=p_base)
    cand_trades = S.simulate(ctx, params=p_cand)

    print(f"{'='*92}\nBASELINE (shipped, no giveback exit)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in base_trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in base_trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", base_trades)

    print(f"\n{'='*92}\nCANDIDATE: + giveback exit (arm at 5.0R, exit on 50% giveback of peak)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in cand_trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in cand_trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", cand_trades)

    print(f"\n{'='*92}\nTail concentration (top-5-trades honesty check)\n{'='*92}")
    print(f"  baseline:  {S.tail_concentration(base_trades)}")
    print(f"  candidate: {S.tail_concentration(cand_trades)}")

    print(f"\n{'='*92}\nPERMUTATION TEST: does the candidate's full-history net beat a random\n"
          f"same-size draw from the BASELINE's own real trade population?\n{'='*92}")
    perm = S.permutation_test(base_trades, cand_trades, n_draws=2000)
    if perm:
        print(f"  candidate real net={perm['real_net']:.2f}  null mean={perm['null_mean']:.2f}  "
              f"null std={perm['null_std']:.2f}  percentile={perm['percentile']:.1f}th")

    print(f"\n  Honest K=1 (single pre-specified arm_r/giveback_frac, not swept).")
