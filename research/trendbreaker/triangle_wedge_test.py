"""
User: "continue testing the triangles and wedges next" - Murphy's
Continuation Patterns ch.7: Symmetrical/Ascending/Descending Triangle and
the Wedge Formation. Genuinely new construction (two CONVERGING trendlines,
not TrendBreaker's single validated line and not H&S's fixed-shape swing
match). Same real building blocks as everything else this session: the
same find_swings() pivot detection (PIVOT_STRENGTH=5, SWING_MIN_ATR=1.0),
same BREAK_TOL_ATR/BREAK_CONFIRM_CLOSES breakout confirmation convention,
same stop_buffer=1.0xATR default, same single-position-sequenced,
walk()/pnl_of()/report() simulation from hs_next_round_test.py.

CONSTRUCTION: take 4 CONSECUTIVE alternating swings (H1-L1-H2-L2 or
L1-H1-L2-H2, exactly like double_triple_top_test.py's double-pattern
window) - 2 highs define the upper line, 2 lows define the lower line.
Require genuine convergence: the gap between the two lines must be
NARROWER at the pattern's end than at its start, and must NOT have already
crossed (apex still ahead) - otherwise it's not a real triangle/wedge, just
two random lines.

CLASSIFICATION (flat tolerance = FLAT_SLOPE_ATR per bar):
  - ASCENDING triangle: upper line flat, lower line rising
  - DESCENDING triangle: lower line flat, upper line falling
  - SYMMETRICAL triangle: upper falling, lower rising (both converge inward)
  - RISING wedge: both lines rising, upper rising slower (gap still narrows)
  - FALLING wedge: both lines falling, upper falling faster (gap narrows)

BREAKOUT: unlike H&S (direction fixed by pattern shape), a triangle/wedge
can break EITHER way - tested honestly, not assumed "ascending breaks up".
Scan forward from the pattern's last swing for BREAK_CONFIRM_CLOSES closes
beyond either line by BREAK_TOL_ATR*ATR. TARGET = the pattern's own base
height (the gap at its widest/starting point - the classic measured-move
rule) projected from the breakout price in the breakout's own direction.
STOP = the opposite line's value at breakout, buffered 1.0xATR further away.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)

FLAT_SLOPE_ATR = 0.02     # per-bar slope <= this * ATR counts as "flat"
MAX_HORIZON_MULT = 4.0
MAX_HORIZON_CAP = 400
STOP_BUFFER = 1.0


def find_candidates(zIdx, zType, zPx, atr):
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
        gap_start = hi_at(i_start) - lo_at(i_start)
        gap_end = hi_at(i_end) - lo_at(i_end)
        if gap_start <= 0 or gap_end <= 0 or gap_end >= gap_start:
            continue   # not converging, or already crossed

        atr_ref = atr[i_end]
        flat = FLAT_SLOPE_ATR * atr_ref
        if abs(slope_hi) <= flat and slope_lo > flat:
            kind = "ascending"
        elif abs(slope_lo) <= flat and slope_hi < -flat:
            kind = "descending"
        elif slope_hi < -flat and slope_lo > flat:
            kind = "symmetrical"
        elif slope_hi > flat and slope_lo > flat:
            kind = "rising_wedge"
        elif slope_hi < -flat and slope_lo < -flat:
            kind = "falling_wedge"
        else:
            continue

        out.append(dict(kind=kind, i_start=i_start, i_end=i_end, hi_at=hi_at, lo_at=lo_at,
                         base_height=gap_start))
    return out


def build_breakouts(df):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    cands = find_candidates(zIdx, zType, zPx, atr)

    out = []
    for p in cands:
        i_end = p["i_end"]
        pattern_len = i_end - p["i_start"]
        horizon_end = min(n - 1, i_end + int(min(pattern_len * MAX_HORIZON_MULT, MAX_HORIZON_CAP)))

        brk_q, brk_dir, run_up, run_dn = -1, None, 0, 0
        for q in range(i_end + 1, horizon_end):
            hv, lv = p["hi_at"](q), p["lo_at"](q)
            if hv <= lv:
                break   # apex reached / lines crossed - pattern no longer meaningful
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

        top = (brk_dir == "down")   # "top"-style (short) convention matching walk()/pnl_of()
        brk_price = c[brk_q]
        target = (brk_price - p["base_height"]) if top else (brk_price + p["base_height"])
        other_line = p["lo_at"](brk_q) if brk_dir == "up" else p["hi_at"](brk_q)
        atr_brk = atr[brk_q]
        stop = (other_line - STOP_BUFFER * atr_brk) if brk_dir == "up" else (other_line + STOP_BUFFER * atr_brk)
        if (top and stop <= brk_price) or ((not top) and stop >= brk_price):
            continue
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(kind=p["kind"], top=top, brk_q=brk_q, brk_price=brk_price, target=target,
                         stop=stop, max_horizon=max_horizon))
    return out, h, l, c


def eval_book(breakouts, h, l, c):
    breakouts = sorted(breakouts, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in breakouts:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk(h, l, b["top"], b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pnl = pnl_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, b["top"])
        results.append(dict(brk_q=b["brk_q"], outcome=outcome, pnl=pnl, kind=b["kind"], top=b["top"]))
        last_exit = exit_bar
    return results


def build_breakouts_from_cands(cands, h, l, c, atr, stop_buffer):
    """Same construction as build_breakouts()'s inner loop, factored out so
    the stop-buffer sensitivity sweep below doesn't have to re-detect
    candidates (find_swings/find_candidates) for every stop width."""
    n = len(c)
    out = []
    for p in cands:
        i_end = p["i_end"]
        pattern_len = i_end - p["i_start"]
        horizon_end = min(n - 1, i_end + int(min(pattern_len * MAX_HORIZON_MULT, MAX_HORIZON_CAP)))
        brk_q, brk_dir, run_up, run_dn = -1, None, 0, 0
        for q in range(i_end + 1, horizon_end):
            hv, lv = p["hi_at"](q), p["lo_at"](q)
            if hv <= lv:
                break
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
        stop = (other_line - stop_buffer * atr_brk) if brk_dir == "up" else (other_line + stop_buffer * atr_brk)
        if (top and stop <= brk_price) or ((not top) and stop >= brk_price):
            continue
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(kind=p["kind"], top=top, brk_q=brk_q, brk_price=brk_price, target=target,
                         stop=stop, max_horizon=max_horizon))
    return out


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    all_b, h, l, c = build_breakouts(df15)
    print(f"M15 data: n={len(df15)} bars")
    print(f"Total triangle/wedge breakouts found (all kinds, before sequencing): {len(all_b)}")
    for kind in ("ascending", "descending", "symmetrical", "rising_wedge", "falling_wedge"):
        print(f"  {kind}: {sum(1 for b in all_b if b['kind'] == kind)} raw candidates that broke out")

    print("\n" + "=" * 95)
    print("ALL KINDS COMBINED, ONE BOOK (single-position-sequenced)")
    print("=" * 95)
    res_all = eval_book(all_b, h, l, c)
    report(res_all, "all triangle/wedge types combined")
    up = [r for r in res_all if not r["top"]]
    dn = [r for r in res_all if r["top"]]
    report(up, "  -> breakouts UP only (post-sequencing subset)")
    report(dn, "  -> breakouts DOWN only (post-sequencing subset)")

    print("\n" + "=" * 95)
    print("EACH PATTERN TYPE IN ITS OWN BOOK (apples-to-apples, same lesson as double/triple tops)")
    print("=" * 95)
    for kind in ("ascending", "descending", "symmetrical", "rising_wedge", "falling_wedge"):
        own = [b for b in all_b if b["kind"] == kind]
        res = eval_book(own, h, l, c)
        report(res, f"{kind} triangle/wedge, own book")

    # Only ascending/symmetrical looked non-negative above - checking
    # whether that survives a stop-buffer sweep (same robustness check as
    # every other real finding this session) rather than trusting one
    # stop width's result.
    print("\n" + "=" * 95)
    print("STOP-BUFFER SENSITIVITY (ascending/symmetrical only - the two non-negative types above)")
    print("=" * 95)
    o = df15["open"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    cands = find_candidates(zIdx, zType, zPx, atr)
    for kind in ("ascending", "symmetrical"):
        sub_cands = [p for p in cands if p["kind"] == kind]
        for sb in (0.5, 0.75, 1.0, 1.5, 2.0):
            b = build_breakouts_from_cands(sub_cands, h, l, c, atr, sb)
            res = eval_book(b, h, l, c)
            report(res, f"{kind} stop_buffer={sb}xATR")
