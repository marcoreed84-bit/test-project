"""
Same random-timing/multiple-testing discipline applied to Ratchet_EA.mq5's
real shipped v3.28 (SHIPPED = sim.RP() defaults) construction, reusing the
ALREADY-BUILT real sequential simulator (sim.py's build_ctx/simulate/close)
completely unmodified for the exit side - trailing stop, breakeven, tail-
loss cap, Stochastic exit, MAXBARS, weekend/session flatten, the
consecutive-loss breaker, all byte-identical to what a real run uses.

ADAPTATION: entry_signal() is called by bare name inside simulate() (a
module-global lookup at call time, not a captured reference), so
monkeypatching sim.entry_signal to a random-direction/random-timing
version before calling sim.simulate() swaps ONLY the entry decision -
every downstream exit rule keeps running against whatever position that
random entry opened, completely unchanged. Same STOP_ATR=1.75x is used for
both (RP.stop_atr isn't touched), so this is a fair "same risk sizing,
random timing" test, same spirit as every other adaptation this session.

Window: WIN_START/WIN_END (2026-01-01 to 2026-09-21) - the same real
window this repo's real MT5 confirmation (research/portfolio/
combine_all7_real.py: net=9,273.91 ZAR) already covers.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import numpy as np
import sim as S

N_RANDOM = 300


def make_random_entry_signal(rng, p_fire):
    def f(ctx, t, p, stats=None):
        a = ctx["atr"][t - 1]
        if not (a > 0):
            return None
        if rng.random() >= p_fire:
            return None
        d = 1 if rng.random() < 0.5 else -1
        return d, "random"
    return f


def pct_pf(trades):
    if not trades:
        return float("nan")
    arr = np.array([t["pnl"] / t["entry"] for t in trades])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def run_random(ctx, rng, p_fire):
    orig = S.entry_signal
    S.entry_signal = make_random_entry_signal(rng, p_fire)
    try:
        trades, _ = S.simulate(ctx, p=S.SHIPPED)
    finally:
        S.entry_signal = orig
    return trades


def calibrate_p_fire(ctx, rng, target_n, trials=4):
    p_fire = 0.01
    for _ in range(trials):
        trades = run_random(ctx, rng, p_fire)
        if len(trades) == 0:
            p_fire *= 3
            continue
        p_fire *= target_n / len(trades)
        p_fire = min(max(p_fire, 1e-5), 0.9)
    return p_fire


if __name__ == "__main__":
    ctx = S.build_ctx()
    real_trades, real_stats = S.simulate(ctx, p=S.SHIPPED)
    real_pct_pf = pct_pf(real_trades)
    pnls = np.array([t["pnl"] for t in real_trades])
    print(f"REAL Ratchet v3.28 shipped defaults ({S.WIN_START.date()} -> {S.WIN_END.date()}): "
          f"n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  net={pnls.sum():.2f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = calibrate_p_fire(ctx, rng, len(real_trades))
    print(f"\nCalibrated p_fire={p_fire:.5f}")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines (same exit machinery)...")
    rng = np.random.default_rng(42)
    pool, ns = [], []
    for _ in range(N_RANDOM):
        tr = run_random(ctx, rng, p_fire)
        ns.append(len(tr))
        pool.append(pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry trade counts: mean={np.mean(ns):.0f} (target {len(real_trades)})")
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.3f})")

    print("\nMultiple-testing correction (best-of-K; K estimated from this dir's own 14 dedicated")
    print("Ratchet research files - candidates.py, features.py, momentum_test.py, robust_keep.py etc.):")
    rng2 = np.random.default_rng(7)
    for K in (1, 14, 30, 50):
        best = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (best >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p95={np.percentile(best,95):.3f}  "
              f"p={p_k:.3f}  [{verdict}]")
