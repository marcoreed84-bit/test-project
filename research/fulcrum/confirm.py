"""
The rigor-closing step for battery.py: two corrections that a per-family
best-of-N does not make.

1. GLOBAL best-of-N. battery.py corrects each family for the cells searched
   WITHIN that family. But four families were searched, so the honest null
   for "the single best thing found anywhere" is best-of-ALL-cells.

2. CROSS-TIMEFRAME REPLICATION. M5 and M15 are near-independent samples of
   the same edge (same symbol and window, but different bars, different
   legs, different trade population - 820 vs 340 trades with little
   overlap). A real regime effect should show up in BOTH. A best-of-N
   artifact picks a different winning cell on each. This runs every M5 cell
   on M15 and vice versa and reports the pair.

3. The InpMinStopATR claim already documented in the shipped .mq5 comment
   ("+15% net, 14/14 IS grid cells, 9/14 OOS, 98.3rd percentile") is
   re-tested here against this independently rebuilt engine - the original
   Python that produced it was lost, so it has never been reproduced.
"""
import numpy as np
import pandas as pd

import engine as E
import sim as S
from indicators import adx, efficiency_ratio, roll_pct


def cell_defs(ctx):
    """(label, kind, payload) for every cell battery.py searches. `kind` is
    'filter' (extra entry gate) or 'params' (whole-sim re-run)."""
    C, H, L = ctx["close"], ctx["high"], ctx["low"]
    out = []
    for v in (0.00, 0.25, 0.75, 1.00, 1.25, 1.50, 2.00, 2.50, 3.00):
        out.append((f"SRdist={v:.2f}", "params", dict(min_sr_dist_atr=v, use_sr_dist=v > 0.0)))
    for n_er in (20, 50, 100):
        er = efficiency_ratio(C, n_er)
        erp = roll_pct(er, 500)
        for thr in (0.10, 0.15, 0.20, 0.25):
            out.append((f"ER({n_er})>={thr}", "filter", er >= thr))
        for q in (0.3, 0.5, 0.7):
            out.append((f"ER({n_er})pct>={q}", "filter", erp >= q))
    A = adx(H, L, C, 14)
    for th in (15, 18, 20, 22, 25, 30, 35):
        out.append((f"ADX>{th}", "filter", A > th))
    for lb in (3, 6):
        out.append((f"ADXrise{lb}", "filter", (A - pd.Series(A).shift(lb).values) > 0))
    atrp = ctx["atr"] / C
    win = 8640 if ctx["n"] > 150000 else 2880
    for w, wl in ((win, "1mo"), (3 * win, "3mo")):
        ap = roll_pct(atrp, w)
        for lo, hi in ((0.0, 0.5), (0.5, 1.0), (0.0, 0.33), (0.33, 0.67), (0.67, 1.0)):
            out.append((f"ATR%{wl}[{lo},{hi})", "filter", (ap >= lo) & (ap < hi)))
    bpd = 288 if ctx["n"] > 150000 else 96
    for mc in (3, 4, 5, 6, 8):
        for pd_ in (1, 3, 5):
            out.append((f"brk{mc}/{pd_}d", "params",
                        dict(use_consec_breaker=True, max_consec_losses=mc, pause_bars=pd_ * bpd)))
    return out


def run_cells(ctx, base_params, cells):
    res = {}
    for label, kind, payload in cells:
        if kind == "filter":
            mask = np.asarray(payload)
            f = (lambda m: (lambda c, i, b: bool(m[i])))(mask)
            tr = S.simulate(ctx, params=base_params, extra_filter=f)
        else:
            p = dict(base_params)
            p.update(payload)
            tr = S.simulate(ctx, params=p)
        res[label] = tr
    return res


def net(tr):
    return float(sum((t["exit_px"] - t["entry_px"]) * t["dir"] for t in tr))


