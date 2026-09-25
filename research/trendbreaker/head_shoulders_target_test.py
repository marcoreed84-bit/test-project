"""
Tests the Head & Shoulders measured-move target rule from the Fidelity/
Kirkpatrick "Identifying Chart Patterns" deck (2026-09-25): "Target is the
distance from the head to the neckline projected from the neckline" -
plus the mirror Inverse H&S (bottom) rule. Real GOLD data, both H4 and D1
(reusing the same real pivot detection as the trendline validation work,
find_swings() from h4_touch_reaction_test.py - NOT the straight-line
BuildLine() fitter, since H&S detection is a 5-swing shape match, not a
no-pierce-between-anchors line fit, so D1's earlier "zero candidates"
result doesn't apply here - worth re-testing D1 on this different
construction rather than assuming it fails the same way).

PATTERN (top): 5 consecutive alternating swings H1-L1-H2-L2-H3 where
  - H2 (head) > H1 and H2 > H3
  - H1, H3 (shoulders) roughly level: |H1-H3| <= SHOULDER_TOL_ATR x ATR
  - neckline = the line through L1, L2 (can be sloped)
  - breakout = BREAK_CONFIRM_CLOSES consecutive closes below the neckline
    (projected forward), same confirmation convention as the trendline work
  - target = (head price - neckline value AT THE HEAD's time), projected
    DOWN from the breakout price
Inverse (bottom) is the exact mirror: L1-H1-L2-H2-L3, head = L2 (lowest),
neckline through H1/H2, breakout = closes above neckline, target = height
added UP from the breakout price.

TEST: does price actually reach the target within a real horizon? Two
honest comparisons rather than just reporting the hit rate on its own:
  (a) a HALF-HEIGHT control (target = 50% of the measured distance) -
      if the full measured target hits about as often as a much smaller
      one, the SPECIFIC height calculation isn't doing much work.
  (b) calibration: of the moves that eventually reverse/stall, how far
      did price actually travel as a fraction of the measured target -
      systematically short, long, or well-centered on 100%?
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_CONFIRM_CLOSES

np.random.seed(42)

SHOULDER_TOL_ATR = 1.5    # shoulders "roughly the same level" - within this many ATR of each other
BREAK_TOL_ATR = 0.10      # same convention as the trendline work
MAX_HORIZON_MULT = 4.0    # look for the target up to this many x the pattern's own formation length
MAX_HORIZON_CAP = 400     # absolute bar cap regardless of pattern length


def find_hs_patterns(zIdx, zType, zPx, top):
    """top=True: H1-L1-H2-L2-H3 (head & shoulders top).
    top=False: L1-H1-L2-H2-L3 (inverse, bottom)."""
    want_outer = 1 if top else -1
    patterns = []
    for m in range(len(zIdx) - 4):
        seq = zType[m:m + 5]
        if top and seq != [1, -1, 1, -1, 1]:
            continue
        if not top and seq != [-1, 1, -1, 1, -1]:
            continue
        p1, t1, p2, t2, p3 = zPx[m:m + 5]
        i1, it1, i2, it2, i3 = zIdx[m:m + 5]
        if top:
            if not (p2 > p1 and p2 > p3):
                continue
        else:
            if not (p2 < p1 and p2 < p3):
                continue
        patterns.append(dict(i_s1=i1, p_s1=p1, i_t1=it1, p_t1=t1,
                              i_head=i2, p_head=p2, i_t2=it2, p_t2=t2,
                              i_s2=i3, p_s2=p3, top=top))
    return patterns


def run(df, label):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    print(f"\n{label}: {df['time'].min()} -> {df['time'].max()}, n={n} bars")

    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    print(f"  swings found: {len(zIdx)}")

    real_results = []   # (hit: bool, frac_of_target_reached_if_not_hit, bars_to_hit)
    half_results = []
    for top in (True, False):
        pats = find_hs_patterns(zIdx, zType, zPx, top)
        shoulder_ok = [p for p in pats
                       if abs(p["p_s1"] - p["p_s2"]) <= SHOULDER_TOL_ATR * atr[p["i_head"]]]
        print(f"  {'H&S top' if top else 'Inverse H&S'}: {len(pats)} raw shapes, "
              f"{len(shoulder_ok)} with level shoulders (<= {SHOULDER_TOL_ATR} ATR apart)")

        for p in shoulder_ok:
            ia, ib = p["i_t1"], p["i_t2"]
            neck_slope = (p["p_t2"] - p["p_t1"]) / (ib - ia) if ib != ia else 0.0

            def neckline_at(q):
                return p["p_t1"] + neck_slope * (q - ia)

            head_height = abs(p["p_head"] - neckline_at(p["i_head"]))
            if head_height <= 0:
                continue
            pattern_len = p["i_s2"] - p["i_s1"]
            horizon_end = min(n - 1, p["i_s2"] + int(min(pattern_len * MAX_HORIZON_MULT, MAX_HORIZON_CAP)))

            # find confirmed breakout after the right shoulder
            brk_q, run_ = -1, 0
            for q in range(p["i_s2"] + 1, horizon_end):
                nl = neckline_at(q)
                beyond = (nl - c[q]) if top else (c[q] - nl)
                if beyond > BREAK_TOL_ATR * atr[q]:
                    run_ += 1
                    if run_ >= BREAK_CONFIRM_CLOSES:
                        brk_q = q; break
                else:
                    run_ = 0
            if brk_q < 0:
                continue

            brk_price = c[brk_q]
            target = (brk_price - head_height) if top else (brk_price + head_height)
            half_target = (brk_price - 0.5 * head_height) if top else (brk_price + 0.5 * head_height)

            hit, hit_half, bars_to_hit = False, False, -1
            max_travel = 0.0
            for k in range(brk_q + 1, min(brk_q + 1 + MAX_HORIZON_CAP, n)):
                reached = (l[k] <= target) if top else (h[k] >= target)
                reached_half = (l[k] <= half_target) if top else (h[k] >= half_target)
                travel = (brk_price - l[k]) if top else (h[k] - brk_price)
                max_travel = max(max_travel, travel)
                if reached_half and not hit_half:
                    hit_half = True
                if reached and not hit:
                    hit, bars_to_hit = True, k - brk_q
                    break
            frac = max_travel / head_height if head_height > 0 else 0.0
            real_results.append((hit, frac, bars_to_hit, brk_q))
            half_results.append(hit_half)

    n_ = len(real_results)
    if n_ == 0:
        print("  0 confirmed H&S breakouts found - nothing to test"); return

    def report(idxs, sublabel):
        if len(idxs) < 8:
            print(f"  {sublabel}: only {len(idxs)} events - too few to conclude anything"); return
        sub = [real_results[i] for i in idxs]
        subh = [half_results[i] for i in idxs]
        hits = sum(1 for r in sub if r[0])
        half_hits = sum(subh)
        avg_bars = np.mean([r[2] for r in sub if r[0]]) if hits else float("nan")
        print(f"  {sublabel}: n={len(sub)}  FULL target {hits}/{len(sub)} ({100*hits/len(sub):.1f}%)  "
              f"HALF target {half_hits}/{len(sub)} ({100*half_hits/len(sub):.1f}%)  "
              f"avg {avg_bars:.1f} bars to hit")

    hits = sum(1 for r in real_results if r[0])
    half_hits = sum(half_results)
    avg_bars = np.mean([r[2] for r in real_results if r[0]]) if hits else float("nan")
    avg_frac_miss = np.mean([r[1] for r in real_results if not r[0]]) if (n_ - hits) else float("nan")
    print(f"\n  POOLED - FULL target: {hits}/{n_} hit ({100*hits/n_:.1f}%), avg {avg_bars:.1f} bars to hit when it did")
    print(f"  POOLED - HALF target (control): {half_hits}/{n_} hit ({100*half_hits/n_:.1f}%)")
    if n_ - hits > 0:
        print(f"  when the full target was NOT hit, price still travelled an average of "
              f"{100*avg_frac_miss:.0f}% of the measured distance before the test horizon ran out")

    # walk-forward: split by BREAKOUT bar time, chronological 70/30
    order = sorted(range(n_), key=lambda i: real_results[i][3])
    cutoff_rank = int(n_ * 0.7)
    is_idxs = order[:cutoff_rank]
    oos_idxs = order[cutoff_rank:]
    print("\n  WALK-FORWARD (chronological 70% IS / 30% OOS, by breakout bar):")
    report(is_idxs, "  IN-SAMPLE  ")
    report(oos_idxs, "  OUT-OF-SAMPLE")


if __name__ == "__main__":
    h4 = E.load_h4()
    run(h4, "H4 (real GOLD# export)")

    d1 = E.derive_d1_from_h4(h4)
    d1["time"] = pd.to_datetime(d1["date"])
    run(d1, "D1 (reconstructed from real GOLD# H4)")
