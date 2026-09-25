"""
Real-data validation of TrendBreaker_MTF_Indicator.mq5's actual construction
(3-touch + BOS-validated anchors + wick/body-spike handling + ATR-tolerance
touch/pierce), asked directly (2026-09-25): "price does respect these
levels?" This is NOT a simplified strawman - it replicates the same pivot/
BOS/line-building logic as the real .mq5 file (FindSwings/AddSwing/BOSOk/
BuildLine), just in Python, on real GOLD H4 data (2001-2026, 23607 bars).

THREE questions, each with its own real control so the result means
something rather than confirming what we already expect:

1. DOES PRICE RESPECT A VALIDATED LINE? For every touch of a VALID line
   (3+ touches, BOS-anchored), classify the next REACT_BARS as a BOUNCE
   (price moves >= REACT_ATR away from the line) or a BREAK (>=
   BREAK_CONFIRM_CLOSES closes beyond it) - same definitions as the .mq5
   file's own InpTouchTolATR/InpBreakTolATR/BREAK_CONFIRM_CLOSES. Compared
   against a SHADOW control: the same line's own value but shifted by a
   random 1-3x ATR offset, tested at the exact same bar - isolates whether
   the SPECIFIC validated price level matters, not just "price near any
   round-ish level tends to wobble".

2. MA CONFLUENCE: among real touches, does proximity to a longer moving
   average (the classic "trendline + MA" confluence idea) raise the
   bounce rate?

3. WEDGE BREAKOUT DIRECTION: when both an up and a down VALID line are
   active at once (a converging wedge/triangle, exactly the pattern in the
   user's own chart), does the breakout DIRECTION predict the next
   REACT_BARS' net move, or is it closer to a coin flip?

Same real-data-first discipline as every other screen in this repo: real
numbers, real control, reported honestly either way.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E

np.random.seed(42)

# --- construction constants, identical to the .mq5 file ---------------
PIVOT_STRENGTH   = 5
SWING_MIN_ATR    = 1.0
ATR_PERIOD       = 14
TOUCH_TOL_ATR    = 0.25
PIERCE_TOL_ATR   = 0.35
BREAK_TOL_ATR    = 0.10
SPIKE_WICK_ATR   = 1.50
TOUCHES_TO_VALIDATE = 3
BREAK_CONFIRM_CLOSES = 3
REACT_BARS       = 10
REACT_ATR        = 0.75
LOOKBACK_BARS    = 300   # matches the .mq5 file's own InpLookbackBars - the
                          # real indicator only ever searches a rolling 300-
                          # bar window, never the whole history at once; an
                          # anchor pair further apart than this could never
                          # actually co-occur on a live chart, so excluding
                          # it isn't a simplification, it's fidelity


def sma_atr(high, low, close, period):
    """MT5's built-in iATR definition (rolling SMA of true range),
    matching the .mq5 file's own BuildATR() - NOT Wilder smoothing."""
    n = len(close)
    tr = np.empty(n)
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        pc = close[i - 1]
        tr[i] = max(high[i] - low[i], abs(high[i] - pc), abs(low[i] - pc))
    atr = pd.Series(tr).rolling(period, min_periods=1).mean().values
    return np.maximum(atr, 1e-6)


def ext_px(o, h, l, c, dir_, body):
    if dir_ < 0:
        return max(o, c) if body else h
    return min(o, c) if body else l


def wick_len(o, h, l, c, dir_):
    if dir_ < 0:
        return h - max(o, c)
    return min(o, c) - l


