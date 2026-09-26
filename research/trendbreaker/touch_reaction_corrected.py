"""
CORRECTED re-run of the touch-reaction research after an Opus review
(2026-09-26) of first_touch_test.py/pierce_tolerance_test.py found that
h4_touch_reaction_test.py's own anchor/dir pairing - inherited unchanged
into both new files - was BACKWARDS relative to the real .mq5's own logic,
and that the "PIERCE_TOL_ATR is the bottleneck" conclusion built on top of
it was therefore built on a broken construction, not a real finding.

THE BUG (confirmed directly against TrendBreaker_MTF_Indicator.mq5:906-907):
    real .mq5:   int dir = (d==0) ? 1 : -1;
                 int want = (dir < 0) ? 1 : -1;   // resistance from HIGHS, support from LOWS
    -> dir=+1 (up/support line) pairs with want=-1 (anchors = swing LOWS)
    -> dir=-1 (down/resistance line) pairs with want=+1 (anchors = swing HIGHS)

    python (h4_touch_reaction_test.py:182, copied into both new files):
                 for dir_, want in ((1, 1), (-1, -1)):
    -> dir_=+1 paired with want=+1 (anchors = swing HIGHS - WRONG)
    -> dir_=-1 paired with want=-1 (anchors = swing LOWS - WRONG)

    Consequence: build_line's own ext_px(..., dir_, ...) extracts the LOW
    of each anchor bar when dir_=+1, but the anchors it was fed were swing
    HIGHS (want=+1) - i.e. it was fitting a line through the LOW price of
    two bars that happen to be flagged as swing highs, not through the
    actual low pivots. Those "low" values on a high-flagged bar are close
    to arbitrary relative to price structure, which is almost never
    parallel to real price action for long - explaining why almost no
    candidate line ever survived PIERCE_TOL_ATR=0.35 (2 lines on H4/25yrs,
    4 on M15/4.2yrs). That scarcity was a bug artifact, not a real finding
    about how strict the indicator's own pierce tolerance is. Confirmed by
    Opus: swapping the pairing alone (nothing else changed) produced 1401
    candidate lines on H4 and 5464 on M15 at the SAME PIERCE_TOL_ATR=0.35.

ADDITIONAL FIXES applied here per the same review, all real and disclosed:
  1. Anchor/dir pairing corrected (the critical fix above).
  2. sma_atr() was being called as sma_atr(h, l, o, period) - passing OPEN
     into the parameter documented and used internally as CLOSE (previous-
     close is used for true-range gap terms). Fixed to pass c. Minor vs.
     fix #1, but real, and was present in every trendbreaker script that
     copied this call pattern.
  3. A line is now RETIRED (no event recorded, stop walking it) the first
     time price closes beyond it by BREAK_TOL_ATR*ATR before any touch is
     found - matching the real .mq5's ST_TENT retirement-on-first-break
     behaviour (BuildLine ~line 748). The original first_touch_test.py had
     no such check and would happily record a "touch" on a line that had
     already broken down bars earlier.
  4. LOOKAHEAD FIX: a candidate anchor only enters the `anchors` list once
     bos_ok() says it EVENTUALLY gets BOS-confirmed - but "eventually" can
     be many bars after the anchor's own bar index. A real-time trader
     couldn't have known bar `ib` was a genuine confirmed pivot until the
     confirming bar itself. get_confirm_bar() now returns that bar
     explicitly, and no touch is evaluated before max(ib+1, confirm_ib) -
     i.e. the line is only "live" once ITS OWN more-recent anchor has
     actually been confirmed by real subsequent price action, not the bar
     the anchor happens to sit on.
  5. CONTROL FIX: the original shadow control was a flat line drawn through
     the exact CLOSE at the touch bar q - but a "touch" is judged using the
     bar's WICK (ext_px), so the close can already sit measurably away from
     the line at the moment of the touch (a real, uncontrolled head start
     toward registering a "bounce" that the old control never got, since it
     was defined to start at zero distance from price by construction).
     Fixed: for every real event, compute offset = lv(q) - c[q] (the line's
     signed distance from that bar's close) and dir_, then re-test the SAME
     offset and slope-implied dynamics but anchored to a RANDOMLY CHOSEN
     OTHER bar in the dataset (`lv_ctrl(k) = c[q_rand] + offset` extended
     flat from there) - isolating "does this specific fitted, anchored,
     validated diagonal matter" from "does being offset from price by this
     typical touch-residual amount produce mean-reversion generically".
  6. DECLUSTERING: events from different candidate lines can land on
     nearby/overlapping bars (non-independent for a Fisher exact test).
     Reports both the raw event count and a declustered count (greedily
     keep the earliest event in any run of events within REACT_BARS of
     each other) so the reader can see how much the raw n is inflated by
     clustering.

Run at the indicator's own SHIPPED default (PIERCE_TOL_ATR=0.35,
TOUCHES_TO_VALIDATE noted separately) first - that is the real question
("can the shipped indicator's lines be traded") - plus a short sweep for
context, same as before.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
import h4_touch_reaction_test as M
from h4_touch_reaction_test import (
    find_swings, bos_ok, build_line, ext_px,
    PIVOT_STRENGTH, ATR_PERIOD, TOUCH_TOL_ATR, BREAK_TOL_ATR,
    BREAK_CONFIRM_CLOSES, REACT_BARS, REACT_ATR, LOOKBACK_BARS,
)

np.random.seed(42)
PIERCE_LEVELS = (0.35, 0.5, 0.75, 1.0, 1.5)


def sma_atr_fixed(high, low, close, period):
    import pandas as pd
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        pc = close[i - 1]
        tr[i] = max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc))
    atr = pd.Series(tr).rolling(period, min_periods=1).mean().values
    return np.maximum(atr, 1e-6)


def get_confirm_bar(m, zIdx, zType, zPx, o, h, l, c, n, body):
    """Same walk as bos_ok(), but returns the actual confirming bar index
    (or -1) instead of a bool - the bar at which this pivot's BOS
    confirmation genuinely became known, not the pivot's own bar index."""
    if m < 1 or zType[m - 1] == zType[m]:
        return -1
    level = zPx[m - 1]
    end_i = zIdx[m + 2] if m + 2 < len(zIdx) else n - 2
    for q in range(zIdx[m] + 1, end_i + 1):
        if zType[m] == 1 and ext_px(o[q], h[q], l[q], c[q], 1, body) < level:
            return q
        if zType[m] == -1 and ext_px(o[q], h[q], l[q], c[q], -1, body) > level:
            return q
    return -1


