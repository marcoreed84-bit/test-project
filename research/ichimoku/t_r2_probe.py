import numpy as np, pandas as pd, engine as E, sim as S
from battery import *

print("=== ATR%-of-price by year on GOLD H4 (checking the 'risen 5-6x' premise) ===")
atrp = CTX["atr"]/C
for y in range(2013, 2027):
    m = CTX["year"] == y
    if m.sum(): print(f"   {y}  median ATR%/price = {np.nanmedian(atrp[m]):.5f}   median ATR=${np.nanmedian(CTX['atr'][m]):6.2f}  median px=${np.nanmedian(C[m]):7.1f}")

print("\n=== PROBE: the one cell that scored 97.4 individually - R2(20) > 0.5 ===")
r2 = rsq_trend(C, 20)
f = lambda ctx,i,b: np.isfinite(r2[i]) and r2[i] > 0.5
row = evaluate("R2(20)>0.5", f)
tr = row["trades"]
print("   year-by-year net:", S.year_breakdown(tr))
print("   trades per year:", {y: sum(1 for t in tr if int(t['year'])==y) for y in sorted({int(t['year']) for t in tr})})
pnl = sorted([t["pnl"] for t in tr], reverse=True)
print(f"   top 5 pnl: {[round(x,1) for x in pnl[:5]]}   bottom 5: {[round(x,1) for x in pnl[-5:]]}")
print(f"   OOS (n={row['OOS']['n']}) detail: {row['OOS']}")

print("\n   -- best-of-N corrected ON PF (the metric that made this cell stand out),")
print("      over the whole 12-cell regime family searched in TEST 2 --")
r2a, r2b = rsq_trend(C,20), rsq_trend(C,50)
adx = CTX["adx"]
fam = []
for lbl, arr, ths, op in [("adx3",(adx-pd.Series(adx).shift(3).values),(0.0,),">"),
                          ("adx6",(adx-pd.Series(adx).shift(6).values),(0.0,),">"),
                          ("r2_20",r2a,(0.3,0.5,0.7),">"), ("r2_50",r2b,(0.3,0.5,0.7),">")]:
    for th in ths:
        fam.append(S.simulate(CTX, P, extra_filter=(lambda a,t: (lambda c,i,b: np.isfinite(a[i]) and a[i]>t))(arr,th)))
for n_ch in (14,28):
    ch = choppiness(H,L,C,n_ch)
    for th in (38.2,50.0,61.8):
        fam.append(S.simulate(CTX, P, extra_filter=(lambda a,t: (lambda c,i,b: np.isfinite(a[i]) and a[i]<t))(ch,th)))
fam = [t for t in fam if len(t) >= 15]

def bestofN_pf(base, sets, n_draws=3000, seed=3):
    rng = np.random.default_rng(seed)
    allp = np.array([t["pnl"] for t in base])
    ks = [len(s) for s in sets]
    def pf(a):
        gw=a[a>0].sum(); gl=-a[a<0].sum(); return gw/gl if gl>0 else 50.0
    real = max(pf(np.array([t["pnl"] for t in s])) for s in sets)
    draws = np.array([max(pf(allp[rng.choice(len(allp),k,replace=False)]) for k in ks) for _ in range(n_draws)])
    return dict(percentile=round(100*(draws<real).mean(),1), real_best_pf=round(real,3),
                null_mean_pf=round(draws.mean(),3), n_cells=len(ks))
print("     ", bestofN_pf(BASE, fam))

print("\n   -- is R2>0.5 stable? sensitivity around the threshold --")
for th in (0.40,0.45,0.50,0.55,0.60,0.65):
    evaluate(f"R2(20) > {th}", (lambda t: (lambda c,i,b: np.isfinite(r2[i]) and r2[i]>t))(th))
print("   -- and around the lookback --")
for nb in (14,16,18,20,22,26,30):
    a = rsq_trend(C, nb)
    evaluate(f"R2({nb}) > 0.5", (lambda aa: (lambda c,i,b: np.isfinite(aa[i]) and aa[i]>0.5))(a))
