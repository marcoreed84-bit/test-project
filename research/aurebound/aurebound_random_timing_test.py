"""
FIRST random-timing + best-of-K rigor test for AuRebound_EA.mq5 (v1.04), same
discipline as research/ratchet/ratchet_random_timing_test.py and
research/aurelius/meridian_random_timing_test.py.

REAL SHIPPED CONSTRUCTION: engine.P_SHIPPED (read line-by-line off the EA's
`input` declarations) through sim.simulate(), the validated single-position
OnTick replica: BB(20,2)-band touch within 3 bars + Stochastic(21,5,5) %D
signal-line turn -> fill at next open; structural stop (3-bar extreme +
0.5xATR, capped at 1.5xATR); breakeven snap on the first close through the
BB midline; 70% MFE lock once 1xATR in profit; opposite-band-reject exit
(after breakeven); 120-bar timeout; 2-bar cooldown; blocked hour 8; no new
entries Friday >= 16:00.

ADAPTATION: sim.simulate() calls `aeng.raw_signal(ctx, i, p)` by attribute
lookup at call time, so replacing aeng.raw_signal with a random-direction /
random-timing function swaps ONLY the entry decision. The stop distance is
still computed by the real compute_sl_dist() for whatever direction was
drawn, and every exit rule (breakeven, MFE lock + clamp, band-reject,
timeout, cooldown) runs unchanged. The random entry keeps the Friday >=16:00
no-entry rule (a practical weekend-risk constraint any live system needs)
but NOT the blocked-hour-8 rule, which is a fitted signal filter and is
part of what is being tested.

SPREAD (two corrections, applied identically to real and random trades):
  * sim.py charges spread on LONG entries only (short fills at the raw bid,
    exits are raw) - so shorts were modelled as spread-free. One spread is
    subtracted post-hoc from every short's P&L so both sides pay one
    round-trip spread, the convention every other test here uses.
  * GOLD_H4.csv's spread column is exactly 0 before mid-2014 (data gap).
    Zero-spread bars are imputed at the median non-zero spread (~30 pts).
%PF = sum of positive (pnl-cost)/entry over sum of negative, never raw
points.

WINDOW: 2013-01-01 -> end (the baseline.py session-standard window, full
pre-2013 history kept for indicator warm-up). The shipped values were chosen
on data overlapping all of it, so the 70/30 split is informational only and
best-of-K carries the multiple-testing burden.

K: this directory holds 6 research .py files (the file-count convention).
AuRebound's parameters were NOT tuned here - they came from the
AuRebound_Signals.mq5 indicator's own sweep (not in this repo), which the
EA's input comments show included at least a leave-one-fold-out choice of
blocked hour (24 candidates), two Stochastic trigger modes and the
indecision filter on/off - so the file count is a floor, and K=30/50 are
printed as the documented-scale reference.
"""
import importlib.util
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
N_RANDOM = 1000
K_FILES = 6


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


asim = _load("aurebound_sim", "sim.py")
aeng = asim.aeng          # the SAME module object sim.simulate() looks raw_signal up on
REAL_RAW_SIGNAL = aeng.raw_signal


def pct_arr(trades, ctx):
    sp = ctx["spread"]
    return np.array([(t["pnl"] - (sp[t["entry_i"]] if t["dir"] < 0 else 0.0)) / t["entry"] for t in trades])


def pct_pf(a):
    if len(a) == 0:
        return float("nan")
    gw = a[a > 0].sum(); gl = -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def run(ctx, p, i0, rng=None, p_fire=0.0, p_long=0.5):
    if rng is None:
        aeng.raw_signal = REAL_RAW_SIGNAL
    else:
        def rnd(ctx_, i, p_):
            if p_["BlockFridayClose"] and ctx_["dow"][i] == 4 and ctx_["hour"][i] >= p_["FridayCloseHour"]:
                return 0
            if rng.random() >= p_fire:
                return 0
            return 1 if rng.random() < p_long else -1
        aeng.raw_signal = rnd
    try:
        return asim.simulate(ctx, p, i0=i0, intrabar="stop_first")
    finally:
        aeng.raw_signal = REAL_RAW_SIGNAL


