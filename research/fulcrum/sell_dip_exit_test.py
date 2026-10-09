"""
SELL DIP EXIT for Fulcrum M15 (2026-10-09, confirmed via a real diagnostic
on the user's own observation). Real SELL trades that close back above the
50-MA at any point mid-trade are a real losing group (letting them ride:
PF=0.405, net=-633.22; cut at the first dip: PF=0.309, net=-459.21 - still
a loss, but smaller). Confirmed on BOTH IS and OOS (IS net +10.1%, OOS net
+17.5%, whole-system net 1235.04 -> 1409.05, PF 1.483 -> 1.654). SELL-ONLY
by design: BUY trades showed the opposite shape in the same diagnostic
(brief 1-2 bar dips are a real losing group, but SUSTAINED 3+ bar dips are
still net positive, PF 1.926) - a blanket exit-on-first-dip rule would have
cut off that 74-trade winning group, so this is deliberately not applied to
buys. Implementation: sim_sell_dip_exit.py is an exact `cp` of sim.py with
one new block right after the native SL/TP check, gated behind
params["use_sell_dip_exit"] and restricted to is_buy==False, so the
baseline run (no key) reproduces sim.py byte-for-byte.

This file adds the random-timing null the manual diagnostic didn't have:
does the candidate's real OOS PF beat random entry timing on SELL trades
specifically, under the same real exit machinery including this new rule?
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim_sell_dip_exit as S


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
    p_cand = dict(E.P15, use_sell_dip_exit=True)

    base_trades = S.simulate(ctx, params=p_base)
    cand_trades = S.simulate(ctx, params=p_cand)

    print(f"{'='*92}\nBASELINE (shipped, no sell-dip exit)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in base_trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in base_trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", base_trades)

    print(f"\n{'='*92}\nCANDIDATE: + sell-dip exit (SELL trades only)\n{'='*92}")
    report("IN-SAMPLE (first 70%)", [t for t in cand_trades if t["entry_i"] < cutoff_i])
    report("OUT-OF-SAMPLE (last 30%)", [t for t in cand_trades if t["entry_i"] >= cutoff_i])
    report("FULL HISTORY", cand_trades)

    print(f"\n{'='*92}\nSELLS ONLY, side by side\n{'='*92}")
    base_sells = [t for t in base_trades if t["dir"] < 0]
    cand_sells = [t for t in cand_trades if t["dir"] < 0]
    report("Baseline sells", base_sells)
    report("Candidate sells", cand_sells)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL on SELLS (OOS only), 2000 draws - matched trade\n"
          f"count, SAME real exit machinery (sell-dip rule + stop/target/Friday),\n"
          f"entries restricted to the real sell-eligible alignment windows\n{'='*92}")
    oos_cand_sells = [t for t in cand_trades if t["dir"] < 0 and t["entry_i"] >= cutoff_i]
    n_oos = len(oos_cand_sells)
    if n_oos < 5:
        print(f"  only {n_oos} OOS sell trades - too few for a meaningful null")
    else:
        real_pf = pf([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in oos_cand_sells])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}")
        aligned_sell = ctx["aligned_sell"]
        eligible = np.array([i for i in range(cutoff_i, n_bars - 1) if aligned_sell[i]])
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            rng = np.random.default_rng(seed)
            if len(eligible) < n_oos:
                break
            chosen = set(rng.choice(eligible, size=n_oos, replace=False).tolist())

            def filt(ctx_, i, is_buy, chosen=chosen):
                return (not is_buy) and (i in chosen)
            ntrades = S.simulate(ctx, extra_filter=filt, params=p_cand)
            noos = [t for t in ntrades if t["dir"] < 0 and t["entry_i"] >= cutoff_i]
            pnl = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in noos]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        if null_pfs:
            null_pfs = np.array(null_pfs)
            p_value = (null_pfs >= real_pf).mean()
            print(f"  null PF: median={np.median(null_pfs):.3f}  p95={np.percentile(null_pfs,95):.3f}")
            print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {len(null_pfs)} draws")
            print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K=1 (single pre-specified rule, sell-only, no sweep).")
