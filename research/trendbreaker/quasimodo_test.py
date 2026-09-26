"""
Quasimodo pattern (also called "Over and Under" / QM) - from the user's
chart-pattern poster. A retail/smart-money-concepts pattern, less
academically documented than Bulkowski's work but with a clear, specific
community-standard geometric definition:

BEARISH QM (topping, for shorts):
  A = a swing high. B = the next swing low. C = the next swing high, and
  C must exceed A (price sweeps beyond the prior high - a "liquidity
  grab"/false breakout). Confirmation: price then breaks BELOW B (the
  swing low between A and C) - the "break of structure" that invalidates
  the uptrend. Entry: either immediately on that break, or (the more
  common real-world practice) wait for a RETEST - price retracing back UP
  to B's level (now acting as resistance) - before shorting. Both tested.
  Stop above C (the swept high). Target = measured move: height = C - B,
  same convention as every other pattern this session.
BULLISH QM is the exact mirror (A=low, B=high, C=low with C<A, break
above B, entry on the break or on a retest of B from below).

Same rigor discipline as everything since Wolfe Wave: lookahead-lag fix
(a swing point isn't knowable until PIVOT_STRENGTH bars after it forms -
the CONFIRM_LAG lesson), %PF not raw points, random-timing baseline run
immediately, both H4 and M15.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES, PIVOT_STRENGTH
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)
MAX_HORIZON_CAP = 400
STOP_BUFFER = 1.0
CONFIRM_LAG = PIVOT_STRENGTH + 1
RETEST_WINDOW = 60
RETEST_TOL_ATR = 0.35


def find_candidates(zIdx, zType, zPx):
    """3-point windows: high-low-high (bearish) or low-high-low (bullish),
    with the 3rd point sweeping beyond the 1st (C beyond A)."""
    out = []
    for m in range(len(zIdx) - 2):
        seq = zType[m:m + 3]
        iA, iB, iC = zIdx[m:m + 3]
        pA, pB, pC = zPx[m:m + 3]
        if seq == [1, -1, 1] and pC > pA:      # bearish: A high, B low, C higher high
            out.append(dict(top=True, iA=iA, iB=iB, iC=iC, pA=pA, pB=pB, pC=pC))
        elif seq == [-1, 1, -1] and pC < pA:   # bullish: A low, B high, C lower low
            out.append(dict(top=False, iA=iA, iB=iB, iC=iC, pA=pA, pB=pB, pC=pC))
    return out


def build_trades(cands, h, l, c, atr, n, use_retest):
    out = []
    for cd in cands:
        top, iB, iC, pB, pC = cd["top"], cd["iB"], cd["iC"], cd["pB"], cd["pC"]
        scan_start = iC + CONFIRM_LAG
        horizon_end = min(n - 1, iC + MAX_HORIZON_CAP)
        brk_q, run_ = -1, 0
        for q in range(scan_start, horizon_end):
            beyond = (pB - c[q]) if top else (c[q] - pB)
            if beyond > BREAK_TOL_ATR * atr[q]:
                run_ += 1
                if run_ >= BREAK_CONFIRM_CLOSES:
                    brk_q = q; break
            else:
                run_ = 0
        if brk_q < 0:
            continue

        entry_q, entry_price = brk_q, c[brk_q]
        if use_retest:
            tol = RETEST_TOL_ATR * atr[brk_q]
            found = False
            for q in range(brk_q + 1, min(brk_q + 1 + RETEST_WINDOW, n)):
                if (top and h[q] >= pB - tol) or ((not top) and l[q] <= pB + tol):
                    entry_q, entry_price = q, pB
                    found = True
                    break
            if not found:
                continue

        height = abs(pC - pB)
        if height <= 0:
            continue
        target = (entry_price - height) if top else (entry_price + height)
        stop = pC + STOP_BUFFER * atr[entry_q] if top else pC - STOP_BUFFER * atr[entry_q]
        if (top and stop <= entry_price) or ((not top) and stop >= entry_price):
            continue
        max_horizon = min(n - 1, entry_q + MAX_HORIZON_CAP)
        out.append(dict(top=top, brk_q=entry_q, brk_price=entry_price, target=target,
                         stop=stop, max_horizon=max_horizon))
    return out


def eval_book_pct(trades, h, l, c):
    trades = sorted(trades, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in trades:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk(h, l, b["top"], b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pnl = pnl_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, b["top"])
        pnl_pct = pnl / b["brk_price"]
        results.append(dict(brk_q=b["brk_q"], top=b["top"], pnl=pnl, pnl_pct=pnl_pct,
                             stop_pct=abs(b["brk_price"] - b["stop"]) / b["brk_price"],
                             target_pct=abs(b["target"] - b["brk_price"]) / b["brk_price"]))
        last_exit = exit_bar
    return results


def pct_pf(results):
    if not results:
        return float("nan")
    arr = np.array([r["pnl_pct"] for r in results])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def random_timing_baseline(real_results, h, l, c, n, rng, n_runs=1500):
    pfs = []
    lo, hi = MAX_HORIZON_CAP, n - MAX_HORIZON_CAP - 1
    for _ in range(n_runs):
        pcts = []
        for r in real_results:
            q0 = int(rng.integers(lo, hi))
            entry = c[q0]
            top = r["top"]
            stop = entry * (1 + r["stop_pct"]) if top else entry * (1 - r["stop_pct"])
            target = entry * (1 - r["target_pct"]) if top else entry * (1 + r["target_pct"])
            max_horizon = min(n - 1, q0 + MAX_HORIZON_CAP)
            outcome, exit_bar = walk(h, l, top, q0, max_horizon, stop, target)
            pnl = pnl_of(outcome, entry, stop, target, c, exit_bar, top)
            pcts.append(pnl / entry)
        arr = np.array(pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        pfs.append(gw / gl if gl > 0 else np.nan)
    return np.array(pfs)


def run(name, df):
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    cands = find_candidates(zIdx, zType, zPx)
    print(f"\n{'='*92}\n{name}: n={n} bars, {years:.2f} yrs, {len(cands)} raw QM shapes ({len(cands)/years:.1f}/yr)\n{'='*92}")

    for use_retest, label in ((False, "immediate entry on break"), (True, "retest entry (wait for pullback to B)")):
        trades = build_trades(cands, h, l, c, atr, n, use_retest)
        res = eval_book_pct(trades, h, l, c)
        if len(res) < 8:
            print(f"  {label}: only {len(res)} trades - too few")
            continue
        real_pf = pct_pf(res)
        report(res, f"  {label}")
        print(f"    %PF={real_pf:.3f}")
        bull = [r for r in res if not r["top"]]
        bear = [r for r in res if r["top"]]
        if len(bull) >= 8:
            report(bull, "    bullish only")
        if len(bear) >= 8:
            report(bear, "    bearish only")

        rng = np.random.default_rng(42)
        rand_pfs = random_timing_baseline(res, h, l, c, n, rng)
        rand_pfs = rand_pfs[~np.isnan(rand_pfs)]
        pctile = 100 * (rand_pfs < real_pf).mean()
        p_val = (rand_pfs >= real_pf).mean()
        print(f"    random-timing median={np.median(rand_pfs):.3f}  p95={np.percentile(rand_pfs,95):.3f}")
        print(f"    REAL sits at {pctile:.1f}th percentile (one-sided p={p_val:.3f})")


if __name__ == "__main__":
    h4 = E.load_h4()
    run("H4", h4)

    m5 = E.load_m5()
    m15 = E.resample_m15_from_m5(m5)
    run("M15 (resampled from real M5)", m15)
