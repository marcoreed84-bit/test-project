"""AUDIT: isolate the H&S research-sim fill assumption. Same causal breakouts, same stacked-combo
logic as hs_stacked_random_baseline_test.eval_pullback_and_runner_pct, but three fill conventions:
  A  repo: entry = neckline price on the retest bar itself (frictionless, may be a price never traded)
  B  EA:   retest detected on the CLOSED bar q -> market fill at open[q+1], no spread
  C  EA + spread: as B, long pays spread at entry (ask), stop/trail on bid
Random null in every case uses the SAME convention as its real run (A: close[q0]; B/C: open[q0+1]).
Untouched native M15 2014-06-13 -> 2022-07-03."""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np, pandas as pd
import engine as E, pattern_rigor_common as R
import hs_stacked_random_baseline_test as H
from hs_next_round_test import find_breakouts_causal, STOP_BUFFER
from hs_causal_detection_check import pool_fast

CUT = pd.Timestamp("2022-07-04")


def eval_fill(breakouts, o, h, l, c, sp, mode):
    res, last_exit = [], -1
    n = len(c)
    for b in breakouts:
        top, brk_q, target = b["top"], b["brk_q"], b["target"]
        if brk_q < last_exit:
            continue
        tol = H.RETEST_TOL * b["atr_at_brk"]
        eb = None
        for q in range(brk_q + 1, min(brk_q + 1 + H.RETEST_WINDOW, b["max_horizon"])):
            nl = b["neckline_at"](q)
            if (h[q] >= nl - tol) if top else (l[q] <= nl + tol):
                eb = q
                break
        if eb is None:
            continue
        if mode == "A":
            entry, first = b["neckline_at"](eb), eb + 1
        else:
            if eb + 1 >= n:
                continue
            entry = o[eb + 1] + (sp[eb + 1] if (mode == "C" and not top) else 0.0)
            first = eb + 1          # the fill bar itself can stop the trade out
        stop = (b["shoulder_ext"] + STOP_BUFFER * b["atr_at_brk"]) if top else (b["shoulder_ext"] - STOP_BUFFER * b["atr_at_brk"])
        if (top and (stop <= entry or target >= entry)) or ((not top) and (stop >= entry or target <= entry)):
            continue
        atrv = b["atr_at_brk"]; cur = stop; reached = False; peak = entry; xb = None
        for k in range(first, b["max_horizon"] + 1):
            if (h[k] >= cur) if top else (l[k] <= cur):
                xb, xp = k, cur
                break
            if not reached and ((l[k] <= target) if top else (h[k] >= target)):
                reached, peak = True, target
            if reached:
                if top:
                    peak = min(peak, l[k]); cur = min(cur, peak + H.TRAIL_MULT * atrv)
                else:
                    peak = max(peak, h[k]); cur = max(cur, peak - H.TRAIL_MULT * atrv)
        if xb is None:
            xb = b["max_horizon"]; xp = c[min(xb, n - 1)]
        pnl = (entry - xp) if top else (xp - entry)
        res.append(dict(brk_q=eb, top=top, pnl_pct=pnl / entry, stop_pct=abs(entry - stop) / entry,
                        target_pct=abs(target - entry) / entry, trail_pct=H.TRAIL_MULT * atrv / entry))
        last_exit = xb
    return res


def replay_open(o, h, l, c, sp, q, top, stop_pct, target_pct, trail_pct, spread, cap=H.MAX_HORIZON_CAP):
    n = len(c); f = q + 1
    entry = o[f] + (sp[f] if (spread and not top) else 0.0)
    d = -1 if top else 1
    stop = entry * (1 - d * stop_pct); target = entry * (1 + d * target_pct); trail = trail_pct * entry
    reached = False; peak = entry
    for k in range(f, min(n - 1, q + cap) + 1):
        if (h[k] >= stop) if top else (l[k] <= stop):
            return (stop - entry) * d / entry
        if not reached and ((l[k] <= target) if top else (h[k] >= target)):
            reached, peak = True, target
        if reached:
            if top:
                peak = min(peak, l[k]); stop = min(stop, peak + trail)
            else:
                peak = max(peak, h[k]); stop = max(stop, peak - trail)
    return (c[min(n - 1, q + cap)] - entry) * d / entry


if __name__ == "__main__":
    m15 = E.load_m15_native()
    df = m15[(m15.time >= R.REAL_M15_START) & (m15.time < CUT)].reset_index(drop=True)
    b, h, l, c, atr = find_breakouts_causal(df, break_tol=0.35)
    o = df["open"].values; sp = df["spread"].values * 0.01
    print(f"untouched M15 {df.time.iloc[0]} -> {df.time.iloc[-1]}, causal breakouts={len(b)}, RETEST_TOL={H.RETEST_TOL}")
    for mode in ("A", "B", "C"):
        real = eval_fill(b, o, h, l, c, sp, mode)
        a = np.array([r["pnl_pct"] for r in real]); rpf = H.pct_pf(real)
        rng = np.random.default_rng(42)
        if mode == "A":
            pool = pool_fast(real, h, l, c, rng, n_runs=400)
        else:
            n = len(c); lo, hi = H.MAX_HORIZON_CAP, n - H.MAX_HORIZON_CAP - 1; pool = []
            for _ in range(300):
                qs = rng.integers(lo, hi, size=len(real))
                arr = np.array([replay_open(o, h, l, c, sp, int(q), r["top"], r["stop_pct"], r["target_pct"], r["trail_pct"], mode == "C")
                                for q, r in zip(qs, real)])
                gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum(); pool.append(gw / gl)
            pool = np.array(pool)
        pool = pool[np.isfinite(pool)]
        rows = R.best_of_k(rpf, pool, (1, 27, 50))
        print(f"  mode {mode}: n={len(a)} win%={100*(a>0).mean():.1f} %PF={rpf:.3f} | null median={np.median(pool):.3f} "
              f"p95={np.percentile(pool,95):.3f} -> {100*(pool<rpf).mean():.1f}th pct | " +
              " ".join(f"K={r['K']}:p={r['p']:.3f}" for r in rows), flush=True)
