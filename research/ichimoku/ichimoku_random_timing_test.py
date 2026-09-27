"""
FIRST random-timing + best-of-K rigor test for Ichimoku_EA.mq5 (v1.07), the
same discipline already applied to H&S / Aurelius / Vanguard / Ratchet /
Meridian (see research/ratchet/ratchet_random_timing_test.py and
research/aurelius/meridian_random_timing_test.py for the convention).

REAL SHIPPED CONSTRUCTION (read off Ichimoku_EA.mq5's own `input` lines, v1.05
default change, logic unchanged through v1.07): ENTRY_PLAIN (Tenkan/Kijun
cross while close is beyond the cloud) + ADX(14)>20, EXIT_CROSS with
InpMinHoldBars=8, InpSafetyStopATR=2.5 (Wilder ATR), Friday flatten at 21:00
(no entries after Fri 19:00). That is exactly engine.P_BEST_PLAIN_ADX, which
sim.simulate() (the validated event-driven OnTick replica) runs unmodified.

ADAPTATION: sim.simulate() already takes `entry_override` - a per-bar signal
array read in place of CheckEntry(). The random null passes a random array
(coin-flip direction, fired with a calibrated per-bar probability so the
mean trade count matches the real run). EVERYTHING downstream - the Friday
no-entry gate, fill at next open, the 2.5xATR broker stop (live on the
entry bar), the min-hold-gated TK-cross exit, the Friday 21:00 flatten - is
the unchanged sim code. Only the entry decision differs.

SPREAD: sim.py reports raw price P&L with NO spread charge. This file charges
one real spread per round trip from the H4 CSV's own per-bar `spread` column
on the FILL bar (spread * meta_point 0.01). GOLD_H4.csv records spread as
exactly 0 for every bar before mid-2014 (a data gap, not a free market), so
zero-spread bars are imputed at the median of the non-zero spreads (~30
points = $0.30) - applied identically to real and random trades.

%PF is computed on (pnl - spread) / entry_price, never raw points (GOLD went
~$1200 -> ~$4300 over this window).

WINDOW: 2013-01-01 -> end (engine.load_h4's session-standard window). The
shipped config was CHOSEN on this whole window, so there is no genuinely
untouched gold OOS; the 70/30 chronological IS/OOS split (sim.split_stats
convention) is reported for information, and the best-of-K correction is what
carries the multiple-testing burden - identical to the other gold-side tests.

K: this directory holds 20 dedicated Ichimoku research .py files (the file-
count convention the Ratchet (14) and Meridian (15) tests used). The EA's
own changelog documents a search that is plainly LARGER than 20 variants
(2 entry modes, Chikou on/off, 7 ADX thresholds, 7 confluence filters, a
4-24 bar min-hold plateau, a 1.0-5.0x stop sweep, 12 Coleman R:R configs,
200-EMA/cloud-rejection/Senkou-cross entries...), so K=50 is printed as a
stricter documented-scale reference alongside the file-count K.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/ichimoku")
import numpy as np
import engine as E
import sim as S

N_RANDOM = 1000
K_FILES = 20
POINT = 0.01   # GOLD_H4.csv meta_point


def spread_px(d):
    sp = d["spread"].values.astype(float)
    med = np.median(sp[sp > 0])
    return np.where(sp > 0, sp, med) * POINT, med


def pct_arr(trades, spx):
    return np.array([(t["pnl"] - spx[t["entry_i"]]) / t["entry_px"] for t in trades])


def pct_pf(a):
    if len(a) == 0:
        return float("nan")
    gw = a[a > 0].sum(); gl = -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_sig(n, rng, p_fire, p_long=0.5):
    fire = rng.random(n) < p_fire
    d = np.where(rng.random(n) < p_long, 1, -1)
    return np.where(fire, d, 0).astype(int)


def run_random(ctx, p, rng, p_fire, p_long=0.5):
    return S.simulate(ctx, p, entry_override=random_sig(ctx["n"], rng, p_fire, p_long))


def calibrate(ctx, p, target_n, rng):
    p_fire = target_n / ctx["n"]
    for _ in range(8):
        m = np.mean([len(run_random(ctx, p, rng, p_fire)) for _ in range(5)])
        if m <= 0:
            p_fire *= 3; continue
        if abs(m - target_n) / target_n < 0.03:
            break
        p_fire = min(0.9, p_fire * target_n / m)
    return p_fire


def verdict(p):
    return "SURVIVES" if p < 0.05 else ("borderline" if p < 0.15 else "DOES NOT SURVIVE")


def best_of_k(pool, real, K, seed=7):
    rng = np.random.default_rng(seed)
    b = pool[rng.integers(0, len(pool), size=(5000, K))].max(axis=1)
    return float((b >= real).mean()), float(np.median(b))


if __name__ == "__main__":
    d = E.load_h4("2013-01-01")
    p = E.P_BEST_PLAIN_ADX
    ctx = E.build_context(d, p)
    spx, med = spread_px(d)
    n = ctx["n"]; cut = int(n * 0.7)
    print(f"GOLD H4 {d['time'].iloc[0]} -> {d['time'].iloc[-1]}  n={n} bars; zero-spread bars imputed at "
          f"{med:.0f} pts; 70/30 cut at {d['time'].iloc[cut]}")

    real = S.simulate(ctx, p)
    ra = pct_arr(real, spx)
    ei = np.array([t["entry_i"] for t in real])
    real_pf, is_pf, oos_pf = pct_pf(ra), pct_pf(ra[ei < cut]), pct_pf(ra[ei >= cut])
    print(f"\nREAL Ichimoku v1.07 shipped (PLAIN+ADX>20, minhold 8, 2.5xATR stop, Fri flatten):")
    print(f"  n={len(real)}  win%={100*(ra>0).mean():.1f}  sum%={100*ra.sum():.1f}  %PF={real_pf:.3f}   "
          f"IS n={int((ei<cut).sum())} %PF={is_pf:.3f} | OOS n={int((ei>=cut).sum())} %PF={oos_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = calibrate(ctx, p, len(real), rng)
    rng = np.random.default_rng(42)
    pool, pool_oos, ns = [], [], []
    for _ in range(N_RANDOM):
        tr = run_random(ctx, p, rng, p_fire)
        a = pct_arr(tr, spx); e = np.array([t["entry_i"] for t in tr])
        ns.append(len(tr)); pool.append(pct_pf(a)); pool_oos.append(pct_pf(a[e >= cut]) if len(a) else np.nan)
    pool = np.array(pool); pool = pool[np.isfinite(pool)]
    pool_oos = np.array(pool_oos); pool_oos = pool_oos[np.isfinite(pool_oos)]
    print(f"\nrandom-timing null: p_fire={p_fire:.5f}, {len(pool)} draws, mean n={np.mean(ns):.0f} (target {len(real)})")
    print(f"  full-window null %PF median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pct = 100 * (pool < real_pf).mean(); p1 = float((pool >= real_pf).mean())
    print(f"  REAL full %PF={real_pf:.3f} -> {pct:.1f}th percentile, one-sided p={p1:.4f}")
    p1o = float((pool_oos >= oos_pf).mean())
    print(f"  (supplementary) OOS-slice null median={np.median(pool_oos):.3f}; REAL OOS %PF={oos_pf:.3f} "
          f"-> {100*(pool_oos<oos_pf).mean():.1f}th pct, p={p1o:.4f}")

    longf = float(np.mean([t["dir"] > 0 for t in real]))
    rng = np.random.default_rng(900)
    dpool = np.array([pct_pf(pct_arr(run_random(ctx, p, rng, p_fire, longf), spx)) for _ in range(N_RANDOM)])
    dpool = dpool[np.isfinite(dpool)]
    print(f"  (supplementary) direction-matched null (p_long={longf:.2f}): median={np.median(dpool):.3f}  "
          f"p(K=1)={float((dpool >= real_pf).mean()):.4f}  p(K={K_FILES})={best_of_k(dpool, real_pf, K_FILES)[0]:.4f}")

    print(f"\nbest-of-K correction (K_FILES={K_FILES} = this dir's research .py count; 50 = documented-scale):")
    for K in (1, K_FILES, 30, 50):
        pk, mk = best_of_k(pool, real_pf, K)
        print(f"  K={K:>3}: best-of-K median={mk:.3f}  p={pk:.4f}  [{verdict(pk)}]")
