"""
Classic manual-charting trend-line break test - the user's explicit ask:
"old school", the same technique most discretionary traders have used for
decades. Different construction from the prior_day_sr_search.py test
(which used flat horizontal prior-day highs/lows) - this connects actual
swing pivots with a DIAGONAL line and trades a break of it, same as
drawing a trend line on a chart by hand.

PIVOTS: N-bar fractal highs/lows via common.pivots() (confirmation-time,
no lookahead - a pivot at bar j is only known once bar j+PIVOT_K closes).

TREND LINES, rebuilt bar by bar as new pivots confirm:
  - RESISTANCE: the two most recent confirmed swing HIGHS, only used while
    they form a genuine descending line (2nd high < 1st high) - i.e. only
    while the chart is actually making lower highs, same as a trader would
    only draw a resistance line across a series of falling peaks.
  - SUPPORT: the two most recent confirmed swing LOWS, only while they form
    a genuine ascending line (2nd low > 1st low) - rising troughs.
Each line is linearly extrapolated forward from its two anchor points to
today's bar.

SIGNAL (classic trend-line-break interpretation - a break signals the
established trend is ENDING, not continuing): close breaks UP through a
valid descending resistance line -> long (a downtrend line finally being
broken to the upside). Close breaks DOWN through a valid ascending support
line -> short. BUFFER_ATR filters noise-level touches from a real break.
Only ONE signal is taken per distinct pivot-pair (the same two anchor
points can't re-signal every bar once broken - a trader redraws the line
after a break, they don't re-trade the old one).

EXIT: fixed 1.5R target or an ATR-multiple stop, first to hit, max hold
200 bars - same shape as prior_day_sr_search.py and the VWAP tests for a
fair comparison against everything else tried this session.

GRID (K=18, literal): PIVOT_K (swing size) in {5,10,20} x BUFFER_ATR in
{0.1,0.2} x STOP_ATR_MULT in {0.5,1.0,1.5}.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

PIVOT_KS = [5, 10, 20]
BUFFER_ATRS = [0.1, 0.2]
STOP_ATR_MULTS = [0.5, 1.0, 1.5]
TARGET_R = 1.5


def build_trendline_signals(h, l, c, atr, ph, pl, pivot_k, buffer_atr):
    """Single forward pass: maintain the latest 2-pivot resistance/support
    lines, emit a break signal the first time each distinct line is broken."""
    n = len(c)
    long_sig = np.zeros(n, dtype=np.bool_)
    short_sig = np.zeros(n, dtype=np.bool_)

    res1 = res2 = None  # each: (bar, price)
    sup1 = sup2 = None
    res_signaled = True  # no valid line yet -> nothing to signal
    sup_signaled = True

    for i in range(n):
        if not np.isnan(ph[i]):
            pbar = i - pivot_k
            res1, res2 = res2, (pbar, ph[i])
            res_signaled = False
        if not np.isnan(pl[i]):
            pbar = i - pivot_k
            sup1, sup2 = sup2, (pbar, pl[i])
            sup_signaled = False

        if not res_signaled and res1 is not None and res2 is not None and res2[1] < res1[1]:
            slope = (res2[1] - res1[1]) / (res2[0] - res1[0])
            lv = res1[1] + slope * (i - res1[0])
            a = atr[i]
            if not np.isnan(a) and a > 0 and c[i] > lv + buffer_atr * a:
                long_sig[i] = True
                res_signaled = True

        if not sup_signaled and sup1 is not None and sup2 is not None and sup2[1] > sup1[1]:
            slope = (sup2[1] - sup1[1]) / (sup2[0] - sup1[0])
            lv = sup1[1] + slope * (i - sup1[0])
            a = atr[i]
            if not np.isnan(a) and a > 0 and c[i] < lv - buffer_atr * a:
                short_sig[i] = True
                sup_signaled = True

    return long_sig, short_sig


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    log(f"\n{'='*90}\n{symbol} M15 -- Trend-line break (PIVOT_K, BUFFER_ATR, STOP_ATR_MULT)\n{b.describe()}")

    grid = list(itertools.product(PIVOT_KS, BUFFER_ATRS, STOP_ATR_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    pivot_cache = {}
    for pk in PIVOT_KS:
        pivot_cache[pk] = C.pivots(b.high, b.low, pk)

    sig_cache = {}
    for pk, buf in itertools.product(PIVOT_KS, BUFFER_ATRS):
        ph, pl = pivot_cache[pk]
        sig_cache[(pk, buf)] = build_trendline_signals(b.high, b.low, b.close, b.atr, ph, pl, pk, buf)

    rows = []
    cache = {}
    for cfg in grid:
        pk, buf, stop_mult = cfg
        long_sig, short_sig = sig_cache[(pk, buf)]
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        valid_l = ~np.isnan(b.atr[il]) & (b.atr[il] > 0)
        valid_s = ~np.isnan(b.atr[is_]) & (b.atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = stop_mult * b.atr[il]
        dist_s = stop_mult * b.atr[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        sig_bar, sig_dir, sig_dist = sig_bar[order], sig_dir[order], sig_dist[order]

        no_exit = np.zeros(b.n, dtype=np.bool_)
        ex = dict(target_r=TARGET_R, max_hold=200, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)
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
    out_path = "/home/user/test-project/research/silver_btc/trendline_break_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
