"""
Andrews' Pitchfork (user's 2026-09-26 textbook, Errante Academy "The Art of
Trend Analysis and Chart Mastery") - standalone test on real H4 and real
native M15 with the full random-timing + best-of-K pipeline
(pattern_rigor_common.py).

CONSTRUCTION. Three consecutive alternating zigzag swings A, B, C from the
repo's standard find_swings(), consumed CAUSALLY (causal_swing_events: a
fork exists only from C's pivot bar + PIVOT_STRENGTH onward, and only in the
swing state known then - if C is later replaced by a more extreme pivot the
fork is re-drawn from the new C, or dropped if the new triple is invalid,
exactly like a trader re-drawing it live):
  - BULLISH fork: A = swing low, B = swing high, C = HIGHER swing low
    (pC > pA). BEARISH fork: A = high, B = low, C = LOWER high (pC < pA).
  - MEDIAN LINE: from A through the midpoint of B-C
    (M = ((iB+iC)/2, (pB+pC)/2)), extended. UPPER/LOWER PARALLELS: same
    slope, through B and through C.
  - A fork stays live for FORK_LIFE = max(iC - iA, 20) bars after it becomes
    knowable, or until price BREAKS OUT of it (below), or a newer fork of the
    same direction replaces it. One live fork per direction.

STRATEGIES (bullish fork shown; bearish is the exact mirror). Decision on a
bar's close, filled at that close, single-position book, same as every
pattern test in this directory:
 (i)   MEDIAN MAGNET: at the first bar after the fork becomes knowable,
       BUY if the median line is >= 0.5 x ATR above price and price is
       still above the lower parallel; target = median line (value at the
       entry bar - a static snapshot of a rising line, so if anything it
       UNDERSTATES the target, same disclosed simplification as Wolfe Wave's
       EPA line), stop = C - 1.0 x ATR. This is Andrews' own "price returns
       to the median line" rule.
 (ii)  LOWER-PARALLEL BOUNCE (with-trend dynamic support): first touch of
       the lower parallel that closes back above it -> BUY, target = median
       line, stop = lower parallel - 1.0 x ATR.
 (iii) UPPER-PARALLEL REJECTION (dynamic resistance, counter-trend back to
       the median): first touch of the upper parallel closing back below
       it -> SELL, target = median, stop = upper parallel + 1.0 x ATR.
 (iv)  UPPER-PARALLEL BREAKOUT (acceleration): BREAK_CONFIRM_CLOSES(3)
       closes above the upper parallel by BREAK_TOL_ATR -> BUY, stop =
       median line, target = entry + fork width (upper - lower).
 (v)   LOWER-PARALLEL BREAKDOWN (trend failure): 3 closes below the lower
       parallel -> SELL, stop = median, target = entry - fork width.
 A breakout/breakdown (iv/v) ends the fork (no further bounce signals).

K floor: 5 strategies x 2 timeframes = 10 in this file, inside the same
trendline/S-R family as fan_principle_test.py / price_channel_test.py and
this directory's touch/pierce files - K=30 decision threshold, 50/100 shown.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pattern_rigor_common as R

MAGNET_MIN_ATR = 0.5
DECISION_K = 30


class Fork:
    def __init__(self, bull, A, B, C, known):
        self.bull = bull
        (self.iA, self.pA), (self.iB, self.pB), (self.iC, self.pC) = A, B, C
        mi = (self.iB + self.iC) / 2.0
        mp = (self.pB + self.pC) / 2.0
        self.slope = (mp - self.pA) / (mi - self.iA)
        self.known = known
        self.expire = known + max(self.iC - self.iA, 20)
        self.run_up = 0
        self.run_dn = 0
        self.magnet_done = False

    def median(self, q):
        return self.pA + self.slope * (q - self.iA)

    def par_B(self, q):
        return self.pB + self.slope * (q - self.iB)

    def par_C(self, q):
        return self.pC + self.slope * (q - self.iC)

    def upper(self, q):
        return max(self.par_B(q), self.par_C(q))

    def lower(self, q):
        return min(self.par_B(q), self.par_C(q))


def fork_from_snapshot(snap, known):
    if len(snap) < 3:
        return None
    (iA, tA, pA), (iB, tB, pB), (iC, tC, pC) = snap[-3:]
    if (tA, tB, tC) == (-1, 1, -1) and pC > pA:
        return Fork(True, (iA, pA), (iB, pB), (iC, pC), known)
    if (tA, tB, tC) == (1, -1, 1) and pC < pA:
        return Fork(False, (iA, pA), (iB, pB), (iC, pC), known)
    return None


def detect(h, l, c, atr, events, state=None):
    """state: optional int array (len n) - filled with the direction of the
    newest LIVE fork as known at each bar's close (+1 bullish, -1 bearish,
    0 none). Used only by the gate/filter tests on the kept EAs
    (new_pattern_gate_features.py); signals are identical with or without it."""
    n = len(c)
    sig = dict(magnet=[], bounce_trend=[], reject_counter=[], break_accel=[], break_fail=[])
    live = {True: None, False: None}
    ev = 0
    tol = R.BREAK_TOL_ATR
    for q in range(1, n):
        for bull in (True, False):
            f = live[bull]
            if f is None:
                continue
            if q > f.expire:
                live[bull] = None; continue
            if q <= f.known:
                continue
            a = atr[q]; e = c[q]
            med, up, lo = f.median(q), f.upper(q), f.lower(q)
            up1, lo1 = f.upper(q - 1), f.lower(q - 1)
            width = up - lo
            # (i) median magnet - once, first bar after the fork is knowable
            if not f.magnet_done:
                f.magnet_done = True
                if bull and med - e >= MAGNET_MIN_ATR * a and e > lo:
                    tr = R.make_trade(False, q, e, f.pC - R.STOP_BUFFER * a, med, n)
                    if tr: sig["magnet"].append(tr)
                if (not bull) and e - med >= MAGNET_MIN_ATR * a and e < up:
                    tr = R.make_trade(True, q, e, f.pC + R.STOP_BUFFER * a, med, n)
                    if tr: sig["magnet"].append(tr)
            # breakouts (3 consecutive closes beyond, standard rule)
            f.run_up = f.run_up + 1 if c[q] - up > tol * a else 0
            f.run_dn = f.run_dn + 1 if lo - c[q] > tol * a else 0
            if f.run_up >= R.BREAK_CONFIRM_CLOSES:
                tr = R.make_trade(False, q, e, med, e + width, n)
                if tr: sig["break_accel" if bull else "break_fail"].append(tr)
                live[bull] = None; continue
            if f.run_dn >= R.BREAK_CONFIRM_CLOSES:
                tr = R.make_trade(True, q, e, med, e - width, n)
                if tr: sig["break_fail" if bull else "break_accel"].append(tr)
                live[bull] = None; continue
            # parallel touches (first touch, closed back inside)
            lower_touch = l[q] <= lo < c[q] and l[q - 1] > lo1
            upper_touch = h[q] >= up > c[q] and h[q - 1] < up1
            if lower_touch and med > e:
                tr = R.make_trade(False, q, e, lo - R.STOP_BUFFER * a, med, n)
                if tr: sig["bounce_trend" if bull else "reject_counter"].append(tr)
            if upper_touch and med < e:
                tr = R.make_trade(True, q, e, up + R.STOP_BUFFER * a, med, n)
                if tr: sig["reject_counter" if bull else "bounce_trend"].append(tr)
        while ev < len(events) and events[ev][0] == q:
            snap = events[ev][1]
            f = fork_from_snapshot(snap, q)
            if f is not None:
                live[f.bull] = f
            else:
                # C of a live fork replaced by a more extreme pivot that no longer
                # forms a valid fork -> the live fork is dropped (redrawn as nothing)
                for bull in (True, False):
                    g = live[bull]
                    if g is not None and len(snap) >= 2 and snap[-2][0] == g.iB and snap[-1][0] != g.iC:
                        live[bull] = None
            ev += 1
        if state is not None:
            fb, fs = live[True], live[False]
            if fb is not None and (fs is None or fb.known >= fs.known):
                state[q] = 1
            elif fs is not None:
                state[q] = -1
    return sig


def run(name, df):
    o, h, l, c, atr = R.arrays(df)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    events, _ = R.causal_swing_events(o, h, l, c, atr)
    sig = detect(h, l, c, atr, events)
    print("\n" + "=" * 100)
    print(f"{name}: n={len(c)} bars, {years:.2f} yrs  raw signals: " + ", ".join(f"{k}={len(v)}" for k, v in sig.items()))
    print("=" * 100)
    t = df["time"].values
    summ = []
    for key, label in (("magnet", "(i) median-line magnet from C"),
                       ("bounce_trend", "(ii) with-trend parallel bounce -> median"),
                       ("reject_counter", "(iii) counter-trend parallel rejection -> median"),
                       ("break_accel", "(iv) breakout beyond with-trend parallel"),
                       ("break_fail", "(v) breakdown through trend-side parallel")):
        res = R.eval_book_pct(sig[key], h, l, c, times=t)
        summ.append(R.rigor_report(f"{name} pitchfork {label}", res, h, l, c))
    return summ


if __name__ == "__main__":
    summ = []
    summ += run("H4", R.load_h4_real())
    summ += run("M15", R.load_m15_real())
    R.verdict_table(summ, DECISION_K)
