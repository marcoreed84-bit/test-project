"""
FIRST random-timing + best-of-K rigor test for Tailwind_EA.mq5 (v1.06), same
discipline as research/ratchet/ratchet_random_timing_test.py and
research/aurelius/meridian_random_timing_test.py.

REAL SHIPPED CONSTRUCTION: engine.P_SHIPPED (read off the EA's literal
`input` lines) through sim.simulate(), the validated single-position OnTick
replica: fresh 3-bar run of closes above BOTH EMA21 and the SMA20 midline
(mirror for shorts), indecision-candle block, close >= 0.5xATR beyond the
midline, InpAvoidOpposing shadow filter (full AuRebound/Slipstream replica
walk), blocked hour 12, no entries Friday >= 16:00 / Saturday. Exit: close
back through the midline, 1.5xATR stop (live on the entry bar), 250-bar
max hold, 1-bar cooldown, the real double-IsNewBar() quirk. Spread is
charged on both sides by sim.py itself (buy at open+spread, sell at
open-spread, exits raw).

ADAPTATION: sim.simulate() accepts `sig=(sig_array, warm)` in place of
engine.base_signals(). The random null passes a random-direction / random-
timing array (calibrated so the mean trade count matches the real run) with
avoid_opposing=False - the shadow filter is an ENTRY filter and part of what
is being tested. Friday >=16:00 / Saturday no-entry is kept for random
entries (practical weekend-risk rule); blocked hour 12 is a fitted filter
and is not. Every exit rule runs through the identical sim code.

GOLD_H4.csv spread is exactly 0 before mid-2014 (data gap); zero-spread bars
are imputed at the median non-zero spread (~30 pts) for real and random
alike. %PF on pnl / entry_price, never raw points.

WINDOW: trades entered 2013-01-01 -> end (validate.py's split_stats window;
pre-2013 bars kept for warm-up). Shipped values were chosen on data covering
all of it (Tailwind_Signals.mq5's own sweep), so the 70/30 split is
informational and best-of-K carries the multiple-testing burden.

K: this directory holds only 4 research .py files (engine/sim/validate/
reconcile - validation, not tuning). The tuning happened in
Tailwind_Signals.mq5 (not in this repo): the EA's own input comments cite
sweeps of the entry distance, the SL buffer ("validated local optimum"),
the blocked hour ("hour 12 was the only clear loser" - a 24-way choice),
ATR-expanding filter, partial-close and the avoid-opposing filter. The file
count is therefore a floor; K=30/50 are printed as documented-scale refs.
"""
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
N_RANDOM = 1000
K_FILES = 4


def _load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


E = _load("engine_tailwind", "engine.py")
M = _load("sim_tailwind", "sim.py")


def pct_arr(trades, i0):
    return np.array([t["pnl"] / t["entry_px"] for t in trades if t["entry_i"] >= i0])


def entry_idx(trades, i0):
    return np.array([t["entry_i"] for t in trades if t["entry_i"] >= i0])


def pct_pf(a):
    if len(a) == 0:
        return float("nan")
    gw = a[a > 0].sum(); gl = -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_sig(ctx, p, i0, rng, p_fire, p_long=0.5):
    n = ctx["n"]
    fire = rng.random(n) < p_fire
    d = np.where(rng.random(n) < p_long, 1, -1)
    s = np.where(fire, d, 0).astype(int)
    s[:i0] = 0
    # practical weekend rule, read off the SIGNAL bar j-1 exactly as base_signals does
    dow_i = np.roll(ctx["dow"], 1); hour_i = np.roll(ctx["hour"], 1)
    s[(dow_i == 5) & (hour_i >= p["friday_cutoff_hour"])] = 0
    s[dow_i == 6] = 0
    return s


def run_random(ctx, p, i0, warm, rng, p_fire, p_long=0.5):
    return M.simulate(ctx, p, sig=(random_sig(ctx, p, i0, rng, p_fire, p_long), warm), avoid_opposing=False)


