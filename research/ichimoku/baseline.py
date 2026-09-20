import numpy as np, engine as E, sim as S
d = E.load_h4("2013-01-01")

BASE_P = E.params(entry_mode="PLAIN", use_adx=False, min_hold_bars=8, safety_stop_atr=2.5, close_friday=True)
BEST_P = E.P_BEST_PLAIN_ADX
CTX = E.build_context(d, BEST_P)
base = S.simulate(CTX, BASE_P)    # PLAIN, no ADX, same exit shape
best = S.simulate(CTX, BEST_P)    # PLAIN + ADX
n = CTX["n"]

def report(lbl, tr, base_tr=None):
    st = S.stats(tr); ny,ty = S.neg_years(tr)
    i_,o_ = S.split_stats(tr, n)
    print(f"{lbl}")
    print(f"   {S.fmt(st)} negyr={ny}/{ty}")
    print(f"   IS : {S.fmt(i_)}")
    print(f"   OOS: {S.fmt(o_)}")
    print(f"   tail: {S.tail_concentration(tr)}")
    if base_tr is not None:
        print(f"   perm vs base-signal subsets: {S.permutation_test(base_tr, tr)}")
    return st

print("=== BASELINE: PLAIN, NO ADX, same exit shape (flatten+2.5x stop+minhold8) ===")
report("base", base)
print()
print("=== SHIPPED-DOCUMENTED-BEST: PLAIN + ADX(14)>20 ===")
report("best", best, base)
print("   header claims: perm percentile 97.6/97.3, OOS beats IS, 12/14 years positive")
print()
print("=== FILE'S ACTUAL DEFAULT: BREAKOUT_FULL + flatten + 2.5x stop + minhold8 ===")
pf = E.P_FILE_DEFAULT; cf = E.build_context(d, pf)
report("file-default", S.simulate(cf, pf))
print()
print("=== BREAKOUT_FULL as validated (no flatten, no stop, no minhold) ===")
pv = E.P_BREAKOUT_VALIDATED; cv = E.build_context(d, pv)
report("BF-validated", S.simulate(cv, pv))
print()
print("=== BREAKOUT_FULL: isolating which default hurts ===")
for lbl, ov in [("+flatten only", dict(close_friday=True, min_hold_bars=0, safety_stop_atr=0.0)),
                ("+stop2.5 only", dict(close_friday=False, min_hold_bars=0, safety_stop_atr=2.5)),
                ("+minhold8 only", dict(close_friday=False, min_hold_bars=8, safety_stop_atr=0.0)),
                ("+flatten+stop", dict(close_friday=True, min_hold_bars=0, safety_stop_atr=2.5)),
                ("ALL (file default)", dict(close_friday=True, min_hold_bars=8, safety_stop_atr=2.5))]:
    pp = E.params(entry_mode="BREAKOUT_FULL", **ov)
    cc = E.build_context(d, pp); tt = S.simulate(cc, pp); ny,ty=S.neg_years(tt)
    print(f"   {lbl:20s} {S.fmt(S.stats(tt))} negyr={ny}/{ty}")
np.save("/tmp/none.npy", np.array([0]))
