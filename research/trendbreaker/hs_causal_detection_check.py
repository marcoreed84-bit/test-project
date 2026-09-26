"""
BUG CHECK (found 2026-09-26 while building the textbook-batch gate tests):
the H&S RESEARCH simulator has the same lookahead class as the Wolfe Wave /
Bump-and-Run bugs. hs_next_round_test.find_breakouts_full() - reused by
hs_stacked_random_baseline_test.py, hs_m15_oos_test.py and
multiple_testing_correction_test.py - does two things the live EA cannot:
  (1) it counts neckline-break closes from i_s2+1, but the right shoulder is
      a PIVOT_STRENGTH(5)-bar fractal and isn't knowable until bar i_s2+5.
      On the 2022-2026 M15 set, 256 of 998 breakouts (26%) complete their 3
      confirming closes before the pattern could exist at all (median
      brk_q - i_s2 = 9 bars, 10th pct = 3).
  (2) it runs find_hs_patterns() on the FINAL zigzag, which silently drops
      shapes whose provisional right shoulder was later replaced.
HeadShoulders_EA.mq5 ITSELF IS CAUSAL - Recompute() only queues a shape once
FindSwings() has confirmed its right shoulder, and AdvancePending() counts
closes only from then on (it looks at the single newest closed bar each
tick, run counter starting at 0 when the shape is queued). So the LIVE EA is
not affected; what is affected is the Python EVIDENCE for it (the %PF and
random-timing percentiles quoted for H&S).

This file rebuilds the breakout list EA-faithfully: shapes found from
causal_swing_events() snapshots (every shape the EA's per-bar Recompute()
would ever queue, deduped by its (s1, head, s2) anchors exactly like
AlreadyKnown()), closes counted from the bar the right shoulder became
knowable (i_s2 + PIVOT_STRENGTH, inclusive - that close is known at the
same moment as the pivot, matching AdvancePending's order), same shoulder
tolerance / break tol 0.35 / 3 closes / horizon as find_breakouts_full().
(The causal detector now lives in hs_next_round_test.py as the DEFAULT
find_breakouts_full(); this file compares it against causal=False.)
The stacked-combo trade logic (eval_pullback_and_runner_pct), the %PF and
the random-timing replay (replay_bracket_at, vectorized here and checked
identical) are all unchanged. Then it re-runs the SAME rigor on:
  - IS: the 2022-2026 M15 window H&S was built on (resampled real M5),
  - OOS: the native M15 2014-06 -> 2022-07 slice - the genuinely real part
    of hs_m15_oos_test.py's "2001-2022" slice (before 2014-06-13 that file
    is daily then hourly bars, see pattern_rigor_common.py).

RESULT (2026-09-26), stacked combo, random-timing pool of 1500 draws:
                                    breakouts   n    %PF    pctile   K=27 p  K=50 p  K=100 p
  IS 2022-26  original (lookahead)     998     408  2.014   100.0    0.000   0.000   0.000
  IS 2022-26  CAUSAL                  1122     403  1.961   100.0    0.000   0.000   0.000
  OOS 2014-06->2022-07 original       1970     813  1.490   100.0    0.000   0.000   0.000
  OOS 2014-06->2022-07 CAUSAL         2150     798  1.442    99.9    0.030   0.064   0.124
  (hs_m15_oos_test's old mixed slice: original 1.717/n=855 - inflated by
   ~42 trades on mislabeled daily/hourly bars, see pattern_rigor_common.py)
VERDICT: H&S stays KEEP - still clearly beats random timing on genuinely
untouched data and survives its own K floor (27) - but the honest OOS
evidence is ~8 years at %PF ~1.44 (borderline at K=50), not the previously
quoted "21 years, %PF 1.717, 100th percentile".
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
import pattern_rigor_common as R
from h4_touch_reaction_test import sma_atr, ATR_PERIOD, PIVOT_STRENGTH, BREAK_CONFIRM_CLOSES
from head_shoulders_target_test import SHOULDER_TOL_ATR, MAX_HORIZON_MULT, MAX_HORIZON_CAP
from hs_next_round_test import find_breakouts_full, find_breakouts_causal, STOP_BUFFER
import hs_stacked_random_baseline_test as H

BREAK_TOL = 0.35
OOS_CUTOFF = pd.Timestamp("2022-07-04")
HS_K = (1, 27, 50, 100)   # 27 = H&S's own K floor (multiple_testing_correction_test.py)
N_POOL = 1500


def replay_fast(h, l, c, n, q0, top, stop_pct, target_pct, trail_pct, cap=H.MAX_HORIZON_CAP):
    """Vectorized hs_stacked_random_baseline_test.replay_bracket_at()."""
    entry = c[q0]
    stop = entry * (1 + stop_pct) if top else entry * (1 - stop_pct)
    target = entry * (1 - target_pct) if top else entry * (1 + target_pct)
    trail = trail_pct * entry
    mh = min(n - 1, q0 + cap)
    hs, ls = h[q0 + 1:mh + 1], l[q0 + 1:mh + 1]
    m = len(hs)
    if m == 0:
        return 0.0
    if top:
        hit_s, hit_t = hs >= stop, ls <= target
    else:
        hit_s, hit_t = ls <= stop, hs >= target
    s = int(np.argmax(hit_s)) if hit_s.any() else m
    t = int(np.argmax(hit_t)) if hit_t.any() else m
    if s <= t and s < m:
        exit_px = stop
    elif t < m:
        # target reached at bar t (stop not hit at or before it): trail from there
        if top:
            peak = np.minimum.accumulate(np.minimum(ls[t:], target))
            cur = np.minimum(stop, peak + trail)            # stop in force AFTER each bar
            chk = hs[t + 1:] >= cur[:-1]
        else:
            peak = np.maximum.accumulate(np.maximum(hs[t:], target))
            cur = np.maximum(stop, peak - trail)
            chk = ls[t + 1:] <= cur[:-1]
        if chk.any():
            k = int(np.argmax(chk))
            exit_px = cur[k]
        else:
            exit_px = c[mh]
    else:
        exit_px = c[mh]
    pnl = (entry - exit_px) if top else (exit_px - entry)
    return pnl / entry


def pool_fast(real, h, l, c, rng, n_runs=N_POOL):
    n = len(c)
    lo, hi = H.MAX_HORIZON_CAP, n - H.MAX_HORIZON_CAP - 1
    pfs = []
    for _ in range(n_runs):
        qs = rng.integers(lo, hi, size=len(real))
        pcts = [replay_fast(h, l, c, n, int(q), r["top"], r["stop_pct"], r["target_pct"], r["trail_pct"])
                for q, r in zip(qs, real)]
        pfs.append(R.pct_pf_list(pcts))
    pfs = np.array(pfs)
    return pfs[~np.isnan(pfs) & ~np.isinf(pfs)]


def check_replay():
    df = E.resample_m15_from_m5(E.load_m5()).iloc[:40000].reset_index(drop=True)
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    n = len(c); rng = np.random.default_rng(3)
    for _ in range(3000):
        q = int(rng.integers(500, n - 500)); top = bool(rng.random() < 0.5)
        sp, tp, tr = rng.uniform(0.001, 0.01), rng.uniform(0.001, 0.02), rng.uniform(0.0002, 0.003)
        a = H.replay_bracket_at(h, l, c, n, q, top, sp, tp, tr, H.MAX_HORIZON_CAP)
        b = replay_fast(h, l, c, n, q, top, sp, tp, tr)
        assert abs(a - b) < 1e-12, (a, b)
    print("replay_fast == replay_bracket_at on 3000 random brackets")


def study(label, df, finder):
    b, h, l, c, atr = finder(df)
    real, missed = H.eval_pullback_and_runner_pct(b, h, l, c, STOP_BUFFER, H.RETEST_TOL, H.RETEST_WINDOW, H.TRAIL_MULT)
    pf = H.pct_pf(real)
    arr = np.array([r["pnl_pct"] for r in real])
    pool = pool_fast(real, h, l, c, np.random.default_rng(42))
    pct = 100 * (pool < pf).mean(); p1 = (pool >= pf).mean()
    rows = R.best_of_k(pf, pool, HS_K)
    ks = " ".join(f"K={r['K']}:p={r['p']:.3f}" for r in rows)
    print(f"  {label:<44} breakouts={len(b):4d} n={len(real):4d} win%={100*(arr>0).mean():5.1f} %PF={pf:.3f} | "
          f"rand med={np.median(pool):.3f} p95={np.percentile(pool,95):.3f} -> {pct:5.1f}th pct (p={p1:.3f}) | {ks}")
    return pf, pct, rows


if __name__ == "__main__":
    check_replay()
    is_df = E.resample_m15_from_m5(E.load_m5())
    m15 = E.load_m15_native()
    oos_clean = m15[(m15["time"] >= R.REAL_M15_START) & (m15["time"] < OOS_CUTOFF)].reset_index(drop=True)
    oos_orig = m15[m15["time"] < OOS_CUTOFF].reset_index(drop=True)
    fb = lambda d: find_breakouts_full(d, break_tol=BREAK_TOL, causal=False)
    fc = lambda d: find_breakouts_causal(d, break_tol=BREAK_TOL)
    print("\nH&S stacked combo (v1.08: retest 0.50xATR/30 bars, break_tol 0.35, runner trail 0.5xATR)")
    print("=" * 150)
    print("IS - 2022-07 -> 2026-09 M15 (resampled real M5), the window H&S was built on:")
    study("ORIGINAL find_breakouts_full (lookahead)", is_df, fb)
    study("CAUSAL, EA-faithful detection", is_df, fc)
    print("\nOOS - native M15 2014-06-13 -> 2022-07-03 (real M15 bars only):")
    study("ORIGINAL find_breakouts_full (lookahead)", oos_clean, fb)
    study("CAUSAL, EA-faithful detection", oos_clean, fc)
    print("\nFor reference - hs_m15_oos_test.py's own slice (2001 -> 2022-07, incl. ~3,100 daily + ~4,000 hourly bars pre-2014-06):")
    study("ORIGINAL find_breakouts_full (lookahead)", oos_orig, fb)
    study("CAUSAL, EA-faithful detection", oos_orig, fc)
