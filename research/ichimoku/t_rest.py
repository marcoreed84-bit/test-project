import numpy as np, pandas as pd, engine as E, sim as S
from battery import *

header("TEST 5 - session / day-of-week timing of the ENTRY bar")
base_line()
DOW = ["Mon","Tue","Wed","Thu","Fri"]
print("   per-bucket expectancy of the base config's own trades (descriptive):")
for lab, key in (("hour", "hour"), ("dow", "dow")):
    d_ = {}
    for t in BASE: d_.setdefault(int(CTX[key][t["entry_i"]]), []).append(t["pnl"])
    for k in sorted(d_):
        a = np.array(d_[k]); nm = f"{k:02d}:00" if lab=="hour" else DOW[k] if k<5 else str(k)
        print(f"     {lab} {nm:>5}: n={len(a):4d} mean=${a.mean():+7.2f} net=${a.sum():+8.2f} win%={100*(a>0).mean():4.1f}")
cells=[]
for h in (0,4,8,12,16,20):
    cells.append(evaluate(f"exclude entry hour {h:02d}:00", (lambda hh: (lambda c,i,b: c['hour'][i+1] != hh))(h)))
for k in range(5):
    cells.append(evaluate(f"exclude entry day {DOW[k]}", (lambda kk: (lambda c,i,b: c['dow'][i+1] != kk))(k)))
print("   best-of-N over 11 exclusion cells:", S.permutation_test_bestofN(BASE,[c['trades'] for c in cells if c],n_draws=2000))

header("TEST 6 - oscillator confluence NOT already covered (RSI/CMF already tested on PLAIN per v1.02)")
base_line()
st_ = stoch(H, L, C, 14, 3)
cells6=[]
for lo,hi in ((20,80),(30,70),(10,90)):
    cells6.append(evaluate(f"Stoch(14,3) not extreme ({lo}/{hi})",
        (lambda a,b_: (lambda c,i,x: np.isfinite(st_[i]) and (st_[i]<=b_ if x else st_[i]>=a)))(lo,hi)))
    cells6.append(evaluate(f"Stoch(14,3) WITH momentum ({lo}/{hi})",
        (lambda a,b_: (lambda c,i,x: np.isfinite(st_[i]) and (st_[i]>=a if x else st_[i]<=b_)))(50,50)))
rsi = CTX["rsi"]
for lo,hi in ((30,70),(40,60)):
    cells6.append(evaluate(f"RSI(14) not extreme ({lo}/{hi}) [re-check]",
        (lambda l_,h_: (lambda c,i,x: np.isfinite(rsi[i]) and (rsi[i]<=h_ if x else rsi[i]>=l_)))(lo,hi)))
cm = CTX["cmf"]
cells6.append(evaluate("CMF(20) agrees with direction [re-check]",
    lambda c,i,x: np.isfinite(cm[i]) and (cm[i]>0 if x else cm[i]<0)))
print("   best-of-N:", S.permutation_test_bestofN(BASE,[c['trades'] for c in cells6 if c],n_draws=2000))

header("TEST 7 - post-spike behaviour at H4 scale (continuation vs fade)")
atr = CTX["atr"]
body = (C - O)
with np.errstate(invalid="ignore"):
    z = body/atr
print("   Unconditional study over ALL H4 bars 2013-2026: forward return after a big bar")
print("   (signed by the spike's own direction; +ve = continuation, -ve = fade)")
print(f"   {'thr':>6} {'n':>6} " + " ".join(f"{k:>9}" for k in (1,2,3,6,12,24)))
for thr in (1.0, 1.5, 2.0, 2.5, 3.0):
    m = np.isfinite(z) & (np.abs(z) >= thr)
    m[-30:] = False
    idx = np.flatnonzero(m); sgn = np.sign(z[idx])
    row = []
    for k in (1,2,3,6,12,24):
        fwd = (C[np.minimum(idx+k, len(C)-1)] - C[idx]) * sgn / atr[idx]
        row.append(f"{np.nanmean(fwd):+9.4f}")
    print(f"   {thr:6.1f} {len(idx):6d} " + " ".join(row))
print("   (units = ATR; a real effect at H4 would need |mean| well above ~0.02-0.03 ATR)")
print("\n   t-stats for the same table (H0: no drift):")
for thr in (1.0, 2.0, 3.0):
    m = np.isfinite(z)&(np.abs(z)>=thr); m[-30:]=False
    idx=np.flatnonzero(m); sgn=np.sign(z[idx]); out=[]
    for k in (1,3,6,12,24):
        fwd=(C[np.minimum(idx+k,len(C)-1)]-C[idx])*sgn/atr[idx]
        out.append(f"k={k}: t={np.nanmean(fwd)/(np.nanstd(fwd)/np.sqrt(np.isfinite(fwd).sum())):+5.2f}")
    print(f"     thr={thr}: " + "  ".join(out))
print("\n   As an ENTRY FILTER on the shipped config:")
base_line()
cells7=[]
for thr in (1.0,1.5,2.0):
    cells7.append(evaluate(f"skip if |spike| >= {thr} ATR on signal bar",
        (lambda t: (lambda c,i,b: not (np.isfinite(z[i]) and abs(z[i])>=t)))(thr)))
    cells7.append(evaluate(f"REQUIRE aligned spike >= {thr} ATR",
        (lambda t: (lambda c,i,b: np.isfinite(z[i]) and (z[i]>=t if b else z[i]<=-t)))(thr)))
print("   best-of-N:", S.permutation_test_bestofN(BASE,[c['trades'] for c in cells7 if c],n_draws=2000))
