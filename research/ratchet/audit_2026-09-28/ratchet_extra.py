"""AUDIT: Ratchet untouched-window stress tests: (a) zero-spread real vs zero-spread random null,
(b) 2020-07..2022-07 sub-window (closest cost regime to today) real vs random,
(c) full in-build window 2022-07..2025-12 (excludes the 2026 window most tuning used) real vs random,
(d) ALIGNED random null (random timing only on stack-aligned bars, alignment direction)."""
import sys
sys.path.insert(0, "/home/user/test-project/research/ratchet"); sys.path.insert(1, "/home/user/test-project/research/aurelius")
from multiprocessing import Pool
import numpy as np, pandas as pd, sim as S, bars as B, engine as E
from ratchet_random_timing_test import pct_pf
G = {}
def rand_sig(rng, pf_, aligned):
    def f(ctx, t, p, stats=None):
        a = ctx["atr"][t-1]
        if not (a > 0): return None
        if aligned:
            up, dn = bool(ctx["al_up"][t-1]), bool(ctx["al_dn"][t-1])
            if not (up or dn): return None
            if rng.random() >= pf_: return None
            return (1 if up else -1), "random"
        if rng.random() >= pf_: return None
        return (1 if rng.random() < 0.5 else -1), "random"
    return f
def run(args):
    seed, pf_, aligned, a, b = args
    ctx = G["ctx"]; rng = np.random.default_rng(seed)
    S.entry_signal = rand_sig(rng, pf_, aligned)
    tr, _ = S.simulate(ctx, S.SHIPPED, start=a, end=b)
    return pct_pf(tr), len(tr)
def test(label, ctx, a, b, aligned=False, nd=160):
    G["ctx"] = ctx
    real, _ = S.simulate(ctx, S.SHIPPED, start=a, end=b); rpf = pct_pf(real); n = len(real)
    with Pool(4) as pool:
        pf_ = 0.01
        for it in range(6):
            ms = np.mean([x[1] for x in pool.map(run, [(900+it*10+r, pf_, aligned, a, b) for r in range(4)])])
            if abs(ms-n)/n < 0.04: break
            pf_ = min(0.9, pf_*n/max(ms,1))
        out = pool.map(run, [(s, pf_, aligned, a, b) for s in range(nd)])
    pool_ = np.array([x[0] for x in out]); pool_ = pool_[np.isfinite(pool_)]
    print(f"{label}: REAL n={n} %PF={rpf:.3f} | {'ALIGNED' if aligned else 'coin-flip'} null ({len(pool_)}, mean n={np.mean([x[1] for x in out]):.0f}) "
          f"median={np.median(pool_):.3f} p95={np.percentile(pool_,95):.3f} -> {100*(pool_<rpf).mean():.1f}th pct p={(pool_>=rpf).mean():.3f}", flush=True)
if __name__ == "__main__":
    CUT = pd.Timestamp("2022-07-04")
    m5x = E.load_m5_extended()
    oos = m5x[m5x.time < CUT][["time","open","high","low","close","tick_volume","spread"]].reset_index(drop=True)
    ctx = S.build_ctx(oos); ctx0 = dict(ctx); ctx0["spread"] = np.zeros_like(ctx["spread"])
    A, Bn = pd.Timestamp("2014-07-01"), CUT
    test("UNTOUCHED 2014-07..2022-07 ZERO spread", ctx0, A, Bn)
    test("UNTOUCHED 2020-07..2022-07 real spread", ctx, pd.Timestamp("2020-07-01"), Bn)
    test("UNTOUCHED 2014-07..2022-07 real spread", ctx, A, Bn, aligned=True)
    ctxi = S.build_ctx()
    test("BUILD window 2022-07..2025-12 real spread (pre-2026)", ctxi, pd.Timestamp("2022-10-01"), pd.Timestamp("2026-01-01"))
    test("BUILD window 2022-07..2025-12 real spread (pre-2026)", ctxi, pd.Timestamp("2022-10-01"), pd.Timestamp("2026-01-01"), aligned=True)
    test("2026 window real spread", ctxi, S.WIN_START, S.WIN_END, aligned=True)
