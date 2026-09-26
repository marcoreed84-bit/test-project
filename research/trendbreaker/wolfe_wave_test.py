"""
Wolfe Wave (Bill Wolfe) - user asked to "search the web for the wolfe wave
pattern (five-point geometric chart pattern)" (2026-09-26) and test it.
Real construction rules pulled from web search (fxopen.com, howtotrade.com
via search snippets - direct WebFetch was blocked by the egress proxy for
most trading-blog domains, so rules are cross-checked across multiple
independent search results rather than one source):

BULLISH (reversal to the upside, mirrored for bearish):
  5 alternating swings in time order: 1=low, 2=high, 3=low, 4=high, 5=low.
  - Wave 3 undercuts wave 1 (p3 < p1) - real lower low.
  - Wave 4 stays contained: p1 < p4 < p2 (rallies above both prior lows,
    but not as high as wave 2 - the classic "channel containment" rule).
  - Wave 5 makes the pattern's own lowest low (p5 < p3) - the "overshoot"
    or "throw-under": price is expected to PIERCE the 1-3 trendline
    (extended forward through wave 5's own bar) before reversing.
  - EPA ("Estimated Price at Arrival") line = the 1-4 line, extended
    forward - the classic Wolfe profit target once price reverses off
    wave 5.
  BEARISH is the exact mirror (1=high,2=low,3=high>1,4=low with
  p2<p4<p1... i.e. contained between waves 1 and 2, 5=high>3).

SIMPLIFICATIONS DISCLOSED UP FRONT (same discipline as every other
document-sourced pattern this session - core testable geometry kept,
decorative/unverifiable extras dropped rather than silently assumed):
  - The Fibonacci "waves 3/5 = 127%/162% extension" refinement some
    sources add is NOT enforced - it would only shrink an already-small
    sample further, and no source agreed on it being a hard rule vs. a
    common observation. Tested as a stricter variant separately below to
    see if it's actually selective for anything.
  - Time symmetry between wave1-2 and wave3-4 ("should occur at roughly
    consistent intervals" per multiple sources) is measured and reported,
    not enforced as a hard filter, for the same reason.
  - The EPA/1-4 target line is a genuinely MOVING target (it keeps rising
    with time). This repo's walk()/pnl_of() simulation assumes a FIXED
    target for the life of the trade, like every other pattern tested
    here - so the target used is the 1-4 line's value AT THE ENTRY BAR,
    a static snapshot, not the true moving EPA line. This likely
    UNDERSTATES the pattern's real target if price takes a while to get
    there (the real EPA line would have risen further by then) - a
    conservative simplification, not an optimistic one.
  - ENTRY: unlike the pure pattern definition (enter as soon as wave 5
    forms), a real trade needs SOME confirmation that the reversal is
    actually happening, not just called by an idealized 5th point that
    could still be a 6th leg lower in progress. Same BREAK_TOL_ATR/
    BREAK_CONFIRM_CLOSES convention as every other pattern in this
    session: enter once price closes back above (bullish) / below
    (bearish) the 1-3 trendline (extended) by BREAK_TOL_ATR*ATR for
    BREAK_CONFIRM_CLOSES consecutive closes.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_TOL_ATR, BREAK_CONFIRM_CLOSES
from hs_next_round_test import walk, pnl_of, report

np.random.seed(42)

MAX_HORIZON_CAP = 400
STOP_BUFFER = 1.0
CONFIRM_WINDOW = 60   # bars allowed to wait for the reversal-confirm after wave 5


def find_candidates(zIdx, zType, zPx, require_fib=False):
    """5-swing windows matching the Wolfe Wave shape. bull=True: low-high-
    low-high-low (1..5). bull=False: mirrored high-low-high-low-high."""
    out = []
    for m in range(len(zIdx) - 4):
        seq = zType[m:m + 5]
        i1, i2, i3, i4, i5 = zIdx[m:m + 5]
        p1, p2, p3, p4, p5 = zPx[m:m + 5]

        if seq == [-1, 1, -1, 1, -1]:
            bull = True
            ok = (p3 < p1) and (p1 < p4 < p2) and (p5 < p3)
        elif seq == [1, -1, 1, -1, 1]:
            bull = False
            ok = (p3 > p1) and (p2 < p4 < p1) and (p5 > p3)
        else:
            continue
        if not ok:
            continue

        w12 = abs(p2 - p1); w34 = abs(p4 - p3)
        t12 = i2 - i1; t34 = i4 - i3
        if require_fib:
            ext3 = abs(p3 - p2) / w12 if w12 > 0 else 0.0
            ext5 = abs(p5 - p4) / w34 if w34 > 0 else 0.0
            # loose bands around the commonly-cited 127%/162% extensions
            if not (1.0 <= ext3 <= 2.0 and 1.2 <= ext5 <= 2.2):
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
                         time_ratio=(t34 / t12) if t12 > 0 else np.nan,
                         amp_ratio=(w34 / w12) if w12 > 0 else np.nan))
    return out


def build_trades(cands, h, l, c, atr, n):
    out = []
    for p in cands:
        i5 = p["i5"]
        horizon_end = min(n - 1, i5 + CONFIRM_WINDOW)
        entry_q, run_ = -1, 0
        for q in range(i5 + 1, horizon_end):
            lv = p["line13_at"](q)
            beyond = (c[q] - lv) if p["bull"] else (lv - c[q])
            if beyond > BREAK_TOL_ATR * atr[q]:
                run_ += 1
                if run_ >= BREAK_CONFIRM_CLOSES:
                    entry_q = q
                    break
            else:
                run_ = 0
        if entry_q < 0:
            continue

        entry_price = c[entry_q]
        target = p["line14_at"](entry_q)
        atr_e = atr[entry_q]
        stop = (p["p5"] - STOP_BUFFER * atr_e) if p["bull"] else (p["p5"] + STOP_BUFFER * atr_e)
        top = not p["bull"]   # top=True => short, matching walk()/pnl_of() convention
        if top:
            if not (target < entry_price < stop):
                continue
        else:
            if not (stop < entry_price < target):
                continue
        max_horizon = min(n - 1, entry_q + MAX_HORIZON_CAP)
        out.append(dict(top=top, brk_q=entry_q, brk_price=entry_price, target=target,
                         stop=stop, max_horizon=max_horizon,
                         time_ratio=p["time_ratio"], amp_ratio=p["amp_ratio"]))
    return out


def eval_book(trades, h, l, c):
    trades = sorted(trades, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in trades:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk(h, l, b["top"], b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pnl = pnl_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, b["top"])
        results.append(dict(brk_q=b["brk_q"], outcome=outcome, pnl=pnl, top=b["top"]))
        last_exit = exit_bar
    return results


def run(name, df):
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    print("\n" + "=" * 95)
    print(f"{name}: n={n} bars, {years:.2f} yrs, swings={len(zIdx)}")
    print("=" * 95)

    cands = find_candidates(zIdx, zType, zPx, require_fib=False)
    bull = [p for p in cands if p["bull"]]
    bear = [p for p in cands if not p["bull"]]
    print(f"  raw 5-point Wolfe shapes found: {len(cands)}  (bullish={len(bull)}, bearish={len(bear)})  "
          f"({len(cands)/years:.1f}/yr)")

    trades = build_trades(cands, h, l, c, atr, n)
    res = eval_book(trades, h, l, c)
    report(res, "all Wolfe waves combined (bull+bear, single book)")
    report([r for r in res if not r["top"]], "  bullish only")
    report([r for r in res if r["top"]], "  bearish only")

    tr = np.array([p["time_ratio"] for p in cands if not np.isnan(p["time_ratio"])])
    ar = np.array([p["amp_ratio"] for p in cands if not np.isnan(p["amp_ratio"])])
    if len(tr):
        print(f"  time symmetry (wave3-4 / wave1-2 duration ratio): "
              f"median={np.median(tr):.2f}  (1.0 = perfect symmetry)")
    if len(ar):
        print(f"  amplitude ratio (wave3-4 / wave1-2 size): median={np.median(ar):.2f}")

    print("  -- with strict Fibonacci 127%/162% extension filter applied --")
    cands_fib = find_candidates(zIdx, zType, zPx, require_fib=True)
    trades_fib = build_trades(cands_fib, h, l, c, atr, n)
    res_fib = eval_book(trades_fib, h, l, c)
    report(res_fib, f"Fib-filtered Wolfe waves ({len(cands_fib)} raw shapes, {len(cands_fib)/years:.1f}/yr)")

    return dict(name=name, years=years, cands=cands, res=res)


if __name__ == "__main__":
    h4 = E.load_h4()
    r_h4 = run("H4", h4)

    m5 = E.load_m5()
    m15 = E.resample_m15_from_m5(m5)
    r_m15 = run("M15 (resampled from real M5)", m15)

    print("\n" + "=" * 95)
    print("VERDICT: see per-timeframe numbers above.")
    print("=" * 95)