def find_swings(o, h, l, c, atr, body, N=PIVOT_STRENGTH):
    n = len(c)
    zIdx, zType, zPx = [], [], []
    last_closed = n - 2

    def ep(i, dir_):
        return ext_px(o[i], h[i], l[i], c[i], dir_, body)

    def add_swing(typ, idx, px, min_leg):
        if zType and zType[-1] == typ:
            more = (px > zPx[-1]) if typ == 1 else (px < zPx[-1])
            if more:
                zIdx[-1] = idx; zPx[-1] = px
            return
        if zPx and abs(px - zPx[-1]) < min_leg:
            return
        zIdx.append(idx); zType.append(typ); zPx.append(px)

    for i in range(N, last_closed - N + 1):
        hi, lo = ep(i, -1), ep(i, 1)
        isH = isL = True
        for m in range(1, N + 1):
            if ep(i - m, -1) >= hi or ep(i + m, -1) > hi:
                isH = False
            if ep(i - m, 1) <= lo or ep(i + m, 1) < lo:
                isL = False
            if not isH and not isL:
                break
        min_leg = SWING_MIN_ATR * atr[i]
        if isH and isL:
            if zType and zType[-1] == 1:
                add_swing(-1, i, lo, min_leg); add_swing(1, i, hi, min_leg)
            else:
                add_swing(1, i, hi, min_leg); add_swing(-1, i, lo, min_leg)
        elif isH:
            add_swing(1, i, hi, min_leg)
        elif isL:
            add_swing(-1, i, lo, min_leg)
    return zIdx, zType, zPx


def bos_ok(m, zIdx, zType, zPx, o, h, l, c, n, body):
    if m < 1 or zType[m - 1] == zType[m]:
        return False
    level = zPx[m - 1]
    end_i = zIdx[m + 2] if m + 2 < len(zIdx) else n - 2

    def ep(i, dir_):
        return ext_px(o[i], h[i], l[i], c[i], dir_, body)
    for q in range(zIdx[m] + 1, end_i + 1):
        if zType[m] == 1 and ep(q, 1) < level:
            return True
        if zType[m] == -1 and ep(q, -1) > level:
            return True
    return False


def build_line(o, h, l, c, atr, n, ia, ib, dir_, macro_body):
    body = macro_body
    if not body and (wick_len(o[ia], h[ia], l[ia], c[ia], dir_) > SPIKE_WICK_ATR * atr[ia] or
                      wick_len(o[ib], h[ib], l[ib], c[ib], dir_) > SPIKE_WICK_ATR * atr[ib]):
        body = True
    p1 = ext_px(o[ia], h[ia], l[ia], c[ia], dir_, body)
    p2 = ext_px(o[ib], h[ib], l[ib], c[ib], dir_, body)
    if dir_ < 0 and p2 >= p1:
        return None
    if dir_ > 0 and p2 <= p1:
        return None
    slope = (p2 - p1) / (ib - ia)
    gap = max(2, PIVOT_STRENGTH)
    touches, last_touch = 2, ia
    for q in range(ia + 1, ib):
        lv = p1 + slope * (q - ia)
        pe_ = ext_px(o[q], h[q], l[q], c[q], dir_, body)
        pen = (pe_ - lv) if dir_ < 0 else (lv - pe_)
        if pen > PIERCE_TOL_ATR * atr[q]:
            return None
        if pen >= -TOUCH_TOL_ATR * atr[q] and q - last_touch >= gap and ib - q >= gap:
            touches += 1; last_touch = q
    return dict(dir=dir_, ia=ia, ib=ib, p1=p1, p2=p2, slope=slope, body=body,
                touches=touches, atr_ib=atr[ib])


