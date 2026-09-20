import numpy as np, pandas as pd, engine as E, sim as S
from battery import *

header("TEST 1 - Kaufman EFFICIENCY RATIO as an added regime gate (on top of PLAIN+ADX)")
base_line()
cells = []
for n_er in (10, 20, 40):
    er = efficiency_ratio(C, n_er)
    erp = roll_pct(er, 500)
    for thr in (0.2, 0.3, 0.4):
        f = (lambda a: (lambda ctx,i,b: np.isfinite(a[i]) and a[i] >= thr))(er)
        r = evaluate(f"ER({n_er}) >= {thr} (absolute)", f); cells.append(r)
    for q in (0.3, 0.5, 0.7):
        f = (lambda a,qq: (lambda ctx,i,b: np.isfinite(a[i]) and a[i] >= qq))(erp, q)
        r = evaluate(f"ER({n_er}) rollpct >= {q}", f); cells.append(r)
print("  best-of-N corrected over the 18 ER cells:",
      S.permutation_test_bestofN(BASE, [c["trades"] for c in cells if c], n_draws=2000))

header("TEST 2 - a DIFFERENT regime read, on top of the ADX filter already there")
base_line()
cells2 = []
adx = CTX["adx"]
for lbl, arr, ths in [
    ("ADX rising (adx[i]>adx[i-3])", (adx - pd.Series(adx).shift(3).values), (0.0,)),
    ("ADX rising (adx[i]>adx[i-6])", (adx - pd.Series(adx).shift(6).values), (0.0,)),
    ("R2(20) trend quality", rsq_trend(C, 20), (0.3, 0.5, 0.7)),
    ("R2(50) trend quality", rsq_trend(C, 50), (0.3, 0.5, 0.7)),
]:
    for th in ths:
        f = (lambda a,t: (lambda ctx,i,b: np.isfinite(a[i]) and a[i] > t))(arr, th)
        r = evaluate(f"{lbl} > {th}", f); cells2.append(r)
for n_ch in (14, 28):
    ch = choppiness(H, L, C, n_ch)
    for th in (38.2, 50.0, 61.8):
        f = (lambda a,t: (lambda ctx,i,b: np.isfinite(a[i]) and a[i] < t))(ch, th)
        r = evaluate(f"Choppiness({n_ch}) < {th}", f); cells2.append(r)
print("  best-of-N corrected:", S.permutation_test_bestofN(BASE, [c["trades"] for c in cells2 if c], n_draws=2000))

header("TEST 3 - ATR-as-%-of-price, ROLLING PERCENTILE (the disguised-trend trap check)")
atrp = CTX["atr"]/C
print(f"  ATR%/price 2013-2016 median={np.nanmedian(atrp[(CTX['year']>=2013)&(CTX['year']<=2016)]):.5f}  "
      f"2023-2026 median={np.nanmedian(atrp[CTX['year']>=2023]):.5f}  "
      f"ratio={np.nanmedian(atrp[CTX['year']>=2023])/np.nanmedian(atrp[(CTX['year']>=2013)&(CTX['year']<=2016)]):.2f}x")
base_line()
cells3 = []
ap500 = roll_pct(atrp, 500); ap1500 = roll_pct(atrp, 1500)
for wl, ap in (("500", ap500), ("1500", ap1500)):
    for lo, hi in ((0.0,0.5),(0.5,1.0),(0.0,0.33),(0.33,0.67),(0.67,1.0)):
        f = (lambda a,l_,h_: (lambda ctx,i,b: np.isfinite(a[i]) and l_ <= a[i] < h_))(ap, lo, hi)
        r = evaluate(f"ATR% rollpct({wl}) in [{lo},{hi})", f); cells3.append(r)
print("  best-of-N corrected:", S.permutation_test_bestofN(BASE, [c["trades"] for c in cells3 if c], n_draws=2000))

print("\n  --- DETRENDING / date-leak control ---")
print("  ABSOLUTE ATR% thresholds (what a naive regime read would use) - if these")
print("  'work' they are really date filters, because ATR% has trended up:")
for th in (0.004, 0.006, 0.008):
    for side in ("above","below"):
        f = (lambda t,s: (lambda ctx,i,b: np.isfinite(atrp[i]) and (atrp[i]>t if s=="above" else atrp[i]<t)))(th, side)
        r = evaluate(f"ATR%/price {side} {th}", f)
        if r:
            yrs = sorted({int(CTX['year'][t['entry_i']]) for t in r['trades']})
            print(f"       -> years covered: {yrs[0]}-{yrs[-1]}, n_years={len(yrs)}")
print("  PURE DATE control (no indicator at all) - same shape, for comparison:")
for cut in (2019, 2021, 2023):
    f = (lambda cc: (lambda ctx,i,b: ctx['year'][i] >= cc))(cut)
    evaluate(f"date >= {cut} (pure date filter)", f)
