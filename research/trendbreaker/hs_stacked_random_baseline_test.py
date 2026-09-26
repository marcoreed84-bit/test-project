"""
Same random-timing/same-bracket baseline (Opus's Wolfe Wave check,
2026-09-26) applied to HeadShoulders_EA's own real, shipped "stacked
combo" (v1.08 default: pullback/retest entry 0.50xATR/30bar + BREAK_TOL_ATR
=0.35 + runner trail 0.5xATR after target, M15, both directions) - the user
asked to re-run this against RoundingBottom and H&S before trusting them
further.

METHOD: reconstruct the real stacked-combo trades via
hs_next_round_test.py's own eval_pullback_and_runner() (unmodified - that
function is trusted, this script only adds a %-of-price PF and a random-
timing control on top of it). For each real trade, capture its own
stop/target/trail distance as a PERCENTAGE of its entry price (not raw
points - GOLD's ~$270->~$4000 run over this dataset badly inflates a
points-based PF for recent trades), preserving its direction (top=True
bearish/short, top=False bullish/long). Then fire the SAME %-sized
stop/target/trail bracket, same direction, at N_RANDOM sets of randomly
chosen M15 bars, and compare the real %PF against that random-timing
distribution - exactly the test that showed Wolfe Wave's apparent edge was
just GOLD's own drift, and that RoundingBottom's %PF (see
rounding_bottom_random_baseline_test.py) sits around the 85th percentile
of its own random-timing band, not clearly above it.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from hs_next_round_test import find_breakouts_full, eval_pullback_and_runner, STOP_BUFFER

np.random.seed(42)
N_RANDOM = 1500
RETEST_TOL, RETEST_WINDOW, TRAIL_MULT = 0.50, 30, 0.5
BREAK_TOL = 0.35
MAX_HORIZON_CAP = 400


def eval_pullback_and_runner_pct(breakouts, h, l, c, stop_buffer, retest_tol_atr, retest_window, trail_atr_mult):
    """Same construction as hs_next_round_test.eval_pullback_and_runner(),
    but also records stop_pct/target_pct/trail_pct so the random-timing
    control can replay the exact same bracket shape elsewhere."""
    results, last_exit, missed = [], -1, 0
    for b in breakouts:
        top, brk_q, target = b["top"], b["brk_q"], b["target"]
        if brk_q < last_exit:
            continue
        tol = retest_tol_atr * b["atr_at_brk"]
        entry_bar, entry = None, None
        for q in range(brk_q + 1, min(brk_q + 1 + retest_window, b["max_horizon"])):
            nl = b["neckline_at"](q)
            touched = (h[q] >= nl - tol) if top else (l[q] <= nl + tol)
            if touched:
                entry_bar, entry = q, nl
                break
        if entry_bar is None:
            missed += 1
            continue
        stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        atrv = b["atr_at_brk"]
        cur_stop = stop
        outcome, exit_bar, exit_px = None, None, None
        reached_target = False
        peak = entry
        for k in range(entry_bar + 1, b["max_horizon"] + 1):
            hit_stop = (h[k] >= cur_stop) if top else (l[k] <= cur_stop)
            if hit_stop:
                exit_bar, exit_px = k, cur_stop
                break
            hit_target = (l[k] <= target) if top else (h[k] >= target)
            if hit_target and not reached_target:
                reached_target = True
                peak = target
            if reached_target:
                if top:
                    peak = min(peak, l[k])
                    cur_stop = min(cur_stop, peak + trail_atr_mult * atrv)
                else:
                    peak = max(peak, h[k])
                    cur_stop = max(cur_stop, peak - trail_atr_mult * atrv)
        if exit_bar is None:
            exit_bar, exit_px = b["max_horizon"], c[min(b["max_horizon"], len(c) - 1)]
        pnl = (entry - exit_px) if top else (exit_px - entry)
        pnl_pct = pnl / entry
        stop_pct = abs(entry - stop) / entry
        target_pct = abs(target - entry) / entry
        trail_pct = trail_atr_mult * atrv / entry
        results.append(dict(brk_q=entry_bar, top=top, pnl=pnl, pnl_pct=pnl_pct,
                             stop_pct=stop_pct, target_pct=target_pct, trail_pct=trail_pct))
        last_exit = exit_bar
    return results, missed


def pct_pf(results):
    arr = np.array([r["pnl_pct"] for r in results])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def replay_bracket_at(h, l, c, n, q0, top, stop_pct, target_pct, trail_pct, max_horizon_cap):
    entry = c[q0]
    stop = entry * (1 - stop_pct) if not top else entry * (1 + stop_pct)
    target = entry * (1 + target_pct) if not top else entry * (1 - target_pct)
    trail_dist = trail_pct * entry
    max_horizon = min(n - 1, q0 + max_horizon_cap)
    cur_stop = stop
    reached_target = False
    peak = entry
    exit_px = None
    for k in range(q0 + 1, max_horizon + 1):
        hit_stop = (h[k] >= cur_stop) if top else (l[k] <= cur_stop)
        if hit_stop:
            exit_px = cur_stop
            break
        hit_target = (l[k] <= target) if top else (h[k] >= target)
        if hit_target and not reached_target:
            reached_target = True
            peak = target
        if reached_target:
            if top:
                peak = min(peak, l[k])
                cur_stop = min(cur_stop, peak + trail_dist)
            else:
                peak = max(peak, h[k])
                cur_stop = max(cur_stop, peak - trail_dist)
    if exit_px is None:
        exit_px = c[min(max_horizon, n - 1)]
    pnl = (entry - exit_px) if top else (exit_px - entry)
    return pnl / entry


def random_timing_baseline(real_results, h, l, c, n, rng, n_runs=N_RANDOM):
    pfs = []
    lo, hi = MAX_HORIZON_CAP, n - MAX_HORIZON_CAP - 1
    for _ in range(n_runs):
        pcts = []
        for r in real_results:
            q0 = int(rng.integers(lo, hi))
            pcts.append(replay_bracket_at(h, l, c, n, q0, r["top"], r["stop_pct"],
                                           r["target_pct"], r["trail_pct"], MAX_HORIZON_CAP))
        arr = np.array(pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        pfs.append(gw / gl if gl > 0 else np.nan)
    return np.array(pfs)


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    breakouts, h, l, c, atr = find_breakouts_full(df15, break_tol=BREAK_TOL)
    n = len(c)
    print(f"M15 data: n={n} bars, {len(breakouts)} raw H&S breakouts (break_tol={BREAK_TOL})\n")

    real, missed = eval_pullback_and_runner_pct(breakouts, h, l, c, STOP_BUFFER,
                                                 RETEST_TOL, RETEST_WINDOW, TRAIL_MULT)
    real_arr = np.array([r["pnl_pct"] for r in real])
    wins = (real_arr > 0).sum()
    real_pct_pf = pct_pf(real)
    print(f"REAL stacked combo: n={len(real)} (missed {missed})  win%={100*wins/len(real):.1f}  "
          f"net%={100*real_arr.sum():.2f}  %PF={real_pct_pf:.3f}")
    n_top = sum(1 for r in real if r["top"])
    print(f"  direction mix: {n_top} short (bearish H&S), {len(real)-n_top} long (inverse H&S)")

    rng = np.random.default_rng(42)
    print(f"\nRunning {N_RANDOM} random-timing baselines (same %% brackets incl. runner trail, "
          f"same direction mix, random M15 bars)...")
    rand_pfs = random_timing_baseline(real, h, l, c, n, rng)
    rand_pfs = rand_pfs[~np.isnan(rand_pfs)]
    print(f"  random-timing %%PF distribution: median={np.median(rand_pfs):.3f}  "
          f"p10={np.percentile(rand_pfs,10):.3f}  p90={np.percentile(rand_pfs,90):.3f}  "
          f"p95={np.percentile(rand_pfs,95):.3f}")
    p_value = (rand_pfs >= real_pct_pf).mean()
    percentile_rank = 100 * (rand_pfs < real_pct_pf).mean()
    print(f"\n  REAL %%PF={real_pct_pf:.3f} sits at the {percentile_rank:.1f}th percentile of "
          f"{len(rand_pfs)} random-timing runs (one-sided p={p_value:.3f}).")
    if real_pct_pf > np.percentile(rand_pfs, 95):
        print("  -> ABOVE the random-timing band (95th pct) - genuine timing edge beyond bracket size.")
    elif real_pct_pf < np.percentile(rand_pfs, 5):
        print("  -> BELOW the random-timing band - timing is actively worse than random.")
    else:
        print("  -> INSIDE the random-timing band - no statistically distinguishable evidence the")
        print("     pattern's specific timing adds anything beyond 'trade GOLD with a bracket this size'.")
