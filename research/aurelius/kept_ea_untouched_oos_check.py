"""
Follow-up to the textbook-batch gate tests (2026-09-26): their UNGATED
baselines were the first time Aurelius M5, Aurelius M15 and Meridian were
ever run on the untouched real 2014-06 -> 2022-07 history (every earlier
"survives K=50/100" result for these three is an IN-SAMPLE multiple-testing
argument on the 2022-2026 build window - only H&S had a real OOS test).
They came out flat-to-negative:
    Aurelius M5  OOS %PF 0.973 (n=2057)   vs IS 1.424
    Aurelius M15 OOS %PF 1.003 (n=1064)   vs IS 1.855
    Meridian     OOS %PF 0.796 (n=5709)   vs IS 1.209
This file checks whether that is the ENTRY SIGNAL failing, or the cost
regime: median M5 spread was 0.47-0.72 x ATR per trade in 2014-2019 vs
0.08-0.20 x ATR in 2024-2026 (printed below) - low-volatility years with the
same ~$0.30-0.40 spread make every trade 3-6x more expensive in ATR terms.
So, per system, on the untouched slice only, FROZEN shipped settings:
  (1) real %PF with the real recorded spread, and with spread = 0 (gross
      signal edge; the spread>60-point entry block is inert at 0 - disclosed),
  (2) the SAME random-timing baseline already used for each system
      (aurelius_random_timing_test.simulate_random_entry /
      meridian_random_timing_test.sim_random_entry - same exits, same real
      spread, coin-flip direction, calibrated trade count) - since random
      entries pay the same costs, the percentile is the cost-neutral answer
      to "does the entry timing still carry an edge on data it never saw?"
      K=1 is the right comparison here: nothing was selected on this data,
  (3) %PF by ~2-year block next to that block's spread/ATR.
Reporting only - no verdict in this repo is changed by this file; the
KEEP/WIND DOWN call is the user's.

RESULT (2026-09-26), untouched real 2014-06 -> 2022-07, frozen settings:
                 net %PF (n)     gross %PF   random-timing median  REAL pctile (p)
  Aurelius M5    0.973 (2057)    1.232       0.480                 100.0 (0.000)
  Aurelius M15   1.003 (1064)    1.121       0.711                 100.0 (0.000)
  Meridian       0.796 (5709)    1.026       0.765                  81.5 (0.185)
  (Ratchet, ratchet_untouched_oos_check.py: 0.542 (3808) / 1.016 / 0.508 / 84.5 (0.155))
READING: Aurelius's entry TIMING edge genuinely replicates on data it never
saw - it beats random timing paying the same spreads by a wide margin on
both M5 and M15 - but in that low-volatility, high-spread/ATR regime the
net result is ~breakeven (M5 blocks: 1.05 / 1.17 / 0.69 / 1.00). Meridian's
does NOT: on untouched data its timing is not distinguishable from random
(p=0.185), and it loses net (%PF 0.80) in every 2-year block. This is the
first real OOS evidence for either; their existing "survives K=50/100"
results are in-sample only.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from sim import simulate
import aurelius_random_timing_test as A
import meridian_random_timing_test as M
from m5_stack_variants_fixed_test import sim_filtered_entries
import pattern_rigor_common as R

CUTOFF = pd.Timestamp("2022-07-04")
N_RANDOM = 200
BLOCKS = ("2014-06-13", "2016-07-01", "2018-07-01", "2020-07-01", "2022-07-04")


def pf(p):
    return R.pct_pf_list(p)


def by_block(times, pcts, ratio_by_time):
    times = pd.to_datetime(times)
    out = []
    for a, b in zip(BLOCKS[:-1], BLOCKS[1:]):
        m = (times >= a) & (times < b)
        sub = np.asarray(pcts)[m]
        out.append(f"{a[:7]}..{b[:7]}: n={m.sum():4d} %PF={pf(sub):.3f} (spread/ATR {ratio_by_time(a, b):.2f})")
    return out


def spread_ratio_fn(df, atr):
    t = df["time"]
    r = df["spread"].values * E.POINT / atr

    def f(a, b):
        m = ((t >= a) & (t < b)).values & np.isfinite(r)
        return float(np.median(r[m])) if m.any() else float("nan")
    return f


def aurelius_block(label, df, h4, params):
    ctx = E.build_context(df, h4, params)
    real = simulate(ctx, params=params)
    pcts = [(x["exit_px"] - x["entry_px"]) * x["dir"] / x["entry_px"] for x in real]
    times = ctx["time"][[x["entry_i"] for x in real]]
    ctx0 = dict(ctx); ctx0["spread"] = np.zeros_like(ctx["spread"])
    gross = simulate(ctx0, params=params)
    gp = [(x["exit_px"] - x["entry_px"]) * x["dir"] / x["entry_px"] for x in gross]
    rng = np.random.default_rng(1)
    p_fire = A.calibrate_p_fire(ctx, params, rng, len(real))
    rng = np.random.default_rng(42)
    pool = np.array([A.pct_pf(A.simulate_random_entry(ctx, params, rng, p_fire)) for _ in range(N_RANDOM)])
    pool = pool[np.isfinite(pool)]
    report(label, pcts, gp, pool, times, spread_ratio_fn(df, ctx["atr"]))


def meridian_block(label, df, h4):
    trades, raw, close, high, low, spread, atr, n = M.build_real(df, h4)
    pf_fn = M.make_pct_pf(close, spread)
    pcts = []
    for (i, eb, pnl, is_buy) in trades:
        sc = spread[i + 1] * E.POINT
        pcts.append(pnl / (close[i] + sc if is_buy else close[i] - sc))
    times = df["time"].values[[t[0] for t in trades]]
    # gross: identical entries (the entry mask doesn't use spread), zero spread cost
    ctx = E.build_context(df, h4, params=E.P)
    ok = np.zeros(n, dtype=bool)
    for (i, *_rest) in trades:
        ok[i] = True
    zero = np.zeros_like(spread)
    g = sim_filtered_entries(raw, ok, close, high, low, zero, atr, n, M.SAFETY_SL)
    gp = [pnl / close[i] for (i, eb, pnl, ib) in g]
    rng = np.random.default_rng(1)
    p_fire = M.calibrate_p_fire(raw, close, high, low, spread, atr, n, rng, len(trades))
    rng = np.random.default_rng(42)
    pool = np.array([pf_fn(M.sim_random_entry(raw, close, high, low, spread, atr, n, rng, p_fire, M.SAFETY_SL))
                     for _ in range(N_RANDOM)])
    pool = pool[np.isfinite(pool)]
    report(label, pcts, gp, pool, times, spread_ratio_fn(df, ctx["atr"]))


def report(label, pcts, gp, pool, times, ratio_fn):
    real_pf = pf(pcts)
    pct = 100 * (pool < real_pf).mean(); p = (pool >= real_pf).mean()
    print(f"\n{label}")
    print(f"  real spread : n={len(pcts)}  win%={100*np.mean(np.array(pcts)>0):.1f}  %PF={real_pf:.3f}  net%={100*np.sum(pcts):.1f}")
    print(f"  zero spread : n={len(gp)}  %PF={pf(gp):.3f}  net%={100*np.sum(gp):.1f}   (gross signal edge)")
    print(f"  random timing, same exits + same real spread ({len(pool)} draws): median={np.median(pool):.3f}  "
          f"p95={np.percentile(pool,95):.3f}  -> REAL at {pct:.1f}th pct (p={p:.3f})")
    for line in by_block(times, pcts, ratio_fn):
        print("    " + line)


if __name__ == "__main__":
    h4 = E.load_h4()
    m5x = E.load_m5_extended()
    m5_oos = m5x[m5x["time"] < CUTOFF].reset_index(drop=True)
    m15n = E.load_m15_native()
    m15_oos = m15n[(m15n["time"] >= R.REAL_M15_START) & (m15n["time"] < CUTOFF)].reset_index(drop=True)
    print(f"UNTOUCHED slices: M5 {m5_oos['time'].min()} -> {m5_oos['time'].max()} ({len(m5_oos)} bars), "
          f"M15 {m15_oos['time'].min()} -> {m15_oos['time'].max()} ({len(m15_oos)} bars)")
    aurelius_block("Aurelius M5 (engine.P, frozen) - untouched 2014-06 -> 2022-07", m5_oos, h4, E.P)
    aurelius_block("Aurelius M15 (engine.P15, frozen) - untouched 2014-06 -> 2022-07 (native M15)", m15_oos, h4, E.P15)
    meridian_block("Meridian (frozen) - untouched 2014-06 -> 2022-07", m5_oos, h4)