def build_all_lines_fixed(o, h, l, c, atr, n, pierce, lookback):
    orig = M.PIERCE_TOL_ATR
    M.PIERCE_TOL_ATR = pierce
    try:
        zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
        confirm = {m: get_confirm_bar(m, zIdx, zType, zPx, o, h, l, c, n, False) for m in range(len(zIdx))}
        lines = []
        # CORRECTED pairing: dir=+1 (up/support) <-> want=-1 (lows);
        # dir=-1 (down/resistance) <-> want=+1 (highs) - matches .mq5:907
        for dir_, want in ((1, -1), (-1, 1)):
            anchor_ms = [m for m in range(len(zIdx)) if zType[m] == want and confirm[m] >= 0]
            for ai in range(len(anchor_ms)):
                for bi in range(ai + 1, len(anchor_ms)):
                    ma, mb = anchor_ms[ai], anchor_ms[bi]
                    a, b = zIdx[ma], zIdx[mb]
                    if b - a < PIVOT_STRENGTH or b - a > lookback:
                        continue
                    L = build_line(o, h, l, c, atr, n, a, b, dir_, False)
                    if L is not None:
                        L["confirm_ib"] = confirm[mb]
                        lines.append(L)
        return lines
    finally:
        M.PIERCE_TOL_ATR = orig


def first_touch_events_fixed(o, h, l, c, atr, n, lines, rng):
    gap = max(2, PIVOT_STRENGTH)
    events = []
    for L in lines:
        dir_, ia, ib, p1, slope, body = L["dir"], L["ia"], L["ib"], L["p1"], L["slope"], L["body"]
        start_q = max(ib + 1, L["confirm_ib"])   # fix #4: can't trade before ib itself is confirmed
        last_touch = ib
        for q in range(start_q, min(n - REACT_BARS, ib + LOOKBACK_BARS)):
            a = atr[q]
            lv = p1 + slope * (q - ia)
            pe_ = ext_px(o[q], h[q], l[q], c[q], dir_, body)
            penC = (c[q] - lv) if dir_ < 0 else (lv - c[q])
            pen = (pe_ - lv) if dir_ < 0 else (lv - pe_)
            # fix #3: retire on first close-beyond before any touch found
            if penC > BREAK_TOL_ATR * a:
                break
            if pen >= -TOUCH_TOL_ATR * a and pen <= TOUCH_TOL_ATR * a and q - last_touch >= gap:
                outcome = forward_outcome(o, h, l, c, atr, n, dir_, p1, slope, ia, q)
                if outcome != 0:
                    offset = lv - c[q]
                    q_rand = int(rng.integers(REACT_BARS, n - REACT_BARS - 1))
                    ctrl = matched_offset_outcome(c, atr, n, dir_, offset, q_rand)
                    events.append(dict(q=q, outcome=outcome, ctrl=ctrl))
                break
    return events


