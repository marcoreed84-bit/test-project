"""
FIRST random-timing + best-of-K rigor test for Fulcrum_EA.mq5 (v2.13, M5) and
Fulcrum_M15_EA.mq5 (same trading code, P15 values), same discipline as
research/ratchet/ratchet_random_timing_test.py and
research/aurelius/meridian_random_timing_test.py. Fulcrum was dropped from
the live portfolio for correlation with Aurelius (SESSION_NOTES.md), never
for failing a statistical test - it had never been given one.

REAL SHIPPED CONSTRUCTION: engine.P / engine.P15 (read off the real `input`
declarations) through sim.simulate(), the validated OnTick replica: the
Aurelius-style ALIGN_MID stack (21>50>150>600 + price vs 2400, 50-EMA slope
0.5-1.0xATR, <=1 21/50 cross in 10 bars, pullback to the 50 within 10 bars,
volume ratio >=1.30, >=0.5xATR from 3-day D1 S/R), 5-bar cooldown; exit is a
native SL at the 50-EMA value at entry -/+ 0.15xATR and a native TP at a
FIXED $45 price distance (0.01 lots), plus the Friday 22:00 flatten. Spread
is charged by sim.py itself (buy at ask; sell SL/TP triggered on ask).

ADAPTATION (entry swapped, exit machinery byte-identical): simulate() reads
its entry decision from ctx arrays, so the random null runs the SAME
simulate() on a copy of ctx whose gate arrays are replaced:
  aligned_buy/aligned_sell -> a random coin-flip direction fired with a
      calibrated per-bar probability (mean trade count matched to real);
  crisscross=0, slope in-band, pullback ok, volume/SR fail-open (NaN) ->
      every signal filter passes, i.e. no signal information at all;
  m50 -> a synthetic anchor placed so the structural stop lands at
      D x ATR from the decision bar's close, with D drawn from the REAL
      trades' own empirical stop-distance distribution (in ATR units).
      The real stop IS "the 50 EMA wherever it happens to be"; the null gets
      the same risk geometry without the information that the 50 EMA is a
      level that just held.
Unchanged for random entries: the fixed $45 TP, stop order handling
(gap-through fills, both-hit = stop), Friday 22:00 flatten, and the
practical gates (cooldown, Friday no-entry, US-holiday block, 60-point
max-spread gate - GOLD points, correct on GOLD).

%PF on pnl / entry_price, never raw points. WINDOW: the full real M5 export
(2022-07 -> 2026-09). The shipped values were chosen on 2023-01 -> 2026-08,
so there is no untouched gold OOS; the 70/30 split is informational and the
best-of-K correction carries the multiple-testing burden.

K: this directory holds 7 research .py files (file-count convention). That
understates the real search: Fulcrum's ENTRY gate is Aurelius's own gate,
which was itself tuned across ~100 research files (the Aurelius M15 gold test
reported K=30/50/100), and Fulcrum added its own target sweep ($40-60) and
stop-buffer choice on top. K=30/50/100 are printed as the inherited-scale
reference.
"""
import sys

import numpy as np

sys.path.insert(0, "/home/user/test-project/research/fulcrum")
import engine as E  # noqa: E402
import sim as S     # noqa: E402

N_RANDOM = 1000
K_FILES = 7


def pct_arr(trades):
    return np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] / t["entry_px"] for t in trades])


def pct_pf(a):
    if len(a) == 0:
        return float("nan")
    gw = a[a > 0].sum(); gl = -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_ctx(ctx, p, rng, p_fire, dist_pool, p_long=0.5):
    n = ctx["n"]
    fire = rng.random(n) < p_fire
    buy = rng.random(n) < p_long
    D = dist_pool[rng.integers(0, len(dist_pool), size=n)]
    dirn = np.where(buy, 1.0, -1.0)
    r = dict(ctx)
    r["aligned_buy"] = fire & buy
    r["aligned_sell"] = fire & ~buy
    r["crisscross"] = np.zeros(n)
    mid = 0.5 * (p["min_slope_atr"] + (p["max_slope_atr"] if p["max_slope_atr"] > 0 else 2 * p["min_slope_atr"]))
    r["slope_buy"] = np.full(n, mid)
    r["slope_sell"] = np.full(n, mid)
    r["pullback_ok_buy"] = np.ones(n, bool)
    r["pullback_ok_sell"] = np.ones(n, bool)
    r["vol_ratio"] = np.full(n, np.nan)
    r["sr_dist_buy"] = np.full(n, np.nan)
    r["sr_dist_sell"] = np.full(n, np.nan)
    # stop_px = m50 -/+ buf*atr  ->  place m50 so stop sits D*ATR from close[i]
    r["m50"] = ctx["close"] - dirn * (D - p["stop_buffer_atr"]) * ctx["atr"]
    return r


