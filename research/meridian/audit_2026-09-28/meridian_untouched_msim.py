"""AUDIT: EA-faithful msim.py V102 on the untouched 2014-07 -> 2022-07 GOLD M5 window,
with the same random-timing null as research/silver_btc/meridian_msim_transfer_test.py."""
import sys
sys.path.insert(0, "/home/user/test-project/research/silver_btc")
sys.path.insert(0, "/home/user/test-project/research/meridian")
sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(1, "/home/user/test-project/research/aurelius")
from dataclasses import replace
from multiprocessing import Pool
import numpy as np, pandas as pd
import msim as M, engine as E
import meridian_msim_transfer_test as T
CUT = pd.Timestamp("2022-07-04"); START = pd.Timestamp("2014-07-01")
G = {}
def rrun(args):
    seed, pf_, pl = args; cx = G["cx"]
    rng = np.random.default_rng(seed); n = len(cx["c"])
    fire = rng.random(n) < pf_; dirs = np.where(rng.random(n) < pl, 1, -1)
    tr, _ = M.simulate(cx, replace(M.V102, entry_fn=lambda c, t: int(dirs[t]) if fire[t] else 0), START, CUT)
    return T.pct(tr), None
if __name__ == "__main__":
    m5x = E.load_m5_extended()
    df = m5x[m5x.time < CUT][["time","open","high","low","close","tick_volume","spread"]].reset_index(drop=True)
    ctx = M.build_ctx(df); p = replace(M.V102)
    real, st = M.simulate(ctx, p, START, CUT)
    ra = T.pct(real); rpf = T.pct_pf(ra)
    from collections import Counter
    print(f"msim V102 untouched {START.date()}->{CUT.date()}: n={len(ra)} win%={100*(ra>0).mean():.1f} %PF={rpf:.3f} net%={100*ra.sum():.1f} exits {dict(Counter(t['reason'] for t in real))} stats {st}")
    ctx0 = dict(ctx); ctx0["spread"] = np.zeros_like(ctx["spread"])
    g, _ = M.simulate(ctx0, p, START, CUT); ga = T.pct(g)
    print(f"  zero spread: n={len(ga)} %PF={T.pct_pf(ga):.3f}")
    et = pd.to_datetime([t["entry_time"] for t in real])
    for a, b in zip(("2014-06","2016-07","2018-07","2020-07"), ("2016-07","2018-07","2020-07","2022-07")):
        m = (et >= a) & (et < b); print(f"   {a}..{b}: n={m.sum()} %PF={T.pct_pf(ra[m]):.3f}")
    # random null restricted to the same window: entry_fn only fires inside START..CUT (simulate is windowed anyway)
    for lab, cx in (("real spread", ctx), ("zero spread", ctx0)):
        target = len(ra) if lab == "real spread" else len(ga)
        tpf = rpf if lab == "real spread" else T.pct_pf(ga)
        G["cx"] = cx
        with Pool(4) as pool_:
            pf_ = target / len(df) * 1.3
            for it in range(8):
                ms = np.mean([len(x[0]) for x in pool_.map(rrun, [(10_000 + it*10 + r, pf_, 0.5) for r in range(4)])])
                if abs(ms - target)/target < 0.03: break
                pf_ = min(0.5, pf_ * target / ms)
            out = pool_.map(rrun, [(s, pf_, 0.5) for s in range(400)])
        pool = np.array([T.pct_pf(a) for a, _ in out]); ns = np.mean([len(a) for a, _ in out]); pool = pool[np.isfinite(pool)]
        print(f"  [{lab}] random null (400, mean n={ns:.0f} vs {target}): median={np.median(pool):.3f} p95={np.percentile(pool,95):.3f} -> real {tpf:.3f} at {100*(pool<tpf).mean():.1f}th pct, p={(pool>=tpf).mean():.4f}")