def forward_outcome(o, h, l, c, atr, n, dir_, p1, slope, ia, q):
    outcome, closes_beyond = 0, 0
    for k in range(q + 1, min(q + 1 + REACT_BARS, n)):
        lvk = p1 + slope * (k - ia)
        penCk = (c[k] - lvk) if dir_ < 0 else (lvk - c[k])
        if penCk > BREAK_TOL_ATR * atr[k]:
            closes_beyond += 1
            if closes_beyond >= BREAK_CONFIRM_CLOSES:
                return -1
        else:
            closes_beyond = 0
        away = (lvk - c[k]) if dir_ < 0 else (c[k] - lvk)
        if away > REACT_ATR * atr[k]:
            return 1
    return outcome


def matched_offset_outcome(c, atr, n, dir_, offset, q0):
    """Fix #5: a flat control line carrying the SAME offset from price the
    real line had at its own touch bar, anchored at a random other bar."""
    lv0 = c[q0] + offset
    outcome, closes_beyond = 0, 0
    for k in range(q0 + 1, min(q0 + 1 + REACT_BARS, n)):
        penCk = (c[k] - lv0) if dir_ < 0 else (lv0 - c[k])
        if penCk > BREAK_TOL_ATR * atr[k]:
            closes_beyond += 1
            if closes_beyond >= BREAK_CONFIRM_CLOSES:
                return -1
        else:
            closes_beyond = 0
        away = (lv0 - c[k]) if dir_ < 0 else (c[k] - lv0)
        if away > REACT_ATR * atr[k]:
            return 1
    return outcome


def decluster(events):
    events = sorted(events, key=lambda e: e["q"])
    kept, last_q = [], -10 ** 9
    for e in events:
        if e["q"] - last_q >= REACT_BARS:
            kept.append(e)
            last_q = e["q"]
    return kept


def summarize(events, label):
    n_ = len(events)
    if n_ == 0:
        print(f"    {label}: 0 events")
        return
    real = np.array([e["outcome"] for e in events])
    ctrl = np.array([e["ctrl"] for e in events])
    rb = (real == 1).sum(); cb = (ctrl == 1).sum()
    line = f"    {label}: n={n_}  real bounce={100*rb/n_:.1f}%  matched-control bounce={100*cb/n_:.1f}%"
    if n_ >= 15:
        from scipy import stats
        table = [[rb, n_ - rb], [cb, n_ - cb]]
        odds, p = stats.fisher_exact(table, alternative="greater")
        line += f"  Fisher p={p:.4f}"
    print(line)


def run_timeframe(name, df):
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    n = len(c)
    atr = sma_atr_fixed(h, l, c, ATR_PERIOD)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    rng = np.random.default_rng(42)
    print("\n" + "=" * 92)
    print(f"{name}: n={n} bars, {years:.2f} yrs (ATR bug fixed, anchors fixed)")
    print("=" * 92)

    for pierce in PIERCE_LEVELS:
        lines = build_all_lines_fixed(o, h, l, c, atr, n, pierce, LOOKBACK_BARS)
        events = first_touch_events_fixed(o, h, l, c, atr, n, lines, rng)
        dec = decluster(events)
        print(f"  PIERCE_TOL_ATR={pierce}: lines={len(lines)} ({len(lines)/years:.1f}/yr)  "
              f"events raw={len(events)} ({len(events)/years:.1f}/yr)  declustered={len(dec)} ({len(dec)/years:.1f}/yr)")
        summarize(events, "raw")
        summarize(dec, "declustered")


if __name__ == "__main__":
    h4 = E.load_h4()
    run_timeframe("H4", h4)

    m5 = E.load_m5()
    m15 = E.resample_m15_from_m5(m5)
    run_timeframe("M15 (resampled from real M5)", m15)