def calibrate(ctx, p, i0, target_n, rng):
    p_fire = 3.0 * target_n / (ctx["n"] - i0)
    for _ in range(8):
        m = np.mean([len(run(ctx, p, i0, rng, p_fire)) for _ in range(4)])
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
    p = aeng.params()
    d, _ = aeng.load_h4(start=None)
    ctx = aeng.build_context(d, p)
    sp = ctx["spread"]
    med = np.median(sp[sp > 0])
    ctx["spread"] = np.where(sp > 0, sp, med)
    i0 = max(aeng.first_tradable(ctx, p),
             int(np.searchsorted(d["time"].values, np.datetime64(pd.Timestamp("2013-01-01")))))
    n = ctx["n"]; cut = i0 + int((n - i0) * 0.7)
    print(f"GOLD H4 {d['time'].iloc[i0]} -> {d['time'].iloc[-1]} ({n - i0} bars); zero spreads imputed at "
          f"${med:.2f}; 70/30 cut {d['time'].iloc[cut]}")

    real = run(ctx, p, i0)
    ra = pct_arr(real, ctx); ei = np.array([t["entry_i"] for t in real])
    real_pf = pct_pf(ra)
    print(f"\nREAL AuRebound v1.04 shipped: n={len(real)} win%={100*(ra>0).mean():.1f} sum%={100*ra.sum():.1f} "
          f"%PF={real_pf:.3f} | IS n={int((ei<cut).sum())} %PF={pct_pf(ra[ei<cut]):.3f} | "
          f"OOS n={int((ei>=cut).sum())} %PF={pct_pf(ra[ei>=cut]):.3f}")
    oos_pf = pct_pf(ra[ei >= cut])

    rng = np.random.default_rng(1)
    p_fire = calibrate(ctx, p, i0, len(real), rng)
    rng = np.random.default_rng(42)
    pool, pool_oos, ns = [], [], []
    for _ in range(N_RANDOM):
        tr = run(ctx, p, i0, rng, p_fire)
        a = pct_arr(tr, ctx); e = np.array([t["entry_i"] for t in tr])
        ns.append(len(tr)); pool.append(pct_pf(a)); pool_oos.append(pct_pf(a[e >= cut]) if len(a) else np.nan)
    pool = np.array(pool); pool = pool[np.isfinite(pool)]
    pool_oos = np.array(pool_oos); pool_oos = pool_oos[np.isfinite(pool_oos)]
    print(f"\nrandom-timing null: p_fire={p_fire:.5f}, {len(pool)} draws, mean n={np.mean(ns):.0f} (target {len(real)})")
    print(f"  null %PF median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    p1 = float((pool >= real_pf).mean())
    print(f"  REAL %PF={real_pf:.3f} -> {100*(pool<real_pf).mean():.1f}th percentile, one-sided p={p1:.4f}")
    print(f"  (supplementary) OOS-slice null median={np.median(pool_oos):.3f}; REAL OOS %PF={oos_pf:.3f} -> "
          f"p={float((pool_oos >= oos_pf).mean()):.4f}")
    longf = float(np.mean([t["dir"] > 0 for t in real]))
    rng = np.random.default_rng(900)
    dpool = np.array([pct_pf(pct_arr(run(ctx, p, i0, rng, p_fire, longf), ctx)) for _ in range(N_RANDOM // 2)])
    dpool = dpool[np.isfinite(dpool)]
    print(f"  (supplementary) direction-matched null (p_long={longf:.2f}): median={np.median(dpool):.3f} "
          f"p(K=1)={float((dpool >= real_pf).mean()):.4f}")

    print(f"\nbest-of-K correction (K_FILES={K_FILES}; 30/50 = documented-scale reference):")
    for K in (1, K_FILES, 30, 50):
        pk, mk = best_of_k(pool, real_pf, K)
        print(f"  K={K:>3}: best-of-K median={mk:.3f}  p={pk:.4f}  [{verdict(pk)}]")
