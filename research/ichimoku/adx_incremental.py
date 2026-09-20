"""How much does ADX actually add BEYOND the base PLAIN signal?
Trade-subset null on three metrics, not just net."""
import numpy as np, engine as E, sim as S
d = E.load_h4("2013-01-01")
BASE_P = E.params(entry_mode="PLAIN", use_adx=False, min_hold_bars=8, safety_stop_atr=2.5)
ctx = E.build_context(d, E.P_BEST_PLAIN_ADX)
base = S.simulate(ctx, BASE_P); best = S.simulate(ctx, E.P_BEST_PLAIN_ADX)

def multi_perm(base_tr, cand_tr, n_draws=4000, seed=1):
    rng = np.random.default_rng(seed)
    allp = np.array([t["pnl"] for t in base_tr]); k = len(cand_tr)
    real = S.stats(cand_tr)
    nets, pfs, dds = [], [], []
    for _ in range(n_draws):
        s = allp[rng.choice(len(allp), k, replace=False)]
        nets.append(s.sum())
        gw = s[s>0].sum(); gl = -s[s<0].sum()
        pfs.append(gw/gl if gl>0 else np.inf)
        dds.append(S.max_dd(s))
    nets, pfs, dds = map(np.array, (nets, pfs, dds))
    return dict(net_pct=round(100*(nets<real["net"]).mean(),1),
                pf_pct=round(100*(pfs<real["pf"]).mean(),1),
                maxdd_pct=round(100*(dds>real["maxdd"]).mean(),1),
                real=dict(net=real["net"], pf=round(real["pf"],3), maxdd=real["maxdd"]))
print("ADX subset vs random equal-size subsets of the base PLAIN trades:")
print(" ", multi_perm(base, best))
print()
print("Sanity: is 'ADX>20' just a proxy for trade count? threshold sweep (all same null):")
for th in (0, 15, 18, 20, 22, 25, 30, 35):
    p = E.params(entry_mode="PLAIN", use_adx=(th>0), adx_threshold=float(th),
                 min_hold_bars=8, safety_stop_atr=2.5)
    t = S.simulate(ctx, p); st = S.stats(t); ny,ty = S.neg_years(t)
    pm = S.permutation_test(base, t, n_draws=2000) if th>0 else None
    tc = S.tail_concentration(t)
    print(f"  ADX>{th:2d}: {S.fmt(st)} negyr={ny}/{ty} "
          f"perm={pm['percentile'] if pm else '-':>5} ex-top5=${tc['ex_top5_net']}")
print()
print("best-of-N corrected (7 thresholds searched):")
sets = []
for th in (15,18,20,22,25,30,35):
    p = E.params(entry_mode="PLAIN", use_adx=True, adx_threshold=float(th), min_hold_bars=8, safety_stop_atr=2.5)
    sets.append(S.simulate(ctx, p))
print(" ", S.permutation_test_bestofN(base, sets, n_draws=2000))
