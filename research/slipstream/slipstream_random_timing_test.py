"""
FIRST random-timing + best-of-K rigor test for Slipstream_EA.mq5 (v1.08),
same discipline as research/ratchet/ratchet_random_timing_test.py and
research/aurelius/meridian_random_timing_test.py.

REAL SHIPPED CONSTRUCTION: engine.P_SHIPPED (read off the EA's literal
`input` lines) through sim.simulate(), the validated single-position OnTick
replica, windowed exactly as validate.py does it (signals zeroed before
2013-01-01, full history kept for EMA200 warm-up): uptrend = close>EMA200 and
EMA50 rising over 10 bars (mirror down), pullback to the SMA14 midline within
3 bars (touch tol 1.25xATR), Stochastic(14,3,3) %D signal-line turn,
indecision block, InpRequireConfluence (AuRebound/Tailwind condition within 2
bars, including the forming bar), blocked hours 0 and 12, no entries Friday
>= 16:00 / Saturday. Exit: structural stop (3-bar extreme + 0.75xATR, live on
the entry bar), 70% MFE lock once 1xATR in profit, close back through EMA50
(trend break), 200-bar max hold, 2-bar cooldown, the double-IsNewBar() entry
suppression. Spread is charged by sim.py itself on both sides at entry.

ADAPTATION: sim.simulate() accepts `sig=(sig_array, warm)` in place of
engine.base_signals(). The random null passes a random-direction / random-
timing array (calibrated to the real trade count) with
require_confluence=False and use_session_filter=False - confluence and the
fitted blocked-hour filter are ENTRY filters and part of what is being
tested; the Friday >=16:00 / Saturday no-entry rule (block_friday_close, a
separate flag) stays on for random entries as a practical weekend-risk rule.
The structural stop is computed by the same code for whatever direction was
drawn; MFE lock, trend-break exit, max hold and cooldown are unchanged.

GOLD_H4.csv spread is exactly 0 before mid-2014 (data gap); zero-spread bars
are imputed at the median non-zero spread (~30 pts) for real and random
alike. %PF on pnl / entry_price, never raw points.

K: this directory holds 5 research .py files (validation only). Slipstream's
values were tuned in Slipstream_Signals.mq5 (not in this repo): the EA header
documents a parameter sweep over BBPeriod, TouchTol and SLBuffer (20/1.0/0.5
-> 14/1.25/0.75), lookback and MFELockFrac sweeps, trendline-confirm and
confluence filters, and two blocked hours. The file count is a floor; K=30/50
are printed as documented-scale references.
"""
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N_RANDOM = 1000
K_FILES = 5


def _load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


E = _load("engine_slipstream", "engine.py")
S = _load("sim_slipstream", "sim.py")


def pct_arr(trades):
    return np.array([t["pnl"] / t["entry_px"] for t in trades])


def pct_pf(a):
    if len(a) == 0:
        return float("nan")
    gw = a[a > 0].sum(); gl = -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_sig(n, i0, rng, p_fire, p_long=0.5):
    fire = rng.random(n) < p_fire
    d = np.where(rng.random(n) < p_long, 1, -1)
    s = np.where(fire, d, 0).astype(int)
    s[:i0] = 0
    return s


def run_random(ctx, p_rand, i0, warm, rng, p_fire, p_long=0.5):
    return S.simulate(ctx, p_rand, sig=(random_sig(ctx["n"], i0, rng, p_fire, p_long), warm),
                      require_confluence=False)


def calibrate(ctx, p_rand, i0, warm, target_n, rng):
    p_fire = target_n / (ctx["n"] - i0)
    for _ in range(8):
        m = np.mean([len(run_random(ctx, p_rand, i0, warm, rng, p_fire)) for _ in range(5)])
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


if __name__ == "__main__":
    d, i0 = E.load_h4(start="2013-01-01", warmup_from_full=True)
    p = E.params()
    p_rand = E.params(use_session_filter=False)
    ctx = E.build_context(d, p)
    sp = ctx["spread"]; med = np.median(sp[sp > 0])
    ctx["spread"] = np.where(sp > 0, sp, med)
    n = ctx["n"]; cut = i0 + int((n - i0) * 0.7)
    sig = E.base_signals(ctx, p)
    sig0 = sig[0].copy(); sig0[:i0] = 0
    warm = max(sig[1], i0)
    print(f"GOLD H4 {d['time'].iloc[i0]} -> {d['time'].iloc[-1]}; zero spreads imputed at {med:.0f} pts; "
          f"70/30 cut {d['time'].iloc[cut]}")

    real = S.simulate(ctx, p, sig=(sig0, warm))
    ra = pct_arr(real); ei = np.array([t["entry_i"] for t in real])
    real_pf, oos_pf = pct_pf(ra), pct_pf(ra[ei >= cut])
    print(f"\nREAL Slipstream v1.08 shipped: n={len(ra)} win%={100*(ra>0).mean():.1f} sum%={100*ra.sum():.1f} "
          f"%PF={real_pf:.3f} | IS n={int((ei<cut).sum())} %PF={pct_pf(ra[ei<cut]):.3f} | "
          f"OOS n={int((ei>=cut).sum())} %PF={oos_pf:.3f}   (raw-$ PF {S.stats(real)['pf']:.3f})")

    rng = np.random.default_rng(1)
    p_fire = calibrate(ctx, p_rand, i0, warm, len(ra), rng)
    rng = np.random.default_rng(42)
    pool, pool_oos, ns = [], [], []
    for _ in range(N_RANDOM):
        tr = run_random(ctx, p_rand, i0, warm, rng, p_fire)
        a = pct_arr(tr); e = np.array([t["entry_i"] for t in tr])
        ns.append(len(a)); pool.append(pct_pf(a)); pool_oos.append(pct_pf(a[e >= cut]) if len(a) else np.nan)
    pool = np.array(pool); pool = pool[np.isfinite(pool)]
    pool_oos = np.array(pool_oos); pool_oos = pool_oos[np.isfinite(pool_oos)]
    print(f"\nrandom-timing null: p_fire={p_fire:.5f}, {len(pool)} draws, mean n={np.mean(ns):.0f} (target {len(ra)})")
    print(f"  null %PF median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    p1 = float((pool >= real_pf).mean())
    print(f"  REAL %PF={real_pf:.3f} -> {100*(pool<real_pf).mean():.1f}th percentile, one-sided p={p1:.4f}")
    print(f"  (supplementary) OOS-slice null median={np.median(pool_oos):.3f}; REAL OOS %PF={oos_pf:.3f} -> "
          f"p={float((pool_oos >= oos_pf).mean()):.4f}")
    longf = float(np.mean([t["dir"] > 0 for t in real]))
    rng = np.random.default_rng(900)
    dpool = np.array([pct_pf(pct_arr(run_random(ctx, p_rand, i0, warm, rng, p_fire, longf)))
                      for _ in range(N_RANDOM)])
    dpool = dpool[np.isfinite(dpool)]
    print(f"  (supplementary) direction-matched null (p_long={longf:.2f}): median={np.median(dpool):.3f} "
          f"p(K=1)={float((dpool >= real_pf).mean()):.4f}  p(K={K_FILES})={best_of_k(dpool, real_pf, K_FILES)[0]:.4f}")

    print(f"\nbest-of-K correction (K_FILES={K_FILES}; 30/50 = documented-scale reference):")
    for K in (1, K_FILES, 30, 50):
        pk, mk = best_of_k(pool, real_pf, K)
        print(f"  K={K:>3}: best-of-K median={mk:.3f}  p={pk:.4f}  [{verdict(pk)}]")
