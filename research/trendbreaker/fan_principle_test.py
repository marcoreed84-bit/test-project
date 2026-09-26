"""
Fan Principle (Edwards & Magee / Murphy; user's 2026-09-26 textbook,
Errante Academy "The Art of Trend Analysis and Chart Mastery") - tested as
a standalone system on real H4 and real native M15, with the full
random-timing + best-of-K pipeline (pattern_rigor_common.py).

PRIOR WORK, disclosed: research/aurelius/fan_trendline_test.py (commit
92ba72a) already tried a 3rd-line fan break on M5 with Vanguard-style
hold-to-reversal exits and rejected it (no edge anywhere in its k x stop
grid once still-open trades at the data boundary were excluded). It never
had a random-timing baseline, never tested H4/M15, never compared the
2nd- vs 3rd-line entry, and used a plain k-bar fractal list (no causal
zigzag). This file is the rigorous version the user asked for, not a
re-run of that one.

CONSTRUCTION (bullish fan = reversal of a DOWNTREND -> BUY; the bearish
fan is the exact mirror on swing lows -> SELL). Swings: the repo's standard
find_swings() zigzag, consumed CAUSALLY via causal_swing_events() (a swing
exists for this detector only from pivot bar + PIVOT_STRENGTH onward, and
only in the state it was known in - see pattern_rigor_common.py):
  - ORIGIN A = the highest swing high of the current down-episode. Any new
    swing high >= A (or the first high after a completed fan) resets the
    fan with that high as the new origin.
  - LINE 1 = A -> the latest LOWER swing high H1 (re-anchored to each newer
    lower high while unbroken - i.e. it is the live down-trendline).
  - BREAK k = BREAK_CONFIRM_CLOSES(3) consecutive closes above line k by
    BREAK_TOL_ATR(0.10) x ATR - the same break rule every pattern in this
    directory uses - scanned only from the bar AFTER the anchor became
    knowable.
  - After break k, the next swing high H(k+1) that forms AFTER the break
    bar (the retest/pullback high) anchors LINE k+1 = A -> H(k+1). It must
    sit ABOVE the broken line k at its own bar (the fan genuinely flattens;
    this is the "old line becomes support, price retests it" step). If
    instead a new lower high forms BELOW line k, the break was false and the
    downtrend resumed: the fan resets to break-count 0 with line 1 = A -> that
    high.
  - ENTRY (tested separately, as asked): the close completing break 2
    ("2nd-line break"), and the close completing break 3 ("3rd-line
    break", the classical signal). Break 1 (a plain trendline break from the
    origin - essentially the already-rejected Vanguard idea) is reported
    for reference only. After break 3 the fan is complete and resets.
  - STOP = lowest low between the current line's anchor and the entry bar,
    minus STOP_BUFFER(1.0) x ATR. TARGET = 2R. The fan principle has no
    textbook measured-move target, so 2R was fixed a priori (not tuned),
    disclosed as a choice. Same MAX_HORIZON_CAP=400 as every other pattern.

Both timeframes, real bars only: H4 2013-05 -> 2026-09 (load_h4_real) and
native M15 2014-06 -> 2026-09 (load_m15_real) - see pattern_rigor_common.py
for why the earlier rows of those files are excluded.

K for the multiple-testing correction: this file itself tries 3 entry
variants x 2 timeframes = 6; the trendline-family research this idea
belongs to (trendline_break/confluence/m15/fan tests in research/aurelius
plus this directory's touch/pierce/first-touch/effort files) is at least
~15 more. K=15/30 are the honest floors; 50/100 shown for sensitivity.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pattern_rigor_common as R

DECISION_K = 30


class Fan:
    """One direction's fan state machine. bull=True: anchors are swing highs,
    breaks are closes ABOVE the line, signal is a BUY."""

    def __init__(self, bull):
        self.bull = bull
        self.reset(None)

    def reset(self, origin):
        self.origin = origin          # (idx, px)
        self.anchor = None            # (idx, px, known_bar)
        self.breaks = 0
        self.awaiting = False         # waiting for the next anchor after a break
        self.last_break_bar = -1
        self.prev_line = None         # (i0, p0, i1, p1) of the last broken line
        self.run = 0

    @staticmethod
    def line_at(i0, p0, i1, p1, q):
        return p0 + (p1 - p0) * (q - i0) / (i1 - i0)

    def cur_line(self, q):
        return self.line_at(self.origin[0], self.origin[1], self.anchor[0], self.anchor[1], q)

    def on_swing(self, idx, px, known):
        """A new/updated swing of the anchor type (high for bull, low for bear)."""
        beyond_origin = self.origin is None or (px >= self.origin[1] if self.bull else px <= self.origin[1])
        if beyond_origin or idx <= self.origin[0]:
            self.reset((idx, px))
            return
        if self.breaks == 0:
            self.anchor = (idx, px, known); self.run = 0
            return
        if self.awaiting and idx <= self.last_break_bar:
            return   # a replacement of a pre-break swing - not a new fan anchor
        i0, p0, i1, p1 = self.prev_line
        pl = self.line_at(i0, p0, i1, p1, idx)
        flatter = (px > pl) if self.bull else (px < pl)
        if flatter:
            self.anchor = (idx, px, known); self.awaiting = False; self.run = 0
        else:
            # false break - the trend resumed below the broken line
            self.breaks = 0; self.awaiting = False; self.prev_line = None
            self.anchor = (idx, px, known); self.run = 0

    def on_bar(self, q, c, atr):
        """Check bar q's close against the active line (state known at q-1).
        Returns the break number completed on this bar, or 0."""
        if self.origin is None or self.anchor is None or self.awaiting:
            return 0
        if q <= self.anchor[2]:
            return 0
        lv = self.cur_line(q)
        beyond = (c[q] - lv) if self.bull else (lv - c[q])
        if beyond > R.BREAK_TOL_ATR * atr[q]:
            self.run += 1
        else:
            self.run = 0
        if self.run < R.BREAK_CONFIRM_CLOSES:
            return 0
        self.breaks += 1
        k = self.breaks
        self.prev_line = (self.origin[0], self.origin[1], self.anchor[0], self.anchor[1])
        self.last_break_bar = q
        self.awaiting = True
        self.run = 0
        return k


def detect(df):
    o, h, l, c, atr = R.arrays(df)
    n = len(c)
    events, _ = R.causal_swing_events(o, h, l, c, atr)
    fans = {1: Fan(True), -1: Fan(False)}
    last_seen = {1: None, -1: None}
    signals = {1: [], 2: [], 3: []}
    ev = 0
    for q in range(n):
        for typ, fan in fans.items():
            k = fan.on_bar(q, c, atr)
            if k == 0:
                continue
            anchor_i = fan.prev_line[2]
            entry = c[q]
            if fan.bull:
                stop = l[anchor_i:q + 1].min() - R.STOP_BUFFER * atr[q]
                target = entry + 2.0 * (entry - stop)
            else:
                stop = h[anchor_i:q + 1].max() + R.STOP_BUFFER * atr[q]
                target = entry - 2.0 * (stop - entry)
            tr = R.make_trade(not fan.bull, q, entry, stop, target, n)
            if tr is not None and k <= 3:
                tr["tag"] = k
                signals[k].append(tr)
            if k >= 3:
                fan.reset(None)
        while ev < len(events) and events[ev][0] == q:
            snap = events[ev][1]
            for typ in (1, -1):
                sw = [s for s in snap if s[1] == typ]
                if not sw:
                    continue
                last = (sw[-1][0], sw[-1][2])
                if last != last_seen[typ]:
                    last_seen[typ] = last
                    fans[typ].on_swing(last[0], last[1], q)
            ev += 1
    return signals, (h, l, c, atr)


def run(name, df):
    years = (df["time"].max() - df["time"].min()).days / 365.25
    signals, (h, l, c, atr) = detect(df)
    print("\n" + "=" * 100)
    print(f"{name}: n={len(c)} bars, {years:.2f} yrs  |  raw fan-break signals: "
          f"line1={len(signals[1])}  line2={len(signals[2])}  line3={len(signals[3])}")
    print("=" * 100)
    out = []
    t = df["time"].values
    for k, label in ((1, "1st-line break (reference only)"), (2, "2nd-line break entry"), (3, "3rd-line break entry (classical)")):
        res = R.eval_book_pct(signals[k], h, l, c, times=t)
        s = R.rigor_report(f"{name} fan {label}", res, h, l, c)
        out.append(s)
    return out


if __name__ == "__main__":
    summ = []
    summ += run("H4", R.load_h4_real())
    summ += run("M15", R.load_m15_real())
    R.verdict_table(summ, DECISION_K)