def calibrate(ctx, p, i0, warm, target_n, rng):
    p_fire = target_n / (ctx["n"] - i0)
    for _ in range(8):
        m = np.mean([len(entry_idx(run_random(ctx, p, i0, warm, rng, p_fire), i0)) for _ in range(5)])
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
    d, i0 = E.load_h4(start="2013-01-01")
    p = E.params()
    ctx = E.build_context(d, p)
    sp = ctx["spread"]; med = np.median(sp[sp > 0])
    ctx["spread"] = np.where(sp > 0, sp, med)
    n = ctx["n"]; cut = i0 + int((n - i0) * 0.7)
    sig = E.base_signals(ctx, p)
    warm = sig[1]
    print(f"GOLD H4 trades from {d['time'].iloc[i0]} -> {d['time'].iloc[-1]}; zero spreads imputed at {med:.0f} pts; "
          f"70/30 cut {d['time'].iloc[cut]}")

    real = M.simulate(ctx, p, sig=sig)
    ra = pct_arr(real, i0); ei = entry_idx(real, i0)
    real_pf, oos_pf = pct_pf(ra), pct_pf(ra[ei >= cut])
    print(f"\nREAL Tailwind v1.06 shipped: n={len(ra)} win%={100*(ra>0).mean():.1f} sum%={100*ra.sum():.1f} "
          f"%PF={real_pf:.3f} | IS n={int((ei<cut).sum())} %PF={pct_pf(ra[ei<cut]):.3f} | "
          f"OOS n={int((ei>=cut).sum())} %PF={oos_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = calibrate(ctx, p, i0, warm, len(ra), rng)
    rng = np.random.default_rng(42)
    pool, pool_oos, ns = [], [], []
    for _ in range(N_RANDOM):
        tr = run_random(ctx, p, i0, warm, rng, p_fire)
        a = pct_arr(tr, i0); e = entry_idx(tr, i0)
        ns.append(len(a)); pool.append(pct_pf(a)); pool_oos.append(pct_pf(a[e >= cut]) if len(a) else np.nan)
    pool = np.array(pool); pool = pool[np.isfinite(pool)]
    pool_oos = np.array(pool_oos); pool_oos = pool_oos[np.isfinite(pool_oos)]
    print(f"\nrandom-timing null: p_fire={p_fire:.5f}, {len(pool)} draws, mean n={np.mean(ns):.0f} (target {len(ra)})")
    print(f"  null %PF median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    p1 = float((pool >= real_pf).mean())
    print(f"  REAL %PF={real_pf:.3f} -> {100*(pool<real_pf).mean():.1f}th percentile, one-sided p={p1:.4f}")
    print(f"  (supplementary) OOS-slice null median={np.median(pool_oos):.3f}; REAL OOS %PF={oos_pf:.3f} -> "
          f"p={float((pool_oos >= oos_pf).mean()):.4f}")
    longf = float(np.mean([t["dir"] > 0 for t in real if t["entry_i"] >= i0]))
    rng = np.random.default_rng(900)
    dpool = np.array([pct_pf(pct_arr(run_random(ctx, p, i0, warm, rng, p_fire, longf), i0)) for _ in range(N_RANDOM)])
    dpool = dpool[np.isfinite(dpool)]
    print(f"  (supplementary) direction-matched null (p_long={longf:.2f}): median={np.median(dpool):.3f} "
          f"p(K=1)={float((dpool >= real_pf).mean()):.4f}")

    print(f"\nbest-of-K correction (K_FILES={K_FILES}; 30/50 = documented-scale reference):")
    for K in (1, K_FILES, 30, 50):
        pk, mk = best_of_k(pool, real_pf, K)
        print(f"  K={K:>3}: best-of-K median={mk:.3f}  p={pk:.4f}  [{verdict(pk)}]")