if __name__ == "__main__":
    df = E.load_h4()
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    ma200 = pd.Series(c).rolling(200, min_periods=1).mean().values
    print(f"H4 data: {df['time'].min()} -> {df['time'].max()}, n={n} bars\n")

    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    print(f"swings found: {len(zIdx)}")

    lines = []
    for dir_, want in ((1, 1), (-1, -1)):
        anchors = [zIdx[m] for m in range(len(zIdx))
                   if zType[m] == want and bos_ok(m, zIdx, zType, zPx, o, h, l, c, n, False)]
        for ai in range(len(anchors)):
            for bi in range(ai + 1, len(anchors)):
                a, b = anchors[ai], anchors[bi]
                if b - a < PIVOT_STRENGTH or b - a > LOOKBACK_BARS:
                    continue
                L = build_line(o, h, l, c, atr, n, a, b, dir_, False)
                if L is not None:
                    lines.append(L)
    valid_lines = [L for L in lines if L["touches"] >= TOUCHES_TO_VALIDATE]
    print(f"candidate lines: {len(lines)}, VALID (3+ touches): {len(valid_lines)}\n")

    # ============================================================
    # Q1: does price respect a VALID line - real touches after validation
    # ============================================================
    real_outcomes = []   # +1 bounce, -1 break, 0 inconclusive
    shadow_outcomes = []
    ma_conf_flags = []   # parallel to real_outcomes: True if within 1 ATR of MA200 at touch

    for L in valid_lines:
        dir_, ia, ib, p1, slope, body = L["dir"], L["ia"], L["ib"], L["p1"], L["slope"], L["body"]
        last_touch = ib
        q = ib + 1
        died = False
        while q < n - REACT_BARS and not died:
            a = atr[q]
            lv = p1 + slope * (q - ia)
            pe_ = ext_px(o[q], h[q], l[q], c[q], dir_, body)
            pen = (pe_ - lv) if dir_ < 0 else (lv - pe_)
            penC = (c[q] - lv) if dir_ < 0 else (lv - c[q])
            # a "touch": within tolerance, spaced from the last one
            if pen >= -TOUCH_TOL_ATR * a and pen <= TOUCH_TOL_ATR * a and q - last_touch >= max(2, PIVOT_STRENGTH):
                last_touch = q
                # forward outcome over REACT_BARS
                outcome = 0
                closes_beyond = 0
                for k in range(q + 1, min(q + 1 + REACT_BARS, n)):
                    lvk = p1 + slope * (k - ia)
                    penCk = (c[k] - lvk) if dir_ < 0 else (lvk - c[k])
                    if penCk > BREAK_TOL_ATR * atr[k]:
                        closes_beyond += 1
                        if closes_beyond >= BREAK_CONFIRM_CLOSES:
                            outcome = -1; break
                    else:
                        closes_beyond = 0
                    pekAway = (lvk - ext_px(o[k], h[k], l[k], c[k], -dir_, body)) if dir_ < 0 else \
                              (ext_px(o[k], h[k], l[k], c[k], -dir_, body) - lvk)
                    # distance moved AWAY from the line, on the trend side
                    away = (lvk - c[k]) if dir_ < 0 else (c[k] - lvk)
                    if away > REACT_ATR * atr[k]:
                        outcome = 1; break
                if outcome != 0:
                    real_outcomes.append(outcome)
                    ma_conf_flags.append(abs(lv - ma200[q]) <= 1.0 * a)
                    # SHADOW CONTROL (fixed): a FLAT line drawn exactly through
                    # price at this same bar q, same dir_ convention, same
                    # forward test. This is genuinely "at" price the same way
                    # a real touch is, so it isolates whether the FITTED,
                    # VALIDATED, SLOPED line is doing real work, vs. "price
                    # near wherever it happens to be" showing similar
                    # short-term bounce/break behaviour on its own. (The
                    # earlier version shifted the line 1-3x ATR AWAY from
                    # price before testing it, which trivially reports
                    # "bounce" every time since the shift itself already
                    # exceeds REACT_ATR - a bug, not a control; fixed here.)
                    lv_s0 = c[q]
                    outcome_s = 0
                    closes_beyond_s = 0
                    for k in range(q + 1, min(q + 1 + REACT_BARS, n)):
                        lvk_s = lv_s0   # flat - a trendline's slope is the thing under test, so the control has none
                        penCk_s = (c[k] - lvk_s) if dir_ < 0 else (lvk_s - c[k])
                        if penCk_s > BREAK_TOL_ATR * atr[k]:
                            closes_beyond_s += 1
                            if closes_beyond_s >= BREAK_CONFIRM_CLOSES:
                                outcome_s = -1; break
                        else:
                            closes_beyond_s = 0
                        away_s = (lvk_s - c[k]) if dir_ < 0 else (c[k] - lvk_s)
                        if away_s > REACT_ATR * atr[k]:
                            outcome_s = 1; break
                    shadow_outcomes.append(outcome_s)
            # line death: 3 consecutive closes beyond -> stop walking this line
            if penC > BREAK_TOL_ATR * a:
                q2 = q; run = 0
                for k in range(q, min(q + 5, n)):
                    lvk = p1 + slope * (k - ia)
                    penCk = (c[k] - lvk) if dir_ < 0 else (lvk - c[k])
                    if penCk > BREAK_TOL_ATR * atr[k]:
                        run += 1
                        if run >= BREAK_CONFIRM_CLOSES:
                            died = True; break
                    else:
                        break
            q += 1

    real_outcomes = np.array(real_outcomes)
    shadow_outcomes = np.array(shadow_outcomes)
    ma_conf_flags = np.array(ma_conf_flags)

    def summarize(outcomes, label):
        n_ = len(outcomes)
        if n_ == 0:
            print(f"  {label}: 0 definitive outcomes"); return
        bounce = (outcomes == 1).sum(); brk = (outcomes == -1).sum()
        print(f"  {label}: n={n_} bounce={bounce} ({100*bounce/n_:.1f}%) break={brk} ({100*brk/n_:.1f}%)")

    print("=" * 70)
    print("Q1: does price respect a VALID line? (real touches vs shadow control)")
    summarize(real_outcomes, "REAL validated-line touches")
    summarize(shadow_outcomes, "SHADOW (flat line drawn through price at the same bar)")
    if len(real_outcomes) > 8 and len(shadow_outcomes) > 8:
        from scipy import stats
        real_bounce = (real_outcomes == 1).astype(int)
        shadow_bounce = (shadow_outcomes == 1).astype(int)
        try:
            table = [[real_bounce.sum(), len(real_bounce) - real_bounce.sum()],
                     [shadow_bounce.sum(), len(shadow_bounce) - shadow_bounce.sum()]]
            odds, p = stats.fisher_exact(table, alternative="greater")
            print(f"  Fisher exact test (real bounce rate > shadow rate): odds={odds:.2f} p={p:.4f}")
        except Exception as e:
            print(f"  (stats test skipped: {e})")

    print("\n" + "=" * 70)
    print("Q2: MA(200) confluence - does proximity to the MA raise the real bounce rate?")
    if ma_conf_flags.sum() > 5 and (~ma_conf_flags).sum() > 5:
        near = real_outcomes[ma_conf_flags]
        far = real_outcomes[~ma_conf_flags]
        summarize(near, "near MA200 (<=1 ATR)")
        summarize(far, "far from MA200 (>1 ATR)")
    else:
        print(f"  not enough split: near={ma_conf_flags.sum()} far={(~ma_conf_flags).sum()}")

    # ============================================================
    # Q3: WEDGE breakout direction - the user's own chart question
    # ============================================================
    print("\n" + "=" * 70)
    print("Q3: converging wedge (up+down both VALID) - does breakout direction predict follow-through?")
    up_lines = [L for L in valid_lines if L["dir"] > 0]
    dn_lines = [L for L in valid_lines if L["dir"] < 0]
    wedge_results = []
    for U in up_lines:
        for D in dn_lines:
            # both must be "alive" (built) over a shared window
            start = max(U["ib"], D["ib"])
            end = min(start + 200, n - REACT_BARS)   # look up to 200 bars ahead for a breakout
            if start >= end:
                continue
            brk_dir, brk_q = 0, -1
            run_u, run_d = 0, 0
            for q in range(start, end):
                lu = U["p1"] + U["slope"] * (q - U["ia"])
                ld = D["p1"] + D["slope"] * (q - D["ia"])
                if ld <= lu:   # lines have crossed - wedge resolved/apex passed, stop
                    break
                penU = lu - c[q]        # >0 means price still above the up-line (inside)
                penD = c[q] - ld        # >0 means price still below the down-line (inside)
                if c[q] < lu - BREAK_TOL_ATR * atr[q]:
                    run_u += 1
                    if run_u >= BREAK_CONFIRM_CLOSES:
                        brk_dir, brk_q = -1, q; break
                else:
                    run_u = 0
                if c[q] > ld + BREAK_TOL_ATR * atr[q]:
                    run_d += 1
                    if run_d >= BREAK_CONFIRM_CLOSES:
                        brk_dir, brk_q = 1, q; break
                else:
                    run_d = 0
            if brk_dir != 0 and brk_q + REACT_BARS < n:
                net = c[brk_q + REACT_BARS] - c[brk_q]
                consistent = (net > 0) == (brk_dir > 0)
                wedge_results.append(consistent)
    if len(wedge_results) >= 5:
        wr = np.array(wedge_results)
        print(f"  n={len(wr)} wedge breakouts, direction-consistent follow-through: "
              f"{wr.sum()}/{len(wr)} ({100*wr.mean():.1f}%) - vs 50% coin-flip baseline")
    else:
        print(f"  only {len(wedge_results)} wedge-breakout events found on H4 over 25 years - too few to conclude anything")
