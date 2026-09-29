"""
"Look to the left" test - the user's explicit pushback on
prior_day_sr_search.py: that test only used a rolling 1/3/5-day window,
which is the opposite of "look to the left for previous levels." A real
old-school trader scans the WHOLE visible history for major levels, not
just the last few days, and treats them as live again whenever price
revisits - weeks or months later.

LEVELS: every confirmed major swing pivot (high OR low, pooled together -
old resistance becoming new support and vice versa is part of the same
folklore) across the FULL history seen so far, kept forever (not a
rolling window). "Major" = at least MIN_SWING_ATR x ATR away from the
last confirmed opposite-type swing before it - same prominence filter as
FanLines_Indicator.mq5's InpMinSwingATR, directly testing the "clever
guys only care about REAL levels, not noise" idea.

SIGNAL: the first bar of a fresh approach (previous bar was NOT within
BUFFER_ATR of a given level, this bar IS) to the nearest level above or
below price - fade (bet the level holds) or break (bet it doesn't),
exactly the same two interpretations prior_day_sr_search.py used, so the
only thing that changes between the two tests is "recent rolling window"
vs. "any major level ever, no matter how old." The SAME level can signal
again much later - that's the whole point of "look to the left," so nothing
here prevents an old level from mattering again after months of no contact.

EXIT: 1.5R target or an ATR-multiple stop, max hold 200 bars - identical
shape to prior_day_sr_search.py for a direct, apples-to-apples comparison.

GRID (K=18, literal): MIN_SWING_ATR (how major a level must be) in
{1.0,2.0,3.0} x MODE in {fade,break} x STOP_ATR_MULT in {0.5,1.0,1.5}.
"""
import bisect
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

MIN_SWING_ATRS = [1.0, 2.0, 3.0]
MODES = ["fade", "break"]
STOP_ATR_MULTS = [0.5, 1.0, 1.5]
TARGET_R = 1.5
BUFFER_ATR = 0.15


def build_major_levels(h, l, atr, pivot_k, min_swing_atr):
    """Fractal pivots (common.pivots() rule) kept only if >= min_swing_atr
    ATR away from the last confirmed opposite-type pivot - same
    prominence filter as the MT5 indicator's InpMinSwingATR."""
    ph, pl = C.pivots(h, l, pivot_k)
    n = len(h)
    is_major_high = np.zeros(n, dtype=np.bool_)
    is_major_low = np.zeros(n, dtype=np.bool_)
    last_major_high, last_major_low = np.nan, np.nan
    for j in range(n):
        a = atr[j]
        okh = not np.isnan(ph[j])
        okl = not np.isnan(pl[j])
        if okh and not np.isnan(last_major_low) and a > 0 and (ph[j] - last_major_low) < min_swing_atr * a:
            okh = False
        if okl and not np.isnan(last_major_high) and a > 0 and (last_major_high - pl[j]) < min_swing_atr * a:
            okl = False
        is_major_high[j] = okh
        is_major_low[j] = okl
        if okh:
            last_major_high = ph[j]
        if okl:
            last_major_low = pl[j]
    return is_major_high, is_major_low


def build_revisit_signals(c, atr, is_major_high, is_major_low, high_val, low_val, mode):
    """Forward pass: maintain a sorted, ever-growing pool of major level
    prices. On the first bar of a fresh approach to the nearest level
    (above or below), fire a fade/break signal. Old levels are never
    dropped - a level from months ago can matter again."""
    n = len(c)
    long_sig = np.zeros(n, dtype=np.bool_)
    short_sig = np.zeros(n, dtype=np.bool_)
    levels = []  # sorted list of price levels
    was_near_below = False  # was previous bar within buffer of nearest-below level
    was_near_above = False

    for i in range(n):
        if is_major_high[i]:
            bisect.insort(levels, high_val[i])
        if is_major_low[i]:
            bisect.insort(levels, low_val[i])

        a = atr[i]
        if np.isnan(a) or a <= 0 or not levels:
            was_near_below = was_near_above = False
            continue

        price = c[i]
        pos = bisect.bisect_right(levels, price)
        buf = BUFFER_ATR * a

        near_below = False
        if pos > 0:
            lvl = levels[pos - 1]
            dist = price - lvl
            if 0 <= dist <= buf:
                near_below = True
                if not was_near_below:
                    if mode == "fade":
                        long_sig[i] = True   # bet the level below holds as support
                    else:
                        if price < lvl:
                            short_sig[i] = True  # already broke through - continuation

        near_above = False
        if pos < len(levels):
            lvl = levels[pos]
            dist = lvl - price
            if 0 <= dist <= buf:
                near_above = True
                if not was_near_above:
                    if mode == "fade":
                        short_sig[i] = True  # bet the level above holds as resistance
                    else:
                        if price > lvl:
                            long_sig[i] = True

        was_near_below, was_near_above = near_below, near_above

    return long_sig, short_sig


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    log(f"\n{'='*90}\n{symbol} M15 -- 'Look to the left' major-level revisit (MIN_SWING_ATR, MODE, STOP_ATR_MULT)\n{b.describe()}")

    grid = list(itertools.product(MIN_SWING_ATRS, MODES, STOP_ATR_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    level_cache = {}
    for ms in MIN_SWING_ATRS:
        level_cache[ms] = build_major_levels(b.high, b.low, b.atr, 10, ms)

    sig_cache = {}
    for ms, mode in itertools.product(MIN_SWING_ATRS, MODES):
        is_mh, is_ml = level_cache[ms]
        sig_cache[(ms, mode)] = build_revisit_signals(b.close, b.atr, is_mh, is_ml, b.high, b.low, mode)

    rows = []
    cache = {}
    for cfg in grid:
        ms, mode, stop_mult = cfg
        long_sig, short_sig = sig_cache[(ms, mode)]
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
    out_path = "/home/user/test-project/research/silver_btc/major_level_revisit_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
