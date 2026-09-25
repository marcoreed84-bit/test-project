"""
Next Murphy-book idea after candlesticks (hs_candlestick_test.py): "Major
Reversal Patterns" ch.5 treats Double/Triple Tops and Bottoms as patterns
genuinely DISTINCT from Head & Shoulders (no head, all extrema roughly
level, not "peaks-with-a-higher-middle-peak"). Never built in this project
before. Real GOLD M15 data, same measured-move-target methodology as
head_shoulders_target_test.py: does price actually reach the classic
book target within a real horizon, checked against a half-height control
(isolates whether the SPECIFIC height calculation does real work) and a
calibration check (of moves that stall, how far as a fraction of target).

DOUBLE TOP (bearish): swings H1-L1-H2, |H1-H2| <= tol*ATR (peaks level),
  neckline = L1 (flat). Breakout = BREAK_CONFIRM_CLOSES consecutive closes
  below neckline. Target = (avg(H1,H2) - neckline) projected DOWN from the
  breakout price. Double bottom is the exact mirror (L1-H1-L2).

TRIPLE TOP (bearish): H1-L1-H2-L2-H3, all three peaks within tol*ATR of
  each other (max-min, not just pairwise), neckline = line through L1,L2
  (sloped, same convention as the H&S neckline). Target = (avg peak height
  over neckline at that peak's own time) projected DOWN from breakout.
  Triple bottom is the mirror (L1-H1-L2-H2-L3).

This is standalone pattern research (not yet wired to any EA) - the
question is whether the pattern itself has real predictive content before
any EA implementation work is considered.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, ATR_PERIOD, BREAK_CONFIRM_CLOSES

np.random.seed(42)

TOL_ATR = 1.0            # "roughly level" extrema tolerance
BREAK_TOL_ATR = 0.10
MAX_HORIZON_MULT = 4.0
MAX_HORIZON_CAP = 400


def find_double(zIdx, zType, zPx, top):
    """top=True: H1-L1-H2 (double top, bearish). top=False: L1-H1-L2 (double bottom)."""
    want = 1 if top else -1
    out = []
    for m in range(len(zIdx) - 2):
        seq = zType[m:m + 3]
        if top and seq != [1, -1, 1]:
            continue
        if not top and seq != [-1, 1, -1]:
            continue
        p1, pn, p2 = zPx[m], zPx[m + 1], zPx[m + 2]
        out.append(dict(i_e1=zIdx[m], i_neck=zIdx[m + 1], i_e2=zIdx[m + 2],
                         p_e1=p1, p_neck=pn, p_e2=p2))
    return out


def find_triple(zIdx, zType, zPx, top):
    """top=True: H1-L1-H2-L2-H3 (triple top). top=False: L1-H1-L2-H2-L3 (triple bottom)."""
    out = []
    for m in range(len(zIdx) - 4):
        seq = zType[m:m + 5]
        if top and seq != [1, -1, 1, -1, 1]:
            continue
        if not top and seq != [-1, 1, -1, 1, -1]:
            continue
        p1, pn1, p2, pn2, p3 = zPx[m:m + 5]
        out.append(dict(i_e1=zIdx[m], i_n1=zIdx[m + 1], i_e2=zIdx[m + 2],
                         i_n2=zIdx[m + 3], i_e3=zIdx[m + 4],
                         p_e1=p1, p_n1=pn1, p_e2=p2, p_n2=pn2, p_e3=p3))
    return out


def evaluate(df, kind, top):
    """kind: 'double' or 'triple'. Returns list of dicts with hit/half_hit/frac_of_target."""
    n = len(df)
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    atr = sma_atr(h, l, o, ATR_PERIOD)
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)

    if kind == "double":
        pats = find_double(zIdx, zType, zPx, top)
    else:
        pats = find_triple(zIdx, zType, zPx, top)

    results = []
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
        half_target = (brk_price - 0.5 * height) if top else (brk_price + 0.5 * height)
        max_horizon = min(n - 1, brk_q + MAX_HORIZON_CAP)

        hit = half_hit = False
        extreme_reached = brk_price
        for k in range(brk_q + 1, max_horizon + 1):
            if top:
                extreme_reached = min(extreme_reached, l[k])
                if not half_hit and l[k] <= half_target:
                    half_hit = True
                if l[k] <= target:
                    hit = True; break
            else:
                extreme_reached = max(extreme_reached, h[k])
                if not half_hit and h[k] >= half_target:
                    half_hit = True
                if h[k] >= target:
                    hit = True; break

        frac_of_target = abs(extreme_reached - brk_price) / height if height > 0 else np.nan
        results.append(dict(hit=hit, half_hit=half_hit, frac=frac_of_target, brk_q=brk_q))
    return results


def report(results, label):
    n = len(results)
    if n < 8:
        print(f"  {label}: only {n} patterns - too few"); return
    hit_rate = 100 * np.mean([r["hit"] for r in results])
    half_hit_rate = 100 * np.mean([r["half_hit"] for r in results])
    frac = np.array([r["frac"] for r in results])
    print(f"  {label}: n={n}  full-target hit%={hit_rate:.1f}  half-target hit%={half_hit_rate:.1f}  "
          f"median frac-of-target reached={np.median(frac):.2f}  mean={np.mean(frac):.2f}")


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    print(f"M15 data: n={len(df15)} bars, {df15['time'].min()} -> {df15['time'].max()}")

    print("\n" + "=" * 95)
    print("DOUBLE TOP / DOUBLE BOTTOM")
    print("=" * 95)
    for top, name in ((True, "double top (bearish)"), (False, "double bottom (bullish)")):
        res = evaluate(df15, "double", top)
        report(res, name)

    print("\n" + "=" * 95)
    print("TRIPLE TOP / TRIPLE BOTTOM")
    print("=" * 95)
    for top, name in ((True, "triple top (bearish)"), (False, "triple bottom (bullish)")):
        res = evaluate(df15, "triple", top)
        report(res, name)
