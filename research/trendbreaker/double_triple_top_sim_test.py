"""
Follow-up to double_triple_top_test.py's real, strong measured-move hit
rates (double top/bottom 78.5%/85.1%, triple 83.2%/89.3% - all beating
H&S's own 75%/69%/75% from head_shoulders_target_test.py). That first test
only asked "does price reach the level", with no stop-loss, no entry cost,
and multiple overlapping patterns counted independently - exactly the gap
H&S had before hs_next_round_test.py built a real tradeable simulation.
Same fix here: single-position-sequenced (last_exit_bar gating, chronological
across double+triple, top+bottom combined - one book, like a real EA would
run), real stop beyond the pattern extrema, reusing the already-audited
walk()/pnl_of() from hs_next_round_test.py (same stop_buffer=1.0xATR
convention validated for H&S, so results are comparable apples-to-apples).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_CONFIRM_CLOSES
from hs_next_round_test import walk, pnl_of, report
from double_triple_top_test import find_double, find_triple, TOL_ATR, BREAK_TOL_ATR, \
    MAX_HORIZON_MULT, MAX_HORIZON_CAP

np.random.seed(42)
STOP_BUFFER = 1.0   # same validated real finding used everywhere else in this session


def build_breakouts(df, kind, top):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    pats = find_double(zIdx, zType, zPx, top) if kind == "double" else find_triple(zIdx, zType, zPx, top)

    out = []
    for p in pats:
        if kind == "double":
            extrema = [p["p_e1"], p["p_e2"]]
            i_last_extreme = p["i_e2"]
            i_neck_pts = [p["i_neck"]]
            p_neck_pts = [p["p_neck"]]
            i_start = p["i_e1"]
        else:
            extrema = [p["p_e1"], p["p_e2"], p["p_e3"]]
            i_last_extreme = p["i_e3"]
            i_neck_pts = [p["i_n1"], p["i_n2"]]
            p_neck_pts = [p["p_n1"], p["p_n2"]]
            i_start = p["i_e1"]

        if max(extrema) - min(extrema) > TOL_ATR * atr[i_last_extreme]:
            continue

        ia, ib = i_neck_pts[0], i_neck_pts[-1]
        neck_slope = (p_neck_pts[-1] - p_neck_pts[0]) / (ib - ia) if ib != ia else 0.0

        def neckline_at(q, ia=ia, neck_slope=neck_slope, p0=p_neck_pts[0]):
            return p0 + neck_slope * (q - ia)

        avg_extreme = float(np.mean(extrema))
        height = abs(avg_extreme - neckline_at(i_last_extreme))
        if height <= 0:
            continue

        pattern_len = i_last_extreme - i_start
        horizon_end = min(n - 1, i_last_extreme + int(min(pattern_len * MAX_HORIZON_MULT, MAX_HORIZON_CAP)))

        brk_q, run_ = -1, 0
        for q in range(i_last_extreme + 1, horizon_end):
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
        target = (brk_price - height) if top else (brk_price + height)
        shoulder_ext = max(extrema) if top else min(extrema)
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(top=top, kind=kind, brk_q=brk_q, brk_price=brk_price, target=target,
                         shoulder_ext=shoulder_ext, atr_at_brk=atr[brk_q], max_horizon=max_horizon))
    return out, h, l, c


def eval_combined(breakouts, h, l, c, stop_buffer=STOP_BUFFER):
    breakouts = sorted(breakouts, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in breakouts:
        top, brk_q, entry, target = b["top"], b["brk_q"], b["brk_price"], b["target"]
        if brk_q < last_exit:
            continue
        stop = (b["shoulder_ext"] + stop_buffer * b["atr_at_brk"]) if top else \
               (b["shoulder_ext"] - stop_buffer * b["atr_at_brk"])
        if (top and stop <= entry) or ((not top) and stop >= entry):
            continue
        outcome, exit_bar = walk(h, l, top, brk_q, b["max_horizon"], stop, target)
        pnl = pnl_of(outcome, entry, stop, target, c, exit_bar, top)
        results.append(dict(brk_q=brk_q, outcome=outcome, pnl=pnl, kind=b["kind"], top=top))
        last_exit = exit_bar
    return results


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)

    all_breakouts, h, l, c = [], None, None, None
    for kind in ("double", "triple"):
        for top in (True, False):
            b, h, l, c = build_breakouts(df15, kind, top)
            all_breakouts += b

    print(f"M15 data: n={len(df15)} bars")
    print(f"Total breakouts before single-position sequencing: {len(all_breakouts)}")

    print("\n" + "=" * 95)
    print("SINGLE-POSITION-SEQUENCED (double+triple, top+bottom combined into one book), stop_buffer=1.0xATR")
    print("=" * 95)
    res = eval_combined(all_breakouts, h, l, c)
    report(res, "double+triple tops/bottoms, market entry")

    for kind in ("double", "triple"):
        sub = [r for r in res if r["kind"] == kind]
        report(sub, f"  -> {kind} only (post-sequencing subset)")
    for top, name in ((True, "top/bearish"), (False, "bottom/bullish")):
        sub = [r for r in res if r["top"] == top]
        report(sub, f"  -> {name} only (post-sequencing subset)")

    print("\n" + "=" * 95)
    print("STOP-BUFFER SWEEP (same convention as hs_stop_loss_test.py)")
    print("=" * 95)
    for sb in (0.5, 0.75, 1.0, 1.5, 2.0):
        res_sb = eval_combined(all_breakouts, h, l, c, stop_buffer=sb)
        report(res_sb, f"stop_buffer={sb}xATR")

    # The "post-sequencing subset" breakdown above is NOT a clean read on
    # each pattern type's own edge - sharing one book means whichever type
    # fires FIRST wins the single position slot, so the subset that
    # actually got to trade is a filtered, non-random sample of each type
    # (contaminated by cross-pattern-type competition), not that type's
    # true standalone performance. Re-running each type in ITS OWN book
    # (as if it were the only pattern an EA traded) is the honest,
    # apples-to-apples comparison against H&S's own single-pattern book.
    print("\n" + "=" * 95)
    print("EACH PATTERN TYPE IN ITS OWN BOOK (not sharing a position slot with the other type)")
    print("=" * 95)
    for kind in ("double", "triple"):
        own_book, h2, l2, c2 = [], None, None, None
        for top in (True, False):
            b, h2, l2, c2 = build_breakouts(df15, kind, top)
            own_book += b
        for sb in (0.5, 1.0, 1.5, 2.0):
            res_own = eval_combined(own_book, h2, l2, c2, stop_buffer=sb)
            report(res_own, f"{kind}-only own book, stop_buffer={sb}xATR")
