"""
Does Ratchet_EA.mq5's frozen v3.30 shipped construction (sim.SHIPPED: 21/50/
150/600 EMA alignment + touch-21-pullback/fresh-alignment-momentum entry,
Bollinger/candle/slope/wick filters, 1.75xATR stop, trail+breakeven+runner-
trail, Stochastic exit, MAXBARS, weekend/session/holiday flatten, cooldown +
consecutive-loss breaker) transfer to SILVER and BTCUSD with the SAME
parameters, unchanged? Same cross-asset question already asked of H&S
(transfers cleanly), Aurelius (fails on both, even after a full tailored
retune) and Vanguard (fails on both, doesn't even beat random timing at K=1).

Data: each instrument's own real M5 export (SILVER_M5.csv from 2022-07,
BTCUSD_M5.csv from 2023-11 - both hit the same 300000-row MT5 export cap
GOLD_M5.csv did; native from each instrument's own export start, nothing to
trim). Full available history run in one pass (WIN_START/WIN_END are
GOLD-specific 2026-only constants in sim.py, not reused here).

BUGS AVOIDED (same class as every other cross-asset check this session):
1. sim.py's POINT is bound to bars.POINT (GOLD's 0.01) at MODULE IMPORT
   TIME and referenced unqualified inside simulate() - reassigning
   `S.POINT` before calling simulate() (not bars.B.POINT) is what actually
   takes effect, exactly like this file's own monkeypatching of
   S.entry_signal for random-timing baselines. SILVER's real point is
   0.001, a 10x difference from GOLD's - same overcharge bug already found
   and fixed for Aurelius/Silver.
2. sim.py hardcoded round(sl/entry, 2) (2 decimal places) for SL/entry
   prices in three places - correct for GOLD/BTCUSD (both meta_digits=2)
   but would silently destroy SILVER's real sub-cent precision
   (meta_digits=3, 0.001 point) e.g. rounding a 2.5xATR stop computed to
   the nearest $0.01 when the real tick is $0.001. Fixed at the source:
   RP now takes an explicit `digits` field (default 2, so every existing
   GOLD caller is byte-identical), used in place of the hardcoded 2 in all
   three round() calls.
3. RP.max_spread=60 is a raw-POINTS gate, same scale-mismatch problem
   already found for Aurelius/BTC (InpMaxSpreadPoints=60 blocking 99.3% of
   BTC entries, median BTC spread ~6000 points at this broker's BTCUSD
   quote convention). Checked here directly (SILVER_M5 median spread=34
   points, close to GOLD's 30 - the gate transfers fine to Silver;
   BTCUSD_M5 median spread=6000 points - the gate would block virtually
   every BTC entry). Reported below both AS SHIPPED (max_spread=60,
   faithful/frozen) and with the gate disabled (max_spread=0) for BTC only,
   as a diagnostic of whether the underlying signal+exit engine has ANY
   edge on BTC once it isn't simply starved of entries - same methodology
   already used for the real H&S-on-Bitcoin "no trades" investigation.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/ratchet")
from dataclasses import replace
import numpy as np
import pandas as pd
import sim as S
from ratchet_random_timing_test import make_random_entry_signal, pct_pf

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
N_RANDOM = 300


def load_m5(symbol):
    df = pd.read_csv(f"{DATA_DIR}/{symbol}_M5.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True)


def run(ctx, p, point, start, end, rng=None, p_fire=None):
    """Wraps S.simulate() with S.POINT patched to the instrument's own real
    point size for the duration of the call (see BUG #1 above)."""
    orig_point = S.POINT
    orig_entry = S.entry_signal
    S.POINT = point
    if rng is not None:
        S.entry_signal = make_random_entry_signal(rng, p_fire)
    try:
        tr, stats = S.simulate(ctx, p=p, start=start, end=end)
    finally:
        S.POINT = orig_point
        S.entry_signal = orig_entry
    return tr, stats


def calibrate_p_fire(ctx, p, point, start, end, rng, target_n, trials=4):
    p_fire = 0.01
    for _ in range(trials):
        tr, _ = run(ctx, p, point, start, end, rng, p_fire)
        if len(tr) == 0:
            p_fire *= 3
            continue
        p_fire *= target_n / len(tr)
        p_fire = min(max(p_fire, 1e-5), 0.9)
    return p_fire


def full_check(symbol, point, digits, max_spread_override=None, label=None):
    df = load_m5(symbol)
    ctx = S.build_ctx(df)
    start, end = df["time"].iloc[0], df["time"].iloc[-1] + pd.Timedelta(minutes=5)
    p = replace(S.SHIPPED, digits=digits)
    if max_spread_override is not None:
        p = replace(p, max_spread=max_spread_override)
    tag = label or f"{symbol} (digits={digits}, max_spread={p.max_spread})"
    print("=" * 78)
    print(f"{tag} -- Ratchet v3.30 frozen defaults, {start.date()} -> {end.date()}")
    print("=" * 78)

    real, stats = run(ctx, p, point, start, end)
    real_pf = pct_pf(real)
    if not real:
        print(f"  NO TRADES generated (blocked entries: {stats})\n")
        return
    pn = np.array([t["pnl"] / t["entry"] for t in real])
    print(f"  real: n={len(real)}  win%={100*(pn>0).mean():.1f}  %PF={real_pf:.3f}  "
          f"signals={stats['signals']}  blk_breaker={stats['blk_breaker']}")

    rng = np.random.default_rng(1)
    p_fire = calibrate_p_fire(ctx, p, point, start, end, rng, len(real))
    print(f"  calibrated p_fire={p_fire:.5f}")

    rng = np.random.default_rng(42)
    pool = []
    for _ in range(N_RANDOM):
        tr, _ = run(ctx, p, point, start, end, rng, p_fire)
        pool.append(pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    pctile = 100 * (pool < real_pf).mean()
    p_val = (pool >= real_pf).mean()
    print(f"  random-timing (same exits, {len(pool)} draws): median={np.median(pool):.3f}  "
          f"p95={np.percentile(pool,95):.3f}")
    print(f"  REAL %PF={real_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.4f})")

    rng2 = np.random.default_rng(7)
    print("  best-of-K (K=14 is Ratchet's own gold tuning-history estimate):")
    for K in (1, 14, 50, 100):
        best = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (best >= real_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"    K={K:>4}: best-of-K median={np.median(best):.3f}  p={p_k:.4f}  [{verdict}]")
    print()


if __name__ == "__main__":
    full_check("SILVER", point=0.001, digits=3)
    full_check("BTCUSD", point=0.01, digits=2, label="BTCUSD (AS SHIPPED, max_spread=60)")
    full_check("BTCUSD", point=0.01, digits=2, max_spread_override=0,
               label="BTCUSD (DIAGNOSTIC: spread gate disabled, max_spread=0)")
