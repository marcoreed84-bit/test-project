"""
Ratchet counterpart of research/aurelius/kept_ea_untouched_oos_check.py
(see its docstring). The textbook-batch gate test's ungated baseline was the
first run of Ratchet's FROZEN shipped v3.30 (sim.SHIPPED) on the untouched
real 2014-06 -> 2022-07 M5 history: %PF 0.542 (n=3808) vs 1.173 on
2022-07 -> 2026-09. Ratchet is the most cost-sensitive system in the book
(0.3xATR breakeven trigger, 0.5xATR trail trigger), and median M5 spread was
0.47-0.72 x ATR in 2014-2019 vs 0.08-0.20 x ATR in 2024-2026.

Same three checks: real vs zero spread (sim.RP.max_spread's entry block is
inert at zero spread - disclosed), the SAME random-timing baseline as
ratchet_random_timing_test.py (monkeypatched entry_signal, every exit rule
unchanged - reimplemented here only because that file's run_random() has no
start/end arguments), and %PF by ~2-year block with its spread/ATR.
Reporting only - no verdict changed.

RESULT (2026-09-26), untouched real 2014-07 -> 2022-07, frozen v3.30:
  real spread n=3808 win%=39.4 %PF=0.542 (net -91%); zero spread %PF=1.016;
  random timing (same exits, same spread, 200 draws) median 0.508, p95 0.568
  -> REAL at 84.5th pct (p=0.155) - NOT distinguishable from random timing
  on untouched data. Every 2-year block loses (0.61 / 0.44 / 0.51 / 0.57),
  including 2020-22 when spread/ATR (0.27) was already close to 2022-23's.
  Ratchet's "survives K=50" is an in-sample (2026-window) result; this is
  the first real OOS evidence and it does not support it.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import numpy as np
import pandas as pd
import sim as S
import bars as B
from ratchet_random_timing_test import make_random_entry_signal, pct_pf
sys.path.insert(1, "/home/user/test-project/research/aurelius")
import engine as E

CUTOFF = pd.Timestamp("2022-07-04")
START = pd.Timestamp("2014-07-01")
N_RANDOM = 200
BLOCKS = ("2014-06-13", "2016-07-01", "2018-07-01", "2020-07-01", "2022-07-04")


def run(ctx, start, end, rng=None, p_fire=None):
    if rng is None:
        tr, _ = S.simulate(ctx, p=S.SHIPPED, start=start, end=end)
        return tr
    orig = S.entry_signal
    S.entry_signal = make_random_entry_signal(rng, p_fire)
    try:
        tr, _ = S.simulate(ctx, p=S.SHIPPED, start=start, end=end)
    finally:
        S.entry_signal = orig
    return tr


if __name__ == "__main__":
    m5x = E.load_m5_extended()
    oos = m5x[m5x["time"] < CUTOFF][["time", "open", "high", "low", "close", "tick_volume", "spread"]].reset_index(drop=True)
    ctx = S.build_ctx(oos)
    real = run(ctx, START, CUTOFF)
    real_pf = pct_pf(real)
    pn = np.array([t["pnl"] / t["entry"] for t in real])
    print(f"Ratchet v3.30 (sim.SHIPPED, frozen) - untouched {START.date()} -> {CUTOFF.date()}")
    print(f"  real spread : n={len(real)}  win%={100*(pn>0).mean():.1f}  %PF={real_pf:.3f}  net%={100*pn.sum():.1f}")
    ctx0 = dict(ctx); ctx0["spread"] = np.zeros_like(ctx["spread"])
    g = run(ctx0, START, CUTOFF)
    gp = np.array([t["pnl"] / t["entry"] for t in g])
    print(f"  zero spread : n={len(g)}  %PF={pct_pf(g):.3f}  net%={100*gp.sum():.1f}   (gross signal edge)")

    rng = np.random.default_rng(1)
    p_fire = 0.01
    for _ in range(4):
        tr = run(ctx, START, CUTOFF, rng, p_fire)
        p_fire = min(max(p_fire * len(real) / max(len(tr), 1), 1e-5), 0.9)
    rng = np.random.default_rng(42)
    pool = np.array([pct_pf(run(ctx, START, CUTOFF, rng, p_fire)) for _ in range(N_RANDOM)])
    pool = pool[np.isfinite(pool)]
    pct = 100 * (pool < real_pf).mean(); p = (pool >= real_pf).mean()
    print(f"  random timing, same exits + same real spread ({len(pool)} draws): median={np.median(pool):.3f}  "
          f"p95={np.percentile(pool,95):.3f}  -> REAL at {pct:.1f}th pct (p={p:.3f})")

    times = pd.to_datetime([t["entry_time"] for t in real])
    ratio = ctx["spread"] * B.POINT / ctx["atr"]
    tt = ctx["time"]
    for a, b in zip(BLOCKS[:-1], BLOCKS[1:]):
        m = (times >= a) & (times < b)
        mm = ((tt >= a) & (tt < b)).values & np.isfinite(ratio)
        print(f"    {a[:7]}..{b[:7]}: n={m.sum():4d} %PF={pct_pf([real[i] for i in np.where(m)[0]]):.3f} "
              f"(spread/ATR {np.median(ratio[mm]):.2f})")
