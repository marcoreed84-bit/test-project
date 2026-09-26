"""
Applying the SAME random-timing/same-bracket baseline that got Wolfe Wave
rejected (Opus review, 2026-09-26) to RoundingBottom_EA's own real,
already-shipped construction (v1.03: window=60, no handle required,
stop = rim - 1.0xATR, target = measured move, on H4, buy-only) - the user
asked to re-run this check against RoundingBottom and H&S before trusting
them further, since both were originally validated with a raw-POINTS PF
and a chronological IS/OOS split, neither of which controls for GOLD's own
multi-decade uptrend the way this baseline does.

METHOD (identical in spirit to Opus's Wolfe Wave check): for every real
trade, take its own risk/reward as a PERCENTAGE of the entry price (not
raw points - GOLD ran from ~$270 to ~$4000 over this dataset, so a
points-based PF over-weights recent trades by 10x+), then fire the exact
same %-sized stop/target bracket, long-only, at N_RANDOM sets of randomly
chosen H4 bars. If the real construction's %PF sits inside the resulting
random-timing distribution, the "pattern" isn't adding anything beyond
"be long GOLD with a bracket this size" - if it sits clearly above the
distribution, that is real, specific evidence the pattern's ENTRY TIMING
itself matters, not just its risk sizing.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES
from rounding_cup_handle_test import find_rounding
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)
N_RANDOM = 300
WINDOW = 60
STOP_BUFFER = 1.0          # v1.03 shipped default
MAX_HORIZON_CAP = 300      # matches InpMaxHorizonBars


def build_real_trades(cands, h, l, c, atr, n):
    """v1.03 construction: stop anchored to the RIM (not the cup's own
    bottom - that was Backtest 1's real, disclosed flaw), no handle filter."""
    out = []
    for cd in cands:
        end, rim, extreme_px = cd["end"], cd["rim"], cd["extreme_px"]
        height = abs(rim - extreme_px)
        if height <= 0:
            continue
        horizon_end = min(n - 1, end + MAX_HORIZON_CAP)
        brk_q, run_ = -1, 0
        for q in range(end + 1, horizon_end):
            beyond = c[q] - rim
            if beyond > BREAK_TOL_ATR * atr[q]:
                run_ += 1
                if run_ >= BREAK_CONFIRM_CLOSES:
                    brk_q = q; break
            else:
                run_ = 0
        if brk_q < 0:
            continue
        brk_price = c[brk_q]
        target = brk_price + height
        atr_brk = atr[brk_q]
        stop = rim - STOP_BUFFER * atr_brk           # v1.03 fix - rim, not cup bottom
        if stop >= brk_price:
            continue
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(top=False, brk_q=brk_q, brk_price=brk_price, target=target,
                         stop=stop, max_horizon=max_horizon))
    return out


def eval_book(trades, h, l, c):
    trades = sorted(trades, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in trades:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk(h, l, False, b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pnl = pnl_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, False)
        pnl_pct = pnl / b["brk_price"]
        results.append(dict(brk_q=b["brk_q"], outcome=outcome, pnl=pnl, pnl_pct=pnl_pct,
                             stop_pct=(b["brk_price"] - b["stop"]) / b["brk_price"],
                             target_pct=(b["target"] - b["brk_price"]) / b["brk_price"]))
        last_exit = exit_bar
    return results


def pct_pf(results, key="pnl_pct"):
    arr = np.array([r[key] for r in results])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_timing_baseline(real_results, h, l, c, atr, n, rng, n_runs=N_RANDOM):
    """For each real trade, replay its own %-sized stop/target bracket
    (long only, matching RoundingBottom's buy-only construction) at a
    randomly chosen H4 bar, using that random bar's own price level."""
    pfs = []
    lo, hi = MAX_HORIZON_CAP, n - MAX_HORIZON_CAP - 1
    for _ in range(n_runs):
        pnl_pcts = []
        for r in real_results:
            q0 = int(rng.integers(lo, hi))
            entry = c[q0]
            stop = entry * (1 - r["stop_pct"])
            target = entry * (1 + r["target_pct"])
            max_horizon = min(n - 1, q0 + MAX_HORIZON_CAP)
            outcome, exit_bar = walk(h, l, False, q0, max_horizon, stop, target)
            pnl = pnl_of(outcome, entry, stop, target, c, exit_bar, False)
            pnl_pcts.append(pnl / entry)
        arr = np.array(pnl_pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        pfs.append(gw / gl if gl > 0 else np.nan)
    return np.array(pfs)


if __name__ == "__main__":
    h4 = E.load_h4()
    o = h4["open"].values; h = h4["high"].values; l = h4["low"].values; c = h4["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    print(f"H4 data: n={n} bars, {h4['time'].min()} -> {h4['time'].max()}\n")

    cands = find_rounding(c, atr, n, WINDOW, top=False)
    trades = build_real_trades(cands, h, l, c, atr, n)
    real = eval_book(trades, h, l, c)
    report(real, f"REAL RoundingBottom v1.03 construction ({len(cands)} candidates)")
    print(f"  in RAW POINTS pf={ (np.array([r['pnl'] for r in real])[np.array([r['pnl'] for r in real])>0].sum()) / max(1e-9,-np.array([r['pnl'] for r in real])[np.array([r['pnl'] for r in real])<=0].sum()):.3f}")
    real_pct_pf = pct_pf(real)
    print(f"  in PERCENT-OF-PRICE terms: pf={real_pct_pf:.3f}  n={len(real)}")

    rng = np.random.default_rng(42)
    print(f"\nRunning {N_RANDOM} random-timing baselines (same %% stop/target brackets, random H4 bars, long-only)...")
    rand_pfs = random_timing_baseline(real, h, l, c, atr, n, rng)
    rand_pfs = rand_pfs[~np.isnan(rand_pfs)]
    print(f"  random-timing %%PF distribution: median={np.median(rand_pfs):.3f}  "
          f"5th={np.percentile(rand_pfs,5):.3f}  95th={np.percentile(rand_pfs,95):.3f}")
    pct_above = 100 * (rand_pfs < real_pct_pf).mean()
    print(f"\n  REAL %%PF={real_pct_pf:.3f} beats {pct_above:.1f}% of {len(rand_pfs)} random-timing runs "
          f"with the SAME risk/reward brackets.")
    if real_pct_pf > np.percentile(rand_pfs, 95):
        print("  -> REAL result is ABOVE the random-timing band (95th pct) - genuine timing edge, not just the bracket size.")
    elif real_pct_pf < np.percentile(rand_pfs, 5):
        print("  -> REAL result is BELOW the random-timing band - the pattern's timing is actively worse than random.")
    else:
        print("  -> REAL result sits INSIDE the random-timing band - no evidence the pattern's specific timing")
        print("     adds anything beyond 'be long GOLD with a bracket this size'.")
