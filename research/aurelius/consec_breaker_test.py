"""
Consecutive-loss circuit breaker on Aurelius's real gates - M5 (v1.46) and
M15 (v1.51). Ported in shape from Zenith_EA.mq5's already-live mechanism
(InpMaxConsecLosses / InpPauseBars) but NOT its numbers: Zenith's 2-losses/
672-M15-bars was tuned to Zenith's own cadence.

Rigor, same as every other candidate in this dir:
  - grid sweep, not one arbitrary setting
  - 70/30 chronological IS/OOS
  - tail concentration + ex-top-5 honesty check
  - permutation nulls: (a) random same-size draws from the baseline's own
    trades, and (b) the one that actually matters for a TIMING rule -
    random pause windows of the same count and length fired at randomly
    chosen trade closes, i.e. "does pausing after a LOSING STREAK beat
    pausing for the same total time at random?"
  - drawdown (closed-equity AND floating-equity), because regime protection
    is the stated purpose - a net-profit change that leaves DD alone is not
    solving the problem this is for.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S
from sr_reject_test import split_stats, tail_concentration, permutation_test

# M5: 288 bars = 1 trading day, 2016 = 7 days (Zenith's own pause length).
# M15: 96 = 1 day, 672 = 7 days (Zenith's literal default).
GRID = {
    "M5": dict(pauses=[288, 576, 1440, 2016, 4032], losses=[2, 3, 4, 5, 6]),
    "M15": dict(pauses=[96, 192, 480, 672, 1344], losses=[2, 3, 4, 5, 6]),
}


def run(params, ctx, use=False, mc=0, pb=0, rule=None):
    p = dict(params)
    if use:
        p.update(use_consec_breaker=True, max_consec_losses=mc, pause_bars=pb)
        if rule is not None:
            p["breaker_rule"] = rule
    return S.simulate(ctx, params=p)


def count_pauses(trades, mc):
    """how many times the real streak rule would have fired"""
    s = 0
    fires = 0
    for t in trades:
        if (t["exit_px"] - t["entry_px"]) * t["dir"] <= 0:
            s += 1
            if s >= mc:
                fires += 1
        else:
            s = 0
    return fires


def report_tf(name, params, ctx):
    base = S.simulate(ctx, params=params)
    bs, br = S.stats(base), S.risk_stats(base, ctx)
    n = ctx["n"]
    print(f"\n################ {name} ################")
    print(f"BASELINE n={bs['n']} net={bs['net']:.1f} pf={bs['pf']:.3f} "
          f"wr={bs['win_rate']:.3f} closed_dd={br['closed_dd']:.1f} float_dd={br['float_dd']:.1f}")
    b_is, b_oos = split_stats(base, n)
    print(f"  IS n={b_is['n']} net={b_is['net']:.1f} pf={b_is['pf']:.2f} | "
          f"OOS n={b_oos['n']} net={b_oos['net']:.1f} pf={b_oos['pf']:.2f}")
    bt = tail_concentration(base)
    print(f"  tail: top5={bt['top5_pct']:.1f}% of net, ex-top5 net={bt['ex_top5_net']:.1f}")

    g = GRID[name]
    print(f"\n  grid (net / pf / closed_dd / float_dd, delta vs baseline in parens):")
    print(f"  {'mc':>3} {'pause':>6} {'fires':>6} {'n':>5} {'net':>9} {'dnet%':>7} "
          f"{'pf':>6} {'cDD':>8} {'dcDD%':>7} {'fDD':>8} {'dfDD%':>7}")
    results = []
    for mc in g["losses"]:
        fires = count_pauses(base, mc)
        for pb in g["pauses"]:
            t = run(params, ctx, use=True, mc=mc, pb=pb)
            st, rk = S.stats(t), S.risk_stats(t, ctx)
            dn = 100 * (st["net"] - bs["net"]) / bs["net"]
            dc = 100 * (rk["closed_dd"] - br["closed_dd"]) / br["closed_dd"]
            dfl = 100 * (rk["float_dd"] - br["float_dd"]) / br["float_dd"]
            results.append((mc, pb, st, rk, dn, dc, dfl, t))
            print(f"  {mc:>3} {pb:>6} {fires:>6} {st['n']:>5} {st['net']:>9.1f} {dn:>6.1f}% "
                  f"{st['pf']:>6.3f} {rk['closed_dd']:>8.1f} {dc:>6.1f}% "
                  f"{rk['float_dd']:>8.1f} {dfl:>6.1f}%")
    return base, bs, br, results


def deep_dive(name, params, ctx, base, bs, br, mc, pb, seed=0):
    print(f"\n  --- deep dive {name} mc={mc} pause={pb} ---")
    t = run(params, ctx, use=True, mc=mc, pb=pb)
    st, rk = S.stats(t), S.risk_stats(t, ctx)
    n = ctx["n"]
    print(f"  cand n={st['n']} net={st['net']:.1f} pf={st['pf']:.3f} "
          f"closed_dd={rk['closed_dd']:.1f} float_dd={rk['float_dd']:.1f}")
    c_is, c_oos = split_stats(t, n)
    b_is, b_oos = split_stats(base, n)
    print(f"  IS  base net={b_is['net']:.1f} pf={b_is['pf']:.2f} -> cand net={c_is['net']:.1f} pf={c_is['pf']:.2f}")
    print(f"  OOS base net={b_oos['net']:.1f} pf={b_oos['pf']:.2f} -> cand net={c_oos['net']:.1f} pf={c_oos['pf']:.2f}")
    ct, bt = tail_concentration(t), tail_concentration(base)
    print(f"  tail base top5={bt['top5_pct']:.1f}% ex-top5={bt['ex_top5_net']:.1f} | "
          f"cand top5={ct['top5_pct']:.1f}% ex-top5={ct['ex_top5_net']:.1f}")
    perm = permutation_test(base, t, n_draws=800, seed=seed)
    if perm:
        print(f"  perm null (random same-size subset of baseline trades): "
              f"real={perm['real_net']:.1f} null_mean={perm['null_mean']:.1f} "
              f"sd={perm['null_std']:.1f} pct={perm['percentile']:.1f}")

    # --- timing null: same number of pauses, same length, random closes ---
    fires = count_pauses(base, mc)
    n_closes = len(base)
    prob = fires / max(1, n_closes)
    rng = np.random.default_rng(seed + 11)
    nets, cdds, fdds = [], [], []
    for _ in range(200):
        r = np.random.default_rng(int(rng.integers(1 << 30)))
        rule = (lambda rr: (lambda consec, pnl, exit_i: rr.random() < prob))(r)
        tt = run(params, ctx, use=True, mc=1, pb=pb, rule=rule)
        nets.append(S.stats(tt)["net"])
        rr2 = S.risk_stats(tt, ctx)
        cdds.append(rr2["closed_dd"]); fdds.append(rr2["float_dd"])
    nets = np.array(nets); cdds = np.array(cdds); fdds = np.array(fdds)
    print(f"  timing null ({fires} random pauses of {pb} bars, 200 draws):")
    print(f"    net  real={st['net']:.1f}  null_mean={nets.mean():.1f} sd={nets.std():.1f} "
          f"pct={(100*(nets < st['net']).mean()):.1f}")
    print(f"    cDD  real={rk['closed_dd']:.1f}  null_mean={cdds.mean():.1f} sd={cdds.std():.1f} "
          f"pct_lower={(100*(cdds > rk['closed_dd']).mean()):.1f}")
    print(f"    fDD  real={rk['float_dd']:.1f}  null_mean={fdds.mean():.1f} sd={fdds.std():.1f} "
          f"pct_lower={(100*(fdds > rk['float_dd']).mean()):.1f}")


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx5 = E.build_context(df, h4, E.P)
    ctx15 = E.build_context(E.resample_m15_from_m5(df), h4, E.P15)

    b5, bs5, br5, r5 = report_tf("M5", E.P, ctx5)
    b15, bs15, br15, r15 = report_tf("M15", E.P15, ctx15)

    # deep-dive the grid cell with the best closed_dd reduction on each TF,
    # and separately the best net - chosen AFTER the sweep, which is exactly
    # the selection bias the permutation nulls below are there to expose.
    for nm, params, ctx, base, bs, br, res in (
        ("M5", E.P, ctx5, b5, bs5, br5, r5), ("M15", E.P15, ctx15, b15, bs15, br15, r15)):
        best_dd = min(res, key=lambda x: x[3]["closed_dd"])
        best_net = max(res, key=lambda x: x[2]["net"])
        seen = set()
        for cell in (best_dd, best_net):
            key = (cell[0], cell[1])
            if key in seen:
                continue
            seen.add(key)
            deep_dive(nm, params, ctx, base, bs, br, cell[0], cell[1])
