import numpy as np, pandas as pd, engine as E, sim as S
from collections import Counter
from battery import *
r2 = rsq_trend(C, 20)
F = lambda c,i,b: np.isfinite(r2[i]) and r2[i] > 0.5
tr = S.simulate(CTX, P, extra_filter=F)

print("=== 1. Mechanism: what is R2>0.5 actually selecting? ===")
print("   base exit mix:", Counter(t['reason'] for t in BASE), " median bars:", np.median([t['bars'] for t in BASE]))
print("   R2   exit mix:", Counter(t['reason'] for t in tr),  " median bars:", np.median([t['bars'] for t in tr]))
for nm, s in (("base", BASE), ("R2>0.5", tr)):
    p = np.array([t['pnl'] for t in s])
    print(f"   {nm:7s} avg_win={p[p>0].mean():7.2f} avg_loss={p[p<0].mean():7.2f} "
          f"win%={100*(p>0).mean():4.1f} |worst|={p.min():7.2f}")

print("\n=== 2. Drop the dominant year (2026 = 51% of net) ===")
for nm, keep in (("all years", lambda y: True), ("ex-2026", lambda y: y != 2026), ("ex-2026 & ex-2015", lambda y: y not in (2026,2015))):
    sub = [t for t in tr if keep(int(t['year']))]
    bsub = [t for t in BASE if keep(int(t['year']))]
    st = S.stats(sub)
    print(f"   {nm:18s} {S.fmt(st)}  perm-vs-base(same years)={S.permutation_test(bsub, sub, n_draws=2000)['percentile']}")

print("\n=== 3. Does the same R2 gradient appear on the base PLAIN signal WITHOUT ADX? ===")
P0 = E.params(entry_mode="PLAIN", use_adx=False, min_hold_bars=8, safety_stop_atr=2.5)
b0 = S.simulate(CTX, P0)
print(f"   PLAIN-noADX base : {S.fmt(S.stats(b0))}")
for th in (0.3,0.4,0.5,0.6):
    t0 = S.simulate(CTX, P0, extra_filter=(lambda x: (lambda c,i,b: np.isfinite(r2[i]) and r2[i]>x))(th))
    if len(t0) >= 15:
        pm = S.permutation_test(b0, t0, n_draws=2000)
        print(f"   PLAIN-noADX R2>{th}: {S.fmt(S.stats(t0))} perm={pm['percentile']}")

print("\n=== 4. Does it appear on BREAKOUT_FULL (validated variant)? independent-ish replication ===")
PB = E.P_BREAKOUT_VALIDATED
cb = E.build_context(d, PB); r2b = rsq_trend(cb['close'], 20)
bb = S.simulate(cb, PB)
print(f"   BF base          : {S.fmt(S.stats(bb))}")
for th in (0.3,0.5):
    tb = S.simulate(cb, PB, extra_filter=(lambda x: (lambda c,i,b: np.isfinite(r2b[i]) and r2b[i]>x))(th))
    if len(tb)>=10:
        print(f"   BF R2>{th}        : {S.fmt(S.stats(tb))} (n small - indicative only)")

print("\n=== 5. Scale-free control: R2 is unitless already, but check it is not a vol proxy ===")
atrp = CTX['atr']/C
m = np.isfinite(r2)&np.isfinite(atrp)
print(f"   corr(R2(20), ATR%/price) = {np.corrcoef(r2[m], atrp[m])[0,1]:+.3f}")
print(f"   corr(R2(20), ADX)        = {np.corrcoef(r2[m&np.isfinite(CTX['adx'])], CTX['adx'][m&np.isfinite(CTX['adx'])])[0,1]:+.3f}")
yr = CTX['year'][m]
print("   R2>0.5 share of bars by era:",
      {e: round(float((r2[m][(yr>=a)&(yr<=b)]>0.5).mean()),3) for e,(a,b) in
       {"2013-16":(2013,2016),"2017-20":(2017,2020),"2021-24":(2021,2024),"2025-26":(2025,2026)}.items()})
