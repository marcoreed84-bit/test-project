"""AUDIT: stricter random-timing null for Aurelius. The repo's null picks a coin-flip direction at
random bars; any entry against the MA stack is closed by ALIGN_BREAK on the very next bar after paying
spread, so the null is mostly spread-paying 1-bar trades. Here the null keeps the stack-alignment
(direction = alignment direction, only aligned bars) and randomises ONLY the timing, i.e. it asks
whether pullback/slope/volume/S-R/cross filters add anything beyond 'be aligned with the trend'.
Uses sim.simulate UNMODIFIED: quality gates disabled via params, pullback mask set to all-True,
random firing injected through extra_filter."""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
from multiprocessing import Pool
import numpy as np, pandas as pd
import engine as E
from sim import simulate
import aurelius_random_timing_test as A
import pattern_rigor_common as R
CUT = pd.Timestamp("2022-07-04")
G = {}
def pctpf(tr):
    return A.pct_pf(tr)
def null_params(p):
    q = dict(p); q.update(use_cross_filter=False, use_slope=False, max_slope_atr=0, use_volume=False,
                          use_sr_dist=False, use_momentum=False, use_slope_sr_block=False)
    return q
def run_null(args):
    seed, pf_ = args
    ctx, q = G["ctx0"], G["q"]
    rng = np.random.default_rng(seed); fire = rng.random(ctx["n"]) < pf_
    return simulate(ctx, extra_filter=lambda c, i, b: bool(fire[i]), params=q)
def run_coin(args):
    seed, pf_ = args
    return A.simulate_random_entry(G["ctx"], G["p"], np.random.default_rng(seed), pf_)
def evaluate(label, df, h4, p, nd=200):
    ctx = E.build_context(df, h4, p)
    real = simulate(ctx, params=p); rpf = pctpf(real); n = len(real)
    pn = np.array([(t["exit_px"]-t["entry_px"])*t["dir"]/t["entry_px"] for t in real])
    ctx0 = dict(ctx); ctx0["pullback_ok_buy"] = np.ones(ctx["n"], bool); ctx0["pullback_ok_sell"] = np.ones(ctx["n"], bool)
    q = null_params(p)
    G.update(ctx=ctx, ctx0=ctx0, q=q, p=p)
    with Pool(4) as pool:
        pf_ = 0.01
        for it in range(6):
            ms = np.mean([len(x) for x in pool.map(run_null, [(1000+it*10+r, pf_) for r in range(4)])])
            if abs(ms-n)/n < 0.03: break
            pf_ = min(0.9, pf_*n/max(ms,1))
        out = pool.map(run_null, [(s, pf_) for s in range(nd)])
        # repo coin-flip null for side-by-side + holding-time diagnostic
        pc = A.calibrate_p_fire(ctx, p, np.random.default_rng(1), n)
        coin = pool.map(run_coin, [(50000+s, pc) for s in range(60)])
    pool_pf = np.array([pctpf(t) for t in out]); pool_pf = pool_pf[np.isfinite(pool_pf)]
    coin_pf = np.array([pctpf(t) for t in coin])
    hold_r = np.median([t["exit_i"]-t["entry_i"] for t in real])
    c1 = np.mean([np.mean([(t["exit_i"]-t["entry_i"])<=1 for t in tr]) for tr in coin])
    n1 = np.mean([np.mean([(t["exit_i"]-t["entry_i"])<=1 for t in tr]) for tr in out])
    r1 = np.mean([(t["exit_i"]-t["entry_i"])<=1 for t in real])
    print(f"\n{label}\n  REAL n={n} win%={100*(pn>0).mean():.1f} %PF={rpf:.3f} net%={100*pn.sum():.1f} median hold={hold_r} bars, <=1-bar trades {100*r1:.0f}%")
    print(f"  repo coin-flip null (60 draws): median %PF={np.median(coin_pf):.3f}, <=1-bar trades {100*c1:.0f}%  -> real pct {100*(coin_pf<rpf).mean():.1f}")
    print(f"  ALIGNED random-timing null ({len(pool_pf)} draws, mean n={np.mean([len(t) for t in out]):.0f}): median={np.median(pool_pf):.3f} "
          f"p95={np.percentile(pool_pf,95):.3f}, <=1-bar {100*n1:.0f}% -> REAL at {100*(pool_pf<rpf).mean():.1f}th pct, p={(pool_pf>=rpf).mean():.3f}")
if __name__ == "__main__":
    h4 = E.load_h4()
    which = sys.argv[1:] or ["m5_is", "m5_oos", "m15_is", "m15_oos"]
    if "m5_is" in which: evaluate("Aurelius M5 IN-SAMPLE 2022-07..2026-09 (load_m5)", E.load_m5(), h4, E.P)
    if "m5_oos" in which:
        m5x = E.load_m5_extended(); evaluate("Aurelius M5 UNTOUCHED 2014-06..2022-07", m5x[m5x.time < CUT].reset_index(drop=True), h4, E.P)
    if "m15_is" in which: evaluate("Aurelius M15 IN-SAMPLE (resampled load_m5)", E.resample_m15_from_m5(E.load_m5()), h4, E.P15)
    if "m15_oos" in which:
        m15 = E.load_m15_native(); m15 = m15[(m15.time >= R.REAL_M15_START) & (m15.time < CUT)].reset_index(drop=True)
        evaluate("Aurelius M15 UNTOUCHED 2014-06..2022-07 (native M15)", m15, h4, E.P15)
