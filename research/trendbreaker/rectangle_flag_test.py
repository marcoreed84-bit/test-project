"""
Last two continuation patterns from Murphy's ch.7 not yet tested (after
triangles/wedges, both weak/rejected): the RECTANGLE (two flat, roughly
PARALLEL boundaries - unlike a triangle, they don't have to converge) and
the FLAG/PENNANT (a sharp "flagpole" move, then a brief tight consolidation,
then continuation in the flagpole's OWN direction - the classic measured-
move rule literally named after this pattern). Same real building blocks:
find_swings() pivot detection, BREAK_TOL_ATR/BREAK_CONFIRM_CLOSES breakout
confirmation, stop_buffer=1.0xATR, single-position-sequenced walk()/
pnl_of()/report() from hs_next_round_test.py.

RECTANGLE: reuses triangle_wedge_test.py's 4-consecutive-swing window
(H1-L1-H2-L2 or L1-H1-L2-H2) but classifies as a rectangle when BOTH
boundaries are flat (no convergence requirement - a rectangle's gap doesn't
have to narrow, just stay roughly horizontal). Breakout direction tested
honestly (either way), target = the rectangle's own height.

FLAG/PENNANT: POLE_BARS-bar lookback move >= POLE_MIN_ATR x ATR defines the
flagpole and its direction; the following CONS_BARS bars must consolidate
tightly (total range <= CONS_MAX_ATR x ATR) - the classic real-world flag/
pennant shape distinction (parallel channel vs small triangle) is NOT
separated out here, both count as "consolidation", a real simplification
disclosed rather than hidden. Breakout is tested BOTH ways (continuation in
the flagpole's own direction, per the textbook claim, AND the opposite, as
an honest control) rather than assuming continuation. Target = the
flagpole's own height (the classic measured-move rule this pattern is named
for), projected from the breakout price.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)
FLAT_SLOPE_ATR = 0.02
MAX_HORIZON_MULT = 4.0
MAX_HORIZON_CAP = 400
STOP_BUFFER = 1.0


# ------------------------------------------------------------- RECTANGLE
def find_rectangles(zIdx, zType, zPx, atr):
    out = []
    for m in range(len(zIdx) - 3):
        seq = zType[m:m + 4]
        if seq == [1, -1, 1, -1]:
            i_h1, p_h1, i_l1, p_l1, i_h2, p_h2, i_l2, p_l2 = (
                zIdx[m], zPx[m], zIdx[m + 1], zPx[m + 1], zIdx[m + 2], zPx[m + 2], zIdx[m + 3], zPx[m + 3])
        elif seq == [-1, 1, -1, 1]:
            i_l1, p_l1, i_h1, p_h1, i_l2, p_l2, i_h2, p_h2 = (
                zIdx[m], zPx[m], zIdx[m + 1], zPx[m + 1], zIdx[m + 2], zPx[m + 2], zIdx[m + 3], zPx[m + 3])
        else:
            continue

        slope_hi = (p_h2 - p_h1) / (i_h2 - i_h1) if i_h2 != i_h1 else 0.0
        slope_lo = (p_l2 - p_l1) / (i_l2 - i_l1) if i_l2 != i_l1 else 0.0

        def hi_at(q, i0=i_h1, s=slope_hi, p0=p_h1):
            return p0 + s * (q - i0)

        def lo_at(q, i0=i_l1, s=slope_lo, p0=p_l1):
            return p0 + s * (q - i0)

        i_start = min(i_h1, i_l1)
        i_end = max(i_h2, i_l2)
        if i_end <= i_start:
            continue
        gap = hi_at(i_end) - lo_at(i_end)
        if gap <= 0:
            continue

        atr_ref = atr[i_end]
        flat = FLAT_SLOPE_ATR * atr_ref
        if abs(slope_hi) <= flat and abs(slope_lo) <= flat:
            out.append(dict(kind="rectangle", i_start=i_start, i_end=i_end, hi_at=hi_at, lo_at=lo_at,
                             base_height=gap))
    return out


# ------------------------------------------------------------- FLAG/PENNANT
POLE_BARS = 20
POLE_MIN_ATR = 3.0
CONS_BARS_MIN, CONS_BARS_MAX = 5, 30
CONS_MAX_ATR = 2.0


def find_flags(h, l, c, atr, n):
    out = []
    i = POLE_BARS
    last_pole_end = -1
    while i < n - CONS_BARS_MAX - 1:
        if i <= last_pole_end:
            i += 1
            continue
        pole_move = c[i] - c[i - POLE_BARS]
        if abs(pole_move) < POLE_MIN_ATR * atr[i]:
            i += 1
            continue
        pole_up = pole_move > 0
        pole_height = abs(pole_move)

        found = False
        for cons_len in range(CONS_BARS_MIN, CONS_BARS_MAX + 1):
            j0, j1 = i + 1, i + cons_len
            if j1 >= n:
                break
            seg_h = h[j0:j1 + 1].max()
            seg_l = l[j0:j1 + 1].min()
            if (seg_h - seg_l) <= CONS_MAX_ATR * atr[j1]:
                out.append(dict(i_pole_start=i - POLE_BARS, i_end=j1, pole_up=pole_up,
                                 pole_height=pole_height, cons_hi=seg_h, cons_lo=seg_l))
                last_pole_end = j1
                i = j1 + 1
                found = True
                break
        if not found:
            i += 1
    return out


def build_flag_breakouts(flags, h, l, c, atr, n, continuation_only):
    out = []
    for f in flags:
        i_end = f["i_end"]
        horizon_end = min(n - 1, i_end + MAX_HORIZON_CAP)
        cons_hi, cons_lo = f["cons_hi"], f["cons_lo"]

        brk_q, brk_dir, run_up, run_dn = -1, None, 0, 0
        for q in range(i_end + 1, horizon_end):
            if c[q] - cons_hi > BREAK_TOL_ATR * atr[q]:
                run_up += 1; run_dn = 0
            elif cons_lo - c[q] > BREAK_TOL_ATR * atr[q]:
                run_dn += 1; run_up = 0
            else:
                run_up = run_dn = 0
            if run_up >= BREAK_CONFIRM_CLOSES:
                brk_q, brk_dir = q, "up"; break
            if run_dn >= BREAK_CONFIRM_CLOSES:
                brk_q, brk_dir = q, "down"; break
        if brk_q < 0:
            continue
        cont = (brk_dir == "up") == f["pole_up"]
        if continuation_only and not cont:
            continue
        top = (brk_dir == "down")
        brk_price = c[brk_q]
        target = (brk_price - f["pole_height"]) if top else (brk_price + f["pole_height"])
        other_line = cons_lo if brk_dir == "up" else cons_hi
        atr_brk = atr[brk_q]
        stop = (other_line - STOP_BUFFER * atr_brk) if brk_dir == "up" else (other_line + STOP_BUFFER * atr_brk)
        if (top and stop <= brk_price) or ((not top) and stop >= brk_price):
            continue
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(top=top, brk_q=brk_q, brk_price=brk_price, target=target, stop=stop,
                         max_horizon=max_horizon, cont=cont))
    return out


def eval_book(breakouts, h, l, c):
    breakouts = sorted(breakouts, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in breakouts:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk(h, l, b["top"], b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pnl = pnl_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, b["top"])
        results.append(dict(brk_q=b["brk_q"], outcome=outcome, pnl=pnl))
        last_exit = exit_bar
    return results


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    o = df15["open"].values; h = df15["high"].values; l = df15["low"].values; c = df15["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)

    print("=" * 95)
    print("RECTANGLE")
    print("=" * 95)
    rects = find_rectangles(zIdx, zType, zPx, atr)
    print(f"Raw rectangle candidates: {len(rects)}")

    def build_generic_breakouts(cands, h, l, c, atr, n):
        out = []
        for p in cands:
            i_end = p["i_end"]
            horizon_end = min(n - 1, i_end + MAX_HORIZON_CAP)
            brk_q, brk_dir, run_up, run_dn = -1, None, 0, 0
            for q in range(i_end + 1, horizon_end):
                hv, lv = p["hi_at"](q), p["lo_at"](q)
                if c[q] - hv > BREAK_TOL_ATR * atr[q]:
                    run_up += 1; run_dn = 0
                elif lv - c[q] > BREAK_TOL_ATR * atr[q]:
                    run_dn += 1; run_up = 0
                else:
                    run_up = run_dn = 0
                if run_up >= BREAK_CONFIRM_CLOSES:
                    brk_q, brk_dir = q, "up"; break
                if run_dn >= BREAK_CONFIRM_CLOSES:
                    brk_q, brk_dir = q, "down"; break
            if brk_q < 0:
                continue
            top = (brk_dir == "down")
            brk_price = c[brk_q]
            target = (brk_price - p["base_height"]) if top else (brk_price + p["base_height"])
            other_line = p["lo_at"](brk_q) if brk_dir == "up" else p["hi_at"](brk_q)
            atr_brk = atr[brk_q]
            stop = (other_line - STOP_BUFFER * atr_brk) if brk_dir == "up" else (other_line + STOP_BUFFER * atr_brk)
            if (top and stop <= brk_price) or ((not top) and stop >= brk_price):
                continue
            max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
            out.append(dict(top=top, brk_q=brk_q, brk_price=brk_price, target=target, stop=stop,
                             max_horizon=max_horizon))
        return out

    rect_breakouts = build_generic_breakouts(rects, h, l, c, atr, n)
    res = eval_book(rect_breakouts, h, l, c)
    report(res, "rectangle, own book")

    print("\n" + "=" * 95)
    print("FLAG / PENNANT")
    print("=" * 95)
    flags = find_flags(h, l, c, atr, n)
    print(f"Raw flag/pennant candidates (pole + tight consolidation): {len(flags)}")

    cont_breakouts = build_flag_breakouts(flags, h, l, c, atr, n, continuation_only=False)
    n_cont = sum(1 for b in cont_breakouts if b["cont"])
    n_rev = len(cont_breakouts) - n_cont
    print(f"Breakouts found: {len(cont_breakouts)} ({n_cont} continuation, {n_rev} reversal)")

    res_cont = eval_book([b for b in cont_breakouts if b["cont"]], h, l, c)
    report(res_cont, "flag/pennant CONTINUATION (breaks same way as the pole - the textbook claim)")

    res_rev = eval_book([b for b in cont_breakouts if not b["cont"]], h, l, c)
    report(res_rev, "flag/pennant REVERSAL (breaks opposite the pole - honest control)")

    res_all = eval_book(cont_breakouts, h, l, c)
    report(res_all, "flag/pennant ALL breakouts combined, own book")
