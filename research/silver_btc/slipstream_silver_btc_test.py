"""
SUPPLEMENTARY cross-asset check: Slipstream (FROZEN gold parameters) on
SILVER and BTCUSD H4.

Status going in: research/slipstream/slipstream_random_timing_test.py found
Slipstream beats random timing on gold at K=1 (p=0.012) but is only
BORDERLINE at its file-count K=5 (p=0.057) and fails at the documented sweep
scale (K=30: p=0.270). It therefore did NOT clear its own honest K and does
not formally qualify for a transfer test; this is run anyway, labelled
supplementary, because it is cheap and answers "would it have mattered".

CONSTRUCTION: research/slipstream/sim.simulate at engine.P_SHIPPED, unchanged
(trend + SMA14 pullback + Stochastic %D turn + AuRebound/Tailwind confluence,
blocked hours 0/12, Friday cutoff; structural stop, MFE lock, EMA50 trend-
break exit, 200-bar max hold). H4 bars are resampled (lossless OHLC, repo
convention) from each instrument's native M15 export via common.resample.

PORTING CHECKS:
  * sim.simulate reads POINT from ITS OWN engine module (sim.E.POINT, GOLD's
    0.01) for the entry spread charge; it is set from each CSV's meta_point
    (SILVER 0.001, BTCUSD 0.01, asserted in common.load_m15).
  * Slipstream has no raw-points spread gate and no fixed-$ distances (stop,
    lock, touch tolerance are all ATR multiples) - nothing else to scale.
  * Session hours (blocked 0/12, Friday 16:00) are applied literally, as the
    EA would on any symbol.

Frozen params -> nothing searched here; verdict on common.py's fixed OOS
windows (SILVER 2021+, BTCUSD 2024+), FULL shown for context. Random null
and %PF exactly as the gold test (slipstream_random_timing_test). K=5 (its
gold K) and K=30 shown. %PF <= 1 never survives.
"""
import sys

import numpy as np

sys.path.insert(0, "/home/user/test-project/research/slipstream")
sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import slipstream_random_timing_test as SR  # noqa: E402
import common as C  # noqa: E402

K_REAL = 5
N_RANDOM = 1000


def evaluate(sym):
    df15, point = C.load_m15(sym)
    d = C.resample(df15, "4h")
    SR.S.E.POINT = point
    p = SR.E.params()
    p_rand = SR.E.params(use_session_filter=False)
    ctx = SR.E.build_context(d, p)
    n = ctx["n"]
    sig = SR.E.base_signals(ctx, p)
    warm = sig[1]
    oos_lo = int(np.searchsorted(d["time"].values, np.datetime64(C.SPLITS[sym][1])))
    real = SR.S.simulate(ctx, p, sig=sig)
    print("=" * 96)
    print(f"{sym} H4 (from native M15) {d['time'].iloc[0]} -> {d['time'].iloc[-1]} n={n} point={SR.S.E.POINT}; "
          f"OOS from {d['time'].iloc[oos_lo]}")
    rows = []
    for wname, lo in (("FULL", warm), ("OOS", oos_lo)):
        rt = [t for t in real if t["entry_i"] >= lo]
        ra = SR.pct_arr(rt)
        if len(ra) < 20:
            print(f"  [{wname}] n={len(ra)} -> too few trades")
            continue
        rpf = SR.pct_pf(ra)
        rng = np.random.default_rng(1)
        p_fire = SR.calibrate(ctx, p_rand, lo, max(warm, lo), len(ra), rng)
        rng = np.random.default_rng(42)
        pool = np.array([SR.pct_pf(SR.pct_arr(SR.run_random(ctx, p_rand, lo, max(warm, lo), rng, p_fire)))
                         for _ in range(N_RANDOM)])
        pool = pool[np.isfinite(pool)]
        p1 = float((pool >= rpf).mean())
        pK, _ = SR.best_of_k(pool, rpf, K_REAL)
        p30, _ = SR.best_of_k(pool, rpf, 30)
        v = SR.verdict(max(p1, pK))
        if rpf <= 1.0:
            v = "DOES NOT SURVIVE (net loser" + (", beats random)" if p1 < 0.05 else ")")
        print(f"  [{wname}] n={len(ra)} win%={100*(ra>0).mean():.1f} sum%={100*ra.sum():.1f} %PF={rpf:.3f} "
              f"long%={100*np.mean([t['dir'] > 0 for t in rt]):.0f}")
        print(f"         null median={np.median(pool):.3f} p95={np.percentile(pool, 95):.3f} -> "
              f"{100*(pool<rpf).mean():.1f}th pct; p(K=1)={p1:.4f} p(K={K_REAL})={pK:.4f} p(K=30)={p30:.4f} => {v}")
        rows.append((sym, wname, len(ra), rpf, p1, pK, v))
    return rows


if __name__ == "__main__":
    out = []
    for s in ("SILVER", "BTCUSD"):
        out += evaluate(s)
    print("\nSUMMARY (supplementary; verdict on OOS)")
    for r in out:
        print(f"  {r[0]:<7} {r[1]:<4} n={r[2]:>4} %PF={r[3]:.3f} p1={r[4]:.4f} p5={r[5]:.4f} -> {r[6]}")
