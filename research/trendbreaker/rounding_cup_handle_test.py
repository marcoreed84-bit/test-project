"""
Last new idea from the Kanu Jain deck: Rounding Bottom/Top (a "long-term
reversal pattern... best suited for weekly charts... a long consolidation
period that turns from a bearish to a bullish bias", i.e. a real U-shape,
not a swing-point shape like H&S or a straight-line construction like the
triangles/wedges/rectangle) and the Cup and Handle (the same rounding
shape, "the cup", followed by a shallower pullback "handle" before the
real breakout). Neither fits this session's usual alternating-swing
construction - a genuinely different detection method: a rolling
QUADRATIC FIT (least-squares parabola over a window), using real R^2 fit
quality as evidence of an actual rounding shape, not just "any 3 points".
Uses H4 data (the deck's own "best suited for weekly/longer charts" cue -
M15 is too short/noisy a bar for a pattern meant to span weeks).

CONSTRUCTION: slide a fixed-length window (stride 5 bars) over H4 closes;
fit y = a*x^2 + b*x + c; require R^2 >= R2_MIN and the right curvature sign
(a>0 = bottom/bullish, a<0 = top/bearish); require the window's own
extreme (min/max close) to sit roughly CENTERED (not at either edge) so a
straight trend can't masquerade as "rounding"; de-duplicate heavily
overlapping windows by non-max suppression on R^2 (keep the best-fitting
window in any overlapping cluster). RIM = the window's own starting price
(the level before the rounding move began). BREAKOUT = BREAK_CONFIRM_CLOSES
consecutive closes beyond the rim. TARGET = the classic measured-move rule
(rim-to-extreme height, projected from the breakout price) - same
convention as every other pattern this session.

CUP AND HANDLE: an entry filter on top of the rounding-bottom/top book -
only take the trade if, within HANDLE_MAX_BARS after the rounding
pattern's own end, price pulls back no more than HANDLE_MAX_RETRACE of the
cup's own depth for at least HANDLE_MIN_BARS (the handle), and the real
breakout is measured from there instead of straight off the rim.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)
STRIDE = 5
R2_MIN = 0.5
CENTER_TOL = 0.25   # extreme must sit within [CENTER_TOL, 1-CENTER_TOL] fraction of the window
MAX_HORIZON_CAP = 300
STOP_BUFFER = 1.0
HANDLE_MAX_BARS = 40
HANDLE_MIN_BARS = 3
HANDLE_MAX_RETRACE = 0.5


def find_rounding(c, atr, n, window, top):
    cands = []
    for end in range(window, n, STRIDE):
        start = end - window
        seg = c[start:end + 1]
        x = np.arange(len(seg), dtype=float)
        xn = x - x.mean()
        coeffs = np.polyfit(xn, seg, 2)
        fit = np.polyval(coeffs, xn)
        ss_res = np.sum((seg - fit) ** 2)
        ss_tot = np.sum((seg - seg.mean()) ** 2)
        if ss_tot <= 0:
            continue
        r2 = 1 - ss_res / ss_tot
        a = coeffs[0]
        shape_ok = (a < 0) if top else (a > 0)
        if not (shape_ok and r2 >= R2_MIN):
            continue
        extreme_i = int(np.argmax(seg)) if top else int(np.argmin(seg))
        frac = extreme_i / len(seg)
        if not (CENTER_TOL <= frac <= 1 - CENTER_TOL):
            continue
        cands.append(dict(start=start, end=end, extreme_i=start + extreme_i,
                           extreme_px=seg[extreme_i], rim=seg[0], r2=r2))

    cands.sort(key=lambda d: -d["r2"])
    accepted = []
    for cd in cands:
        overlap = any(not (cd["end"] < a["start"] or cd["start"] > a["end"]) for a in accepted)
        if not overlap:
            accepted.append(cd)
    accepted.sort(key=lambda d: d["end"])
    return accepted


def build_breakouts(cands, h, l, c, atr, n, top, require_handle):
    out = []
    for cd in cands:
        end, rim, extreme_px = cd["end"], cd["rim"], cd["extreme_px"]
        height = abs(rim - extreme_px)
        if height <= 0:
            continue
        search_start = end
        handle_ok = True
        if require_handle:
            handle_ok = False
            for h_end in range(end + HANDLE_MIN_BARS, min(end + HANDLE_MAX_BARS, n - 1)):
                seg = c[end:h_end + 1]
                retrace = (rim - seg.min()) if not top else (seg.max() - rim)
                if 0 < retrace <= HANDLE_MAX_RETRACE * height:
                    search_start = h_end
                    handle_ok = True
            if not handle_ok:
                continue

        horizon_end = min(n - 1, search_start + MAX_HORIZON_CAP)
        brk_q, run_ = -1, 0
        for q in range(search_start + 1, horizon_end):
            beyond = (rim - c[q]) if top else (c[q] - rim)
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
        atr_brk = atr[brk_q]
        stop = (extreme_px + STOP_BUFFER * atr_brk) if top else (extreme_px - STOP_BUFFER * atr_brk)
        if (top and stop <= brk_price) or ((not top) and stop >= brk_price):
            continue
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)
        out.append(dict(top=top, brk_q=brk_q, brk_price=brk_price, target=target, stop=stop,
                         max_horizon=max_horizon))
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
    h4 = E.load_h4()
    o = h4["open"].values; h = h4["high"].values; l = h4["low"].values; c = h4["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    n = len(c)
    print(f"H4 data: n={n} bars, {h4['time'].min()} -> {h4['time'].max()}")

    for window in (40, 60, 80):
        print("\n" + "=" * 95)
        print(f"WINDOW={window} bars (~{window*4/24:.1f} days)")
        print("=" * 95)
        for top, name in ((False, "rounding bottom"), (True, "rounding top")):
            cands = find_rounding(c, atr, n, window, top)
            b = build_breakouts(cands, h, l, c, atr, n, top, require_handle=False)
            res = eval_book(b, h, l, c)
            report(res, f"{name}: {len(cands)} candidates")

    print("\n" + "=" * 95)
    print("CUP AND HANDLE (window=60, handle filter on top of rounding bottom/top)")
    print("=" * 95)
    for top, name in ((False, "cup and handle (bullish)"), (True, "inverted cup and handle (bearish)")):
        cands = find_rounding(c, atr, n, 60, top)
        b_nohandle = build_breakouts(cands, h, l, c, atr, n, top, require_handle=False)
        b_handle = build_breakouts(cands, h, l, c, atr, n, top, require_handle=True)
        report(eval_book(b_nohandle, h, l, c), f"{name}: no handle required")
        report(eval_book(b_handle, h, l, c), f"{name}: handle required")