def run_random(ctx, p, rng, p_fire, dist_pool, p_long=0.5):
    return S.simulate(random_ctx(ctx, p, rng, p_fire, dist_pool, p_long), params=p)


def calibrate(ctx, p, target_n, dist_pool, rng):
    p_fire = 3.0 * target_n / ctx["n"]
    for _ in range(8):
        m = np.mean([len(run_random(ctx, p, rng, p_fire, dist_pool)) for _ in range(4)])
        if m <= 0:
            p_fire *= 3; continue
        if abs(m - target_n) / target_n < 0.03:
            break
        p_fire = min(0.95, p_fire * target_n / m)
    return p_fire


def verdict(p):
    return "SURVIVES" if p < 0.05 else ("borderline" if p < 0.15 else "DOES NOT SURVIVE")


def best_of_k(pool, real, K, seed=7):
    rng = np.random.default_rng(seed)
    b = pool[rng.integers(0, len(pool), size=(5000, K))].max(axis=1)
    return float((b >= real).mean()), float(np.median(b))


def run(tag, P):
    df, h4, ctx = E.build_all(P)
    n = ctx["n"]; cut = int(n * 0.7)
    print("=" * 90)
    print(f"{tag}: GOLD {P['tf']} {df['time'].iloc[0]} -> {df['time'].iloc[-1]} ({n} bars); 70/30 cut {df['time'].iloc[cut]}")
    real = S.simulate(ctx, params=P)
    ra = pct_arr(real); ei = np.array([t["entry_i"] for t in real])
    real_pf, oos_pf = pct_pf(ra), pct_pf(ra[ei >= cut])
    print(f"REAL shipped: n={len(ra)} win%={100*(ra>0).mean():.1f} sum%={100*ra.sum():.1f} %PF={real_pf:.3f} | "
          f"IS n={int((ei<cut).sum())} %PF={pct_pf(ra[ei<cut]):.3f} | OOS n={int((ei>=cut).sum())} %PF={oos_pf:.3f}"
          f"   (raw-$ PF {S.stats(real)['pf']:.3f})")
    dist_pool = np.array([abs(t["entry_px"] - t["stop0"]) / t["entry_atr"] for t in real])

    rng = np.random.default_rng(1)
    p_fire = calibrate(ctx, P, len(ra), dist_pool, rng)
    rng = np.random.default_rng(42)
    pool, pool_oos, ns = [], [], []
    for _ in range(N_RANDOM):
        tr = run_random(ctx, P, rng, p_fire, dist_pool)
        a = pct_arr(tr); e = np.array([t["entry_i"] for t in tr])
        ns.append(len(a)); pool.append(pct_pf(a)); pool_oos.append(pct_pf(a[e >= cut]) if len(a) else np.nan)
    pool = np.array(pool); pool = pool[np.isfinite(pool)]
    pool_oos = np.array(pool_oos); pool_oos = pool_oos[np.isfinite(pool_oos)]
    print(f"random-timing null: p_fire={p_fire:.5f}, {len(pool)} draws, mean n={np.mean(ns):.0f} (target {len(ra)})")
    print(f"  null %PF median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    p1 = float((pool >= real_pf).mean())
    print(f"  REAL %PF={real_pf:.3f} -> {100*(pool<real_pf).mean():.1f}th percentile, one-sided p={p1:.4f}")
    print(f"  (supplementary) OOS-slice null median={np.median(pool_oos):.3f}; REAL OOS %PF={oos_pf:.3f} -> "
          f"p={float((pool_oos >= oos_pf).mean()):.4f}")
    longf = float(np.mean([t["dir"] > 0 for t in real]))
    rng = np.random.default_rng(900)
    dpool = np.array([pct_pf(pct_arr(run_random(ctx, P, rng, p_fire, dist_pool, longf))) for _ in range(N_RANDOM // 2)])
    dpool = dpool[np.isfinite(dpool)]
    print(f"  (supplementary) direction-matched null (p_long={longf:.2f}): median={np.median(dpool):.3f} "
          f"p(K=1)={float((dpool >= real_pf).mean()):.4f}  p(K={K_FILES})={best_of_k(dpool, real_pf, K_FILES)[0]:.4f}")
    print(f"best-of-K correction (K_FILES={K_FILES}; 30/50/100 = inherited Aurelius-gate scale):")
    for K in (1, K_FILES, 30, 50, 100):
        pk, mk = best_of_k(pool, real_pf, K)
        print(f"  K={K:>3}: best-of-K median={mk:.3f}  p={pk:.4f}  [{verdict(pk)}]")


if __name__ == "__main__":
    run("Fulcrum_EA.mq5 v2.13 (M5)", E.P)
    run("Fulcrum_M15_EA.mq5 (M15)", E.P15)
