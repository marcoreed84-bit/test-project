"""
Trend-line FAN test - the user's own live chart idea: from one anchor
swing point, draw a line to EACH subsequent swing pivot as it confirms
(a growing fan, not just one 2-point line - different construction from
trendline_break_search.py). When price breaks the currently-tightest
("outer") line, the classic manual-charting read is that it falls back to
the next ("inner") line of the fan as a graduated support/resistance
target, rather than just continuing unchecked.

UP-FAN (bull structure): anchor = the most recent confirmed swing LOW
(fractal low at PIVOT_K; the anchor resets to a fresh point whenever a
new, lower swing low confirms - matching how a trader redraws a fan from
a fresh higher-relevance low). Each subsequent confirmed swing HIGH since
that anchor adds one line (anchor -> that high, extrapolated forward).
Because every line shares the same origin, the line with the larger slope
is always the higher/tighter one at any later bar (simple geometry) - so
at each bar the lines sort cleanly into "outer" (currently the tightest,
highest-value line below price) and the rest.

SIGNAL: once >=2 lines exist, the first bar price closes below the
CURRENT outer line (having been riding along/above it) with a real gap
down to the next line (>= MIN_GAP_ATR x ATR, so it's not two nearly-
identical lines) -> SHORT, targeting that next (inner) line. Only one
signal per distinct outer-line break (no repeat signals off a line already
broken). DOWN-FAN (bear structure, anchor = swing high, lines to
subsequent lower lows) is the exact mirror -> LONG signal on an upside
break of the tightest resistance line.

SIZING: sig_dist = the actual price gap from the broken outer line to the
next inner line at the signal bar (not a generic ATR multiple - this is
the one test this session where the stop/target distance comes directly
from the chart structure the user is describing, not an ATR guess).
TARGET_R (grid) x that gap = how far past the next line to aim (0.5 =
halfway there, 1.0 = exactly at it, 1.5 = overshoot). The stop is the
SAME gap distance in the opposite direction (full gap risked to
invalidate the "moving toward the next line" thesis).

STEEPNESS FILTER (the user's own follow-up idea): a line's slope,
expressed in ATR-per-bar, is a measure of how "healthy" vs. "too steep"
(unsustainable) that leg of the move was. MIN_SLOPE_ATR requires the
broken outer line's slope to be at least that many ATR-per-bar before the
break counts as a signal - i.e. only trade the reversion-to-next-line
thesis when the line that broke was actually a steep, likely-unsustainable
one, not a already-gentle one.

PERFORMANCE NOTE: because every line in a fan shares one anchor, the
line with the larger slope is ALWAYS the higher-valued one at every bar
after the anchor (simple shared-origin geometry) - so the slope order
never changes as bars pass, only as new pivots are added. The lines are
kept in a slope-sorted list (bisect.insort on new pivots only, not every
bar) and a broken line is popped off the front - never re-sorted from
scratch per bar. An earlier version re-sorted the full (unbounded,
never-pruned) line list on every single bar and blew up past 8 minutes
of runtime on GOLD alone; this version finishes GOLD in a couple of
seconds.

GRID (K=36, literal): PIVOT_K in {5,10,20} x TARGET_R in {0.5,1.0,1.5} x
MIN_GAP_ATR in {0.5,1.0} x MIN_SLOPE_ATR in {0.0,0.02}.
"""
import bisect
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

PIVOT_KS = [5, 10, 20]
TARGET_RS = [0.5, 1.0, 1.5]
MIN_GAP_ATRS = [0.5, 1.0]
MIN_SLOPE_ATRS = [0.0, 0.02]  # price-units-per-bar / ATR; 0.02 ~= a genuinely steep leg on M15
MAX_GAP_ATR = 8.0  # sanity cap, not a grid axis: a stale anchor can accumulate a fan line spanning
# YEARS, producing a gap of hundreds of ATR to the "next line" - not a real trade a chart-reader would
# take, and with max_hold=200 bars it never resolves, blocking every subsequent signal for 200 bars.
# Found via a diagnostic run: p95 gap/ATR was 65x, max was 1159x, collapsing IS trade counts to ~35
# (below the n>=100 floor on every config) before this cap was added.


