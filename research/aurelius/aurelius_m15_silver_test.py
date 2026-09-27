"""
Does Aurelius M15's frozen v1.56 defaults (the second-strongest-evidenced
system in this project, gold-only until now) transfer to SILVER with the
SAME parameters, unchanged? Same question as hs_silver_test.py, for the
other system that's actually survived genuine out-of-sample scrutiny on
gold.

Data: user's 2026-09-27 SILVER M15 export, trimmed to real M15 only
(2014-06-12 onward - see SILVER_M15_native.csv / hs_silver_test.py for the
contamination story, identical to gold's). No native SILVER H4 export
exists yet, so H4 is resampled from the same real M15 (lossless, H4 = 16
M15 bars - same aggregation convention as engine.py's own
resample_m15_from_m5). engine.py's build_context only uses h4 to derive
D1 H/L via derive_d1_from_h4() for an S/R-distance filter - a resampled H4
reproduces that exactly the same way a native export would, since it's
pure OHLC aggregation, not a separate data source.

The ENTIRE silver dataset is genuinely untouched by any parameter search -
unlike gold, there's no in-sample portion to worry about excluding.

CORRECTION (2026-09-27, found building aurelius_tailored_common.py): this
file charged Silver's spread at GOLD's point. sim.simulate() multiplied the
spread column by engine.POINT = 0.01, but SILVER's meta_point is 0.001, so
every trade paid 10x its real spread (median 33 points = $0.033 real,
charged $0.33, several M15 ATRs). The previously reported "%PF 0.042, win
rate 1.16%, every exit pathway loses" was that artifact. Fixed below by
passing point=0.001 through params (the 60-point entry gate is kept - it
IS the frozen EA's own input, in Silver's own points). Corrected: n=1731,
%PF 0.647, win 18.4% - frozen gold Aurelius still loses on Silver, but not
catastrophically. Its random-timing percentile is 100 (random median 0.306)
at every K - i.e. the ENTRY TIMING genuinely beats random entries paying
the same spread, but the "SURVIVES" labels this file prints only mean
"better than random", NOT profitable: %PF < 1, a net loser. The joint per-instrument retune that followed is in
aurelius_silver_tailored_test.py.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from sim import simulate
import aurelius_random_timing_test as A

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
N_RANDOM = 600


def load_m15_silver():
    df = pd.read_csv(f"{DATA_DIR}/SILVER_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True)


def resample_h4_from_m15(df15):
    d = df15.set_index("time")
    o = d["open"].resample("4h").first()
    h = d["high"].resample("4h").max()
    l = d["low"].resample("4h").min()
    c = d["close"].resample("4h").last()
    v = d["tick_volume"].resample("4h").sum()
    sp = d["spread"].resample("4h").mean()
    out = pd.DataFrame(dict(open=o, high=h, low=l, close=c, tick_volume=v, spread=sp)).dropna()
    return out.reset_index()


if __name__ == "__main__":
    df15 = load_m15_silver()
    h4 = resample_h4_from_m15(df15)
    print(f"SILVER M15: n={len(df15)} bars, {df15['time'].min()} -> {df15['time'].max()} "
          f"({(df15['time'].max()-df15['time'].min()).days/365.25:.1f} yrs) - "
          f"never touched by any parameter search")

    PS = dict(E.P15, point=0.001)   # SILVER's real point - see CORRECTION above
    ctx15 = E.build_context(df15, h4, PS)
    n = ctx15["n"]

    real_trades = simulate(ctx15, params=PS)
    real_pct_pf = A.pct_pf(real_trades)
    print(f"\nREAL Aurelius M15 v1.56 defaults (UNCHANGED params) on SILVER: n={len(real_trades)}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = A.calibrate_p_fire(ctx15, PS, rng, len(real_trades))
    print(f"Calibrated p_fire={p_fire:.5f}")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines on SILVER...")
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(N_RANDOM):
        tr = A.simulate_random_entry(ctx15, PS, rng, p_fire)
        pool.append(A.pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.4f})")

    print("\nMultiple-testing correction (best-of-K; same K ladder used on gold):")
    rng2 = np.random.default_rng(7)
    for K in (1, 30, 50, 100):
        best = pool[rng2.integers(0, len(pool), size=(2000, K))].max(axis=1)
        p_k = (best >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p={p_k:.4f}  [{verdict}]")
