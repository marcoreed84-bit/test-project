"""
Diamond Reversal (user's 2026-09-26 textbook, Errante Academy "The Art of
Trend Analysis and Chart Mastery"; geometry cross-checked against Bulkowski's
diamond top/bottom) - standalone test on real H4 and real native M15, full
random-timing + best-of-K pipeline (pattern_rigor_common.py). A RARE
pattern: expect a small n, and a small n is reported as inconclusive, not
pushed through a significance test it cannot support (min n = 20).

CONSTRUCTION, DIAMOND TOP (reversal of an uptrend -> SELL; the bottom is the
exact mirror -> BUY). Seven consecutive alternating zigzag swings from the
standard find_swings(), consumed CAUSALLY (causal_swing_events - the setup
only exists from L3's pivot bar + PIVOT_STRENGTH onward, in the swing state
known then):
    L0, H1, L1, H2, L2, H3, L3
  - left half BROADENS:   H2 > H1 and L2 < L1  (higher high AND lower low)
  - right half CONTRACTS: H3 < H2 and L3 > L2  (lower high AND higher low -
    the symmetrical-triangle taper)
  - prior UPTREND into it: L0 < L2 (price came up from below the whole
    formation). The "relaxed" variant drops this prior-trend requirement, to
    show whether it matters (and to give the sample a chance to be usable).
  - right-side boundaries: upper-right line H2 -> H3, lower-right line
    L2 -> L3, both extended.
  - ENTRY: BREAK_CONFIRM_CLOSES(3) closes below the lower-right line by
    BREAK_TOL_ATR x ATR (the standard break rule), scanned from the bar after
    L3 became knowable, for at most the formation's own width (iL3 - iH1,
    min 20 bars). If price instead breaks ABOVE the upper-right line first
    (3 closes), the reversal is voided - no trade (the pattern resolved as
    a continuation, which is not what the textbook's reversal signal is).
  - STOP = H3 + 1.0 x ATR (the last right-side high), TARGET = measured move
    = diamond height (H2 - L2) projected from the entry - Bulkowski's rule,
    same measured-move convention as every other pattern here.

K floor: 2 variants x 2 timeframes = 4 here, inside the long list of
Bulkowski-poster patterns this directory already tested (H&S, rectangle,
rounding bottom, triangle/wedge, double/triple top, bump-and-run, Wolfe,
Quasimodo, three valleys...) - K=30 decision threshold as for the rest of
this batch.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pattern_rigor_common as R

DECISION_K = 30


def diamond_from_snapshot(snap, known, strict):
    if len(snap) < 7:
        return None
    s = snap[-7:]
    types = [x[1] for x in s]
    idx = [x[0] for x in s]
    px = [x[2] for x in s]
    if types == [-1, 1, -1, 1, -1, 1, -1]:
        top = True
        L0, H1, L1, H2, L2, H3, L3 = px
        iH1, iH2, iL2, iH3, iL3 = idx[1], idx[3], idx[4], idx[5], idx[6]
        ok = H2 > H1 and L2 < L1 and H3 < H2 and L3 > L2 and (not strict or L0 < L2)
        if not ok:
            return None
        lo_line = (iL2, L2, iL3, L3)   # break side (reversal direction)
        hi_line = (iH2, H2, iH3, H3)   # void side
        stop_px, height = H3, H2 - L2
        start_i, last_i = iH1, iL3
    elif types == [1, -1, 1, -1, 1, -1, 1]:
        top = False
        H0, L1, H1, L2, H2, L3, H3 = px
        iL1, iL2, iH2, iL3, iH3 = idx[1], idx[3], idx[4], idx[5], idx[6]
        ok = L2 < L1 and H2 > H1 and L3 > L2 and H3 < H2 and (not strict or H0 > H2)
        if not ok:
            return None
        lo_line = (iH2, H2, iH3, H3)   # break side: upper-right line, broken upward
        hi_line = (iL2, L2, iL3, L3)   # void side
        stop_px, height = L3, H2 - L2
        start_i, last_i = iL1, iH3
    else:
        return None
    return dict(top=top, brk_line=lo_line, void_line=hi_line, stop_px=stop_px, height=height,
                known=known, expire=known + max(last_i - start_i, 20), run_b=0, run_v=0)


def line_at(ln, q):
    i0, p0, i1, p1 = ln
    return p0 + (p1 - p0) * (q - i0) / (i1 - i0)


def detect(h, l, c, atr, events, strict):
    n = len(c)
    trades = []
    pend = {True: None, False: None}
    ev = 0
    tol = R.BREAK_TOL_ATR
    n_setups = 0
    for q in range(n):
        for top in (True, False):
            d = pend[top]
            if d is None:
                continue
            if q > d["expire"]:
                pend[top] = None; continue
            if q <= d["known"]:
                continue
            bl, vl = line_at(d["brk_line"], q), line_at(d["void_line"], q)
            a = atr[q]
            if top:
                d["run_b"] = d["run_b"] + 1 if bl - c[q] > tol * a else 0
                d["run_v"] = d["run_v"] + 1 if c[q] - vl > tol * a else 0
            else:
                d["run_b"] = d["run_b"] + 1 if c[q] - bl > tol * a else 0
                d["run_v"] = d["run_v"] + 1 if vl - c[q] > tol * a else 0
            if d["run_v"] >= R.BREAK_CONFIRM_CLOSES:
                pend[top] = None; continue
            if d["run_b"] >= R.BREAK_CONFIRM_CLOSES:
                e = c[q]
                if top:
                    tr = R.make_trade(True, q, e, d["stop_px"] + R.STOP_BUFFER * a, e - d["height"], n)
                else:
                    tr = R.make_trade(False, q, e, d["stop_px"] - R.STOP_BUFFER * a, e + d["height"], n)
                if tr:
                    trades.append(tr)
                pend[top] = None
        while ev < len(events) and events[ev][0] == q:
            dm = diamond_from_snapshot(events[ev][1], q, strict)
            if dm is not None:
                pend[dm["top"]] = dm
                n_setups += 1
            ev += 1
    return trades, n_setups


def run(name, df):
    o, h, l, c, atr = R.arrays(df)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    events, _ = R.causal_swing_events(o, h, l, c, atr)
    t = df["time"].values
    print("\n" + "=" * 100)
    print(f"{name}: n={len(c)} bars, {years:.2f} yrs")
    print("=" * 100)
    summ = []
    for strict, label in ((True, "diamond (strict: prior trend required)"), (False, "diamond (relaxed: no prior-trend check)")):
        trades, n_setups = detect(h, l, c, atr, events, strict)
        res = R.eval_book_pct(trades, h, l, c, times=t)
        print(f"  {label}: {n_setups} diamond setups knowable ({n_setups/years:.1f}/yr), "
              f"{len(trades)} confirmed reversal breakouts")
        summ.append(R.rigor_report(f"{name} {label}", res, h, l, c))
    return summ


if __name__ == "__main__":
    summ = []
    summ += run("H4", R.load_h4_real())
    summ += run("M15", R.load_m15_real())
    R.verdict_table(summ, DECISION_K)