if __name__ == "__main__":
    ctxs, bases, results = {}, {}, {}
    for tag, p in (("M5", E.P), ("M15", E.P15)):
        _, _, ctx = E.build_all(p)
        ctxs[tag] = ctx
        bases[tag] = S.simulate(ctx, params=p)
        results[tag] = run_cells(ctx, p, cell_defs(ctx))

    print("=" * 112)
    print("1. GLOBAL best-of-N (all 55 cells across all four families, per timeframe)")
    print("=" * 112)
    for tag in ("M5", "M15"):
        base = bases[tag]
        b = S.stats(base)
        sets = [tr for tr in results[tag].values() if tr]
        g = S.permutation_test_bestofN(base, sets, n_draws=4000)
        best_lbl = max(results[tag], key=lambda k: net(results[tag][k]))
        print(f"  {tag:4s} baseline net=${b['net']:.1f} PF={b['pf']:.3f} | "
              f"best cell = {best_lbl} net=${net(results[tag][best_lbl]):.1f}")
        print(f"       global best-of-{g['n_cells']} percentile = {g['percentile']}  "
              f"(null mean ${g['null_mean']})  -> {'PASSES' if g['percentile'] >= 95 else 'FAILS'} "
              "the >=95th-percentile bar")

    print()
    print("=" * 112)
    print("2. CROSS-TIMEFRAME REPLICATION - the top cells on each timeframe, scored on the other")
    print("=" * 112)
    for tag, other in (("M5", "M15"), ("M15", "M5")):
        base_n, other_base_n = net(bases[tag]), net(bases[other])
        top = sorted(results[tag], key=lambda k: net(results[tag][k]), reverse=True)[:6]
        print(f"\n  top-6 cells by net on {tag} (baseline ${base_n:.0f}), "
              f"re-scored on {other} (baseline ${other_base_n:.0f}):")
        for lbl in top:
            a = net(results[tag][lbl])
            bn = net(results[other][lbl]) if lbl in results[other] else float("nan")
            pa = S.permutation_test(bases[tag], results[tag][lbl], n_draws=2000)
            pb = (S.permutation_test(bases[other], results[other][lbl], n_draws=2000)
                  if lbl in results[other] and results[other][lbl] else None)
            fmt = lambda x: ("%5.1f" % x["percentile"]) if x else "  -  "   # noqa: E731
            print(f"    {lbl:22s} {tag}: ${a:8.1f} ({a-base_n:+7.1f}) perm={fmt(pa)}   "
                  f"{other}: ${bn:8.1f} ({bn-other_base_n:+7.1f}) perm={fmt(pb)}")

    # The decisive count: most cells REDUCE net on both timeframes simply by
    # removing trades, so raw sign agreement is dominated by mutual negatives
    # and says nothing. What matters is how many cells BEAT baseline on BOTH.
    common = [l for l in results["M5"] if l in results["M15"]
              and results["M5"][l] and results["M15"][l]]
    b5, b15 = net(bases["M5"]), net(bases["M15"])
    up5 = [l for l in common if net(results["M5"][l]) > b5]
    up15 = [l for l in common if net(results["M15"][l]) > b15]
    both = sorted(set(up5) & set(up15))
    print(f"\n  of {len(common)} cells: {len(up5)} beat baseline on M5, {len(up15)} on M15, "
          f"{len(both)} on BOTH -> {both}")
    if both:
        for lbl in both:
            p5 = S.permutation_test(bases["M5"], results["M5"][lbl], n_draws=2000)
            p15 = S.permutation_test(bases["M15"], results["M15"][lbl], n_draws=2000)
            print(f"      {lbl:22s} M5 +${net(results['M5'][lbl])-b5:7.1f} perm={p5['percentile']:5.1f}"
                  f"   M15 +${net(results['M15'][lbl])-b15:7.1f} perm={p15['percentile']:5.1f}")
    exp = len(up5) * len(up15) / len(common)
    print(f"      (if the two timeframes were independent coin flips at these rates, "
          f"{exp:.1f} cells would land on both by chance)")

    print()
    print("=" * 112)
    print("3. InpMinStopATR - re-testing the claim already written into the shipped .mq5 comment")
    print("    (\"+15% net, better in 14/14 IS grid cells and 9/14 blind-OOS, 98.3rd percentile\")")
    print("=" * 112)
    for tag, p in (("M5", E.P), ("M15", E.P15)):
        ctx, base = ctxs[tag], bases[tag]
        bst = S.stats(base)
        bis, boos = S.split_stats(base, ctx["n"])
        print(f"\n  {tag} baseline (min_stop_atr=0, off): n={bst['n']} net=${bst['net']:.1f} "
              f"PF={bst['pf']:.3f} win={100*bst['win_rate']:.1f}% "
              f"IS_PF={bis['pf']:.3f} OOS_PF={boos['pf']:.3f} "
              f"exT5=${S.tail_concentration(base)['ex_topk_net']:.1f}")
        sets = []
        for v in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0):
            q = dict(p)
            q["min_stop_atr"] = v
            tr = S.simulate(ctx, params=q)
            st = S.stats(tr)
            i_, o_ = S.split_stats(tr, ctx["n"])
            tc = S.tail_concentration(tr)
            pm = S.permutation_test(base, tr, n_draws=2000)
            pnl = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in tr])
            print(f"    min_stop_atr={v:.1f}: n={st['n']:4d} net=${st['net']:8.1f} "
                  f"({100*(st['net']/bst['net']-1):+5.1f}%) PF={st['pf']:.3f} "
                  f"win={100*st['win_rate']:4.1f}% DD={S.max_dd(pnl):6.1f} "
                  f"IS_PF={i_['pf']:.3f} OOS_PF={o_['pf']:.3f} "
                  f"exT5=${tc['ex_topk_net']:7.1f} perm={pm['percentile']:5.1f}")
            sets.append(tr)
        print(f"    best-of-7 corrected: {S.permutation_test_bestofN(base, sets, n_draws=4000)}")