def build_fan_signals(h, l, c, atr, ph, pl, pivot_k, min_gap_atr, min_slope_atr):
    """Single forward pass, O(n log m). Lines are kept in slope-sorted
    order (bisect.insort on new pivots only); since every line in a fan
    shares one anchor, slope order == value order at every future bar, so
    the sort never needs to be redone per bar. A broken outer line is
    popped from the front - it never needs to be considered again.
    Returns long_sig, short_sig, sig_gap (price gap from the broken line
    to the next one, used as sig_dist)."""
    n = len(c)
    long_sig = np.zeros(n, dtype=np.bool_)
    short_sig = np.zeros(n, dtype=np.bool_)
    sig_gap = np.zeros(n, dtype=np.float64)

    # up-fan: anchor = swing low, lines to subsequent swing highs.
    # stored as (-slope, pbar, pprice), ascending -> descending slope -> descending value -> front = outer.
    up_anchor = None
    up_lines = []

    # down-fan: anchor = swing high, lines to subsequent swing lows.
    # stored as (slope, pbar, pprice); slope is negative, ascending -> most negative (lowest value) first -> front = outer.
    dn_anchor = None
    dn_lines = []

    for i in range(n):
        if not np.isnan(pl[i]):
            pbar, pprice = i - pivot_k, pl[i]
            if up_anchor is None or pprice < up_anchor[1]:
                up_anchor = (pbar, pprice)
                up_lines = []
        if not np.isnan(ph[i]):
            pbar, pprice = i - pivot_k, ph[i]
            if dn_anchor is None or pprice > dn_anchor[1]:
                dn_anchor = (pbar, pprice)
                dn_lines = []

        if not np.isnan(ph[i]) and up_anchor is not None:
            pbar, pprice = i - pivot_k, ph[i]
            abar, aprice = up_anchor
            if pbar > abar and pprice > aprice:
                slope = (pprice - aprice) / (pbar - abar)
                bisect.insort(up_lines, (-slope, pbar, pprice))
        if not np.isnan(pl[i]) and dn_anchor is not None:
            pbar, pprice = i - pivot_k, pl[i]
            abar, aprice = dn_anchor
            if pbar > abar and pprice < aprice:
                slope = (pprice - aprice) / (pbar - abar)
                bisect.insort(dn_lines, (slope, pbar, pprice))

        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue

        if up_anchor is not None and len(up_lines) >= 2:
            abar, aprice = up_anchor
            neg_slope0, _, _ = up_lines[0]
            neg_slope1, _, _ = up_lines[1]
            outer_v = aprice + (-neg_slope0) * (i - abar)
            inner_v = aprice + (-neg_slope1) * (i - abar)
            gap = outer_v - inner_v
            if c[i] < outer_v:
                # line is broken regardless of whether it's tradeable - a stale, huge-gap line
                # (a very old anchor) must not linger and block every future signal for 200 bars
                if min_gap_atr * a <= gap <= MAX_GAP_ATR * a and (-neg_slope0) / a >= min_slope_atr:
                    short_sig[i] = True
                    sig_gap[i] = gap
                up_lines.pop(0)

        if dn_anchor is not None and len(dn_lines) >= 2:
            abar, aprice = dn_anchor
            slope0, _, _ = dn_lines[0]
            slope1, _, _ = dn_lines[1]
            outer_v = aprice + slope0 * (i - abar)
            inner_v = aprice + slope1 * (i - abar)
            gap = inner_v - outer_v
            if c[i] > outer_v:
                if min_gap_atr * a <= gap <= MAX_GAP_ATR * a and (-slope0) / a >= min_slope_atr:
                    long_sig[i] = True
                    sig_gap[i] = gap
                dn_lines.pop(0)

    return long_sig, short_sig, sig_gap


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    log(f"\n{'='*90}\n{symbol} M15 -- Trend-line fan break (PIVOT_K, TARGET_R, MIN_GAP_ATR, MIN_SLOPE_ATR)\n{b.describe()}")

    grid = list(itertools.product(PIVOT_KS, TARGET_RS, MIN_GAP_ATRS, MIN_SLOPE_ATRS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    pivot_cache = {}
    for pk in PIVOT_KS:
        pivot_cache[pk] = C.pivots(b.high, b.low, pk)

    fan_cache = {}
    for pk, mg, ms in itertools.product(PIVOT_KS, MIN_GAP_ATRS, MIN_SLOPE_ATRS):
        ph, pl = pivot_cache[pk]
        fan_cache[(pk, mg, ms)] = build_fan_signals(b.high, b.low, b.close, b.atr, ph, pl, pk, mg, ms)

    rows = []
    cache = {}
    for cfg in grid:
        pk, target_r, mg, ms = cfg
        long_sig, short_sig, sig_gap = fan_cache[(pk, mg, ms)]
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((sig_gap[il], sig_gap[is_]))
        order = np.argsort(sig_bar, kind="stable")
        sig_bar, sig_dir, sig_dist = sig_bar[order], sig_dir[order], sig_dist[order]

        no_exit = np.zeros(b.n, dtype=np.bool_)
        ex = dict(target_r=target_r, max_hold=200, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)
        exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          *exargs, b.is_lo, b.is_hi)
        n_tr, pnl = len(r[3]), r[3]
        cache[cfg] = (sig_bar, sig_dir, sig_dist, ex)
        if n_tr < 100:
            continue
        rows.append(dict(cfg=cfg, n=n_tr, pf=C.pct_pf(pnl), win=float((pnl > 0).mean())))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=100. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}  win%={100*r['win']:.1f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    sig_bar, sig_dir, sig_dist, ex = cache[best["cfg"]]
    exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}  win%={100*best['win']:.1f}")

    r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                      *exargs, b.oos_lo, b.oos_hi)
    oos_pnl, oos_dist = r[3], r[4]
    n_oos = len(oos_pnl)
    if n_oos == 0:
        log("No OOS trades."); return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (0 OOS trades)")
    oos_pf = C.pct_pf(oos_pnl)
    oos_win = 100 * (oos_pnl > 0).mean()
    log(f"OOS (untouched): n={n_oos}  win%={oos_win:.1f}  %PF={oos_pf:.3f}  sum%={100*oos_pnl.sum():.1f}")
    if n_oos < 20:
        log("Too few OOS trades -> DOES NOT SURVIVE (insufficient evidence).")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (n<20)")

    allowed = np.ones(b.n, dtype=np.bool_)
    pool, p_fire, mean_n = C.random_pool(b, oos_dist, n_oos, *exargs, b.oos_lo, b.oos_hi, allowed)
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f}): "
        f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]")
    return dict(label=symbol, K=K, cfg=best["cfg"], is_n=best["n"], is_pf=best["pf"], oos_n=n_oos, oos_pf=oos_pf,
                oos_win=oos_win, pctile=pctile, p1=p1, pK=pK,
                verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/fan_line_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
