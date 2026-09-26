"""
"Dig deeper before just building" (user, 2026-09-26) follow-up to
wolfe_wave_test.py's first H4-bullish result (which already had one real
lookahead bug fixed in that file directly - see its own CONFIRM_LAG note).
Two further robustness checks, same discipline as every other pattern
rejected/accepted this session (symmetrical triangle, HP filter,
gap-continuation, rectangle):

1. SPECIFICITY CONTROL: does the Wolfe Wave's own geometric ordering rules
   (wave 3 undercuts wave 1, wave 4 contained between 1-3, wave 5 makes a
   new extreme) actually add selectivity - or would the exact same entry/
   exit MECHANISM (break back above the 1-3 line, stop at wave 5, target
   at the 1-4 line) do just as well on ANY 5 consecutive alternating
   swings, Wolfe-shaped or not? If the unconstrained version matches or
   beats the constrained one, the "Wolfe Wave" label isn't doing any real
   work - whatever effect exists is generic, not pattern-specific.

2. PARAMETER-STRENGTH SENSITIVITY: PIVOT_STRENGTH=5 is this whole repo's
   shared default (inherited from the TrendBreaker indicator's own
   InpPivotStrength), never itself tuned per-pattern. Sweeping it here
   checks whether the H4 bullish Wolfe result is a genuine effect that
   holds across nearby fractal-strength choices, or a narrow, lucky peak
   at exactly the one value everyone happens to already use - the same
   "does it survive a parameter it wasn't picked for" test this session
   already applied to MA period pairs (HP filter) and stop-buffer widths
   (every accepted pattern).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
import wolfe_wave_test as W
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD
from hs_next_round_test import report

np.random.seed(42)


def find_any_shape(zIdx, zType, zPx):
    """Same 5-swing low-high-low-high-low windowing as find_candidates(),
    but with NONE of the Wolfe-specific price-ordering rules enforced -
    isolates whether those rules add real selectivity."""
    out = []
    for m in range(len(zIdx) - 4):
        seq = zType[m:m + 5]
        i1, i2, i3, i4, i5 = zIdx[m:m + 5]
        p1, p2, p3, p4, p5 = zPx[m:m + 5]
        if seq == [-1, 1, -1, 1, -1]:
            bull = True
        elif seq == [1, -1, 1, -1, 1]:
            bull = False
        else:
            continue
        line13_slope = (p3 - p1) / (i3 - i1) if i3 != i1 else 0.0
        line14_slope = (p4 - p1) / (i4 - i1) if i4 != i1 else 0.0

        def line13_at(q, i0=i1, s=line13_slope, p0=p1):
            return p0 + s * (q - i0)

        def line14_at(q, i0=i1, s=line14_slope, p0=p1):
            return p0 + s * (q - i0)

        out.append(dict(bull=bull, i1=i1, i2=i2, i3=i3, i4=i4, i5=i5,
                         p1=p1, p2=p2, p3=p3, p4=p4, p5=p5,
                         line13_at=line13_at, line14_at=line14_at,
                         time_ratio=np.nan, amp_ratio=np.nan))
    return out


if __name__ == "__main__":
    h4 = E.load_h4()
    o = h4["open"].values; h = h4["high"].values; l = h4["low"].values; c = h4["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)

    print("=" * 92)
    print("CHECK 1: does the Wolfe-specific ordering add selectivity over an unconstrained")
    print("5-swing shape using the exact same entry/exit mechanism?")
    print("=" * 92)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    wolfe_cands = [p for p in W.find_candidates(zIdx, zType, zPx, require_fib=False) if p["bull"]]
    any_cands = [p for p in find_any_shape(zIdx, zType, zPx) if p["bull"]]
    print(f"  Wolfe-constrained bullish shapes: {len(wolfe_cands)}   "
          f"ANY-shape (unconstrained) bullish shapes: {len(any_cands)}")
    for sb in (0.5, 1.0, 1.5, 2.0):
        W.STOP_BUFFER = sb
        res_w = W.eval_book(W.build_trades(wolfe_cands, h, l, c, atr, n), h, l, c)
        res_a = W.eval_book(W.build_trades(any_cands, h, l, c, atr, n), h, l, c)
        report(res_w, f"  Wolfe-constrained, stop={sb}xATR")
        report(res_a, f"  ANY-shape control, stop={sb}xATR")

    print("\n" + "=" * 92)
    print("CHECK 2: PIVOT_STRENGTH sensitivity (Wolfe-constrained, bullish, stop=1.0xATR fixed)")
    print("=" * 92)
    W.STOP_BUFFER = 1.0
    for N in (3, 4, 5, 6, 7, 8, 10):
        zIdx_n, zType_n, zPx_n = find_swings(o, h, l, c, atr, body=False, N=N)
        cands_n = [p for p in W.find_candidates(zIdx_n, zType_n, zPx_n, require_fib=False) if p["bull"]]
        W.CONFIRM_LAG = N + 1
        res_n = W.eval_book(W.build_trades(cands_n, h, l, c, atr, n), h, l, c)
        report(res_n, f"  PIVOT_STRENGTH={N} ({len(cands_n)} raw shapes)")

    print("\nVERDICT: printed above - see chat for interpretation.")

# ============================================================================
# FINAL VERDICT (Opus review, 2026-09-26, after the two checks above):
# REJECTED. Confirmed CONFIRM_LAG is correct (off-by-one in the safe
# direction) and found one more real issue of the same class: find_swings()
# can replace wave 5 with a later, deeper low before the pattern's own
# BREAK_CONFIRM_CLOSES trigger fires - a live EA would have traded the
# earlier (overtaken) version too. A causal swing tracker that trades every
# version as soon as it's knowable didn't change the PF much (Wolfe
# 1.46-1.56, ANY-shape 1.28-1.36 in points), so this specific issue wasn't
# the deciding one - but three things WERE:
#   1. sma_atr(h, l, o, ...) still has the open-vs-close bug documented in
#      touch_reaction_corrected.py. Fixing it drops Wolfe's risk-normalized
#      PF (0.5xATR stop) from 1.02 to 0.96 and IS-R ranges 0.67-1.45 across
#      settings - unstable.
#   2. GOLD ran from ~$270 to ~$4000 over this dataset, so a POINTS-based PF
#      weights recent trades ~10x+ more than old ones. Measured as % of
#      entry price instead, Wolfe's own in-sample PF is only 1.09-1.33, and
#      the 70/30 IS/OOS split lands around 2021 - so "OOS beats IS" mostly
#      just means the 2021-26 rally carried it, not that the edge is robust.
#   3. THE DECIDING CHECK: taking each taken trade's own stop/target
#      distances (as % of price) and firing them at 300 sets of RANDOM H4
#      bars, long-only, same brackets - produced a median PF of 1.29-1.46
#      (5-95% range ~0.9-2.0). Both Wolfe (%PF 1.48-1.52) and the ANY-shape
#      control (%PF 1.43-1.66) land INSIDE that random-timing band. Neither
#      beats "be long GOLD with this bracket, entered whenever."
#
# Lesson carried forward for every future long-only-GOLD pattern test in
# this repo: report PF in R (risk units) or % of price, not raw points, and
# run this same random-entry/same-bracket baseline BEFORE calling anything
# promising. A points-based PF on a 25-year GOLD dataset will flatter almost
# any long-biased idea just from the underlying trend.
# ============================================================================
