"""
Multi-timeframe confluence test - the user's specific follow-up: M15 has
its own local swing levels, nested WITHIN the higher-timeframe (D1/H4)
structure zone_sr_search.py tested. That script only used D1/H4 to find
levels at all (M15 was purely the execution timeframe for entries). This
test asks the actual question: do M15-native swing levels work BETTER
when they sit inside an already-formed D1/H4 zone (confluence) than when
they don't (a plain, timeframe-local level with nothing bigger behind
it)?

LEVELS: M15-native fractal swing pivots (common.pivots(), M15_PIVOT_K
bars each side - the SAME construction trendline_break_search.py and
fan_line_search.py used, just as single price points here, not lines).
Each is tagged CONFLUENCE=True if its price falls inside a D1/H4 zone
(reusing zone_sr_search.py's build_zones() unchanged) that had ALREADY
formed strictly before this M15 pivot confirmed - no lookahead.

REQUIRE_CONFLUENCE (grid, the actual variable under test): True keeps
only M15 levels nested inside a pre-existing HTF zone; False keeps every
M15 level regardless. Comparing these two head to head, with everything
else identical, isolates exactly the "nested levels matter more" claim.

SIGNAL: same revisit-detection shape as major_level_revisit_search.py
(a level stays live forever, the same level can signal again on a later,
separate approach), but upgraded with zone_sr_search.py's stricter
triggers: fade requires an objective rejection candle
(pin-bar/engulfing) at the touch, break requires a full-BODIED close
through the level, not just a wick or a bare close.

GRID (K=16, literal): M15_PIVOT_K in {5,10} x REQUIRE_CONFLUENCE in
{False,True} x MODE in {fade,break} x TARGET_R in {1.5,2.5}. Stop is a
fixed 1.0x ATR (not gridded, to keep K defensible).
"""
import bisect
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C
from zone_sr_search import build_zones, rejection_candle, wilder_atr_d1

M15_PIVOT_KS = [5, 10]
CONFLUENCE_OPTS = [False, True]
MODES = ["fade", "break"]
TARGET_RS = [1.5, 2.5]
STOP_ATR_MULT = 1.0
BUFFER_ATR = 0.15


def tag_confluence(time_vals, ph, pl, high_val, low_val, zones):
    """One pass over M15 fractal pivots: for each, tag whether it falls
    inside a D1/H4 zone formed strictly before this pivot's own time."""
    if not zones:
        zone_times = np.array([], dtype="datetime64[ns]")
        zone_lo = np.array([]); zone_hi = np.array([])
    else:
        order = np.argsort([z["formed_time"] for z in zones])
        zone_times = np.array([zones[o]["formed_time"] for o in order])
        zone_lo = np.array([zones[o]["lo"] for o in order])
        zone_hi = np.array([zones[o]["hi"] for o in order])

    levels = []
    n = len(ph)
    for i in range(n):
        if not np.isnan(ph[i]):
            price = high_val[i]
        elif not np.isnan(pl[i]):
            price = low_val[i]
        else:
            continue
        k = np.searchsorted(zone_times, time_vals[i], side="left")
        confluence = False
        if k > 0:
            lo_active, hi_active = zone_lo[:k], zone_hi[:k]
            confluence = bool(np.any((lo_active <= price) & (price <= hi_active)))
        levels.append((i, price, confluence))
    return levels


def build_revisit_signals(c, h, l, o, atr, levels, require_confluence, mode):
    n = len(c)
    long_sig = np.zeros(n, dtype=np.bool_)
    short_sig = np.zeros(n, dtype=np.bool_)
    lvls = []
    li = 0
    was_near_below = was_near_above = False

    for i in range(n):
        while li < len(levels) and levels[li][0] == i:
            _, price, conf = levels[li]
            if (not require_confluence) or conf:
                bisect.insort(lvls, price)
            li += 1

        a = atr[i]
        if np.isnan(a) or a <= 0 or not lvls:
            was_near_below = was_near_above = False
            continue

        price_now = c[i]
        pos = bisect.bisect_right(lvls, price_now)
        buf = BUFFER_ATR * a
        body_lo, body_hi = min(o[i], c[i]), max(o[i], c[i])

        near_below = False
        if pos > 0:
            lvl = lvls[pos - 1]
            dist = price_now - lvl
            if 0 <= dist <= buf:
                near_below = True
                if not was_near_below:
                    if mode == "fade" and l[i] <= lvl + buf and rejection_candle(o, h, l, c, i, True):
                        long_sig[i] = True
                    elif mode == "break" and body_lo > lvl:
                        short_sig[i] = True  # broke DOWN through what was acting as support from above

        near_above = False
        if pos < len(lvls):
            lvl = lvls[pos]
            dist = lvl - price_now
            if 0 <= dist <= buf:
                near_above = True
                if not was_near_above:
                    if mode == "fade" and h[i] >= lvl - buf and rejection_candle(o, h, l, c, i, False):
                        short_sig[i] = True
                    elif mode == "break" and body_hi < lvl:
                        long_sig[i] = True  # broke UP through what was acting as resistance from below

        was_near_below, was_near_above = near_below, near_above

    return long_sig, short_sig


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    time_vals = df15["time"].values

    dfd = C.resample(df15, "1D")
    df4h = C.resample(df15, "4h")
    d_atr = wilder_atr_d1(dfd)
    zones = build_zones(dfd, d_atr, df4h)

    log(f"\n{'='*90}\n{symbol} M15/D1/H4 -- MTF confluence (M15_PIVOT_K, REQUIRE_CONFLUENCE, MODE, TARGET_R)\n{b.describe()}")
    log(f"built {len(zones)} D1/H4 zones (reused from zone_sr_search.py)")

    grid = list(itertools.product(M15_PIVOT_KS, CONFLUENCE_OPTS, MODES, TARGET_RS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    pivot_cache = {}
    for pk in M15_PIVOT_KS:
        pivot_cache[pk] = C.pivots(b.high, b.low, pk)

    level_cache = {}
    for pk in M15_PIVOT_KS:
        ph, pl = pivot_cache[pk]
        levels = tag_confluence(time_vals, ph, pl, b.high, b.low, zones)
        n_conf = sum(1 for _, _, c in levels if c)
        log(f"  M15_PIVOT_K={pk}: {len(levels)} M15 levels, {n_conf} ({100*n_conf/max(1,len(levels)):.1f}%) inside an HTF zone")
        level_cache[pk] = levels

    sig_cache = {}
    for pk, req_conf, mode in itertools.product(M15_PIVOT_KS, CONFLUENCE_OPTS, MODES):
        levels = level_cache[pk]
        sig_cache[(pk, req_conf, mode)] = build_revisit_signals(b.close, b.high, b.low, b.open, b.atr,
                                                                  levels, req_conf, mode)

    rows = []
    cache = {}
    for cfg in grid:
        pk, req_conf, mode, target_r = cfg
        long_sig, short_sig = sig_cache[(pk, req_conf, mode)]
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        valid_l = ~np.isnan(b.atr[il]) & (b.atr[il] > 0)
        valid_s = ~np.isnan(b.atr[is_]) & (b.atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = STOP_ATR_MULT * b.atr[il]
        dist_s = STOP_ATR_MULT * b.atr[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
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
    out_path = "/home/user/test-project/research/silver_btc/mtf_confluence_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
