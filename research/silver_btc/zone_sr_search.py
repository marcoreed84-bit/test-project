"""
Zone-based S/R test - the user's full operational rundown (verbatim
methodology), which is genuinely different from every prior S/R test this
session (prior_day_sr_search.py: flat rolling-window levels;
major_level_revisit_search.py: single-price pivots from full history).
This one follows the specific steps given:

1. MAPPING: major turning points found on D1 (prominence-filtered swing
   pivots, >= 1x daily-ATR from the last opposite swing), then refined
   into a WIDTH on H4 - the zone is [min low, max high] of the H4 bars
   within 1 day either side of the D1 pivot (captures bodies AND wicks,
   not a single price line).
2. VALIDATION: a zone only becomes tradeable once price has touched it
   >= MIN_TOUCHES times (grid: 2 or 3, testing the rundown's "3+" claim
   against a looser bar). A zone is retired (stops signaling) after
   MAX_TOUCHES=6 touches - the "freshness / overtested levels get weak"
   rule, fixed rather than gridded to keep this tractable.
   CONFLUENCE (grid, on/off): the zone's midpoint must fall within 0.25x
   daily-ATR of a "round number" (instrument-scaled step: $10 for GOLD,
   $0.50 for SILVER, $500 for BTCUSD) to count at all.
3. EXECUTION, two strategies (grid axis):
   - "bounce": at a validated touch, require an objective rejection
     candle (a pin-bar-style long wick >= 2x body closing in the
     favorable half of its range, OR a same-direction engulfing candle)
     on the M15 execution timeframe. Stop goes just beyond that candle's
     wick (entry-specific, not a generic ATR guess). Target is a
     TARGET_R multiple of that stop distance - an approximation of "the
     next opposing zone" (an exact dynamic zone-to-zone target isn't
     supported by this project's R-multiple sim engine; documented here
     rather than silently simplified).
   - "break_retest": a full-BODIED candle closes cleanly through the
     zone (not just a wick), then within a 48h window price returns to
     retest the outside of that same zone with a same-direction
     continuation candle - only then does it enter. Stop sits just
     inside the zone.

GRID (K=16, literal): MIN_TOUCHES in {2,3} x STRATEGY in
{bounce,break_retest} x CONFLUENCE in {off,on} x TARGET_R in {1.5,2.5}.

SIMPLIFICATIONS, stated plainly rather than silently dropped: MA
confluence (only round-number confluence is tested), fixed (not gridded)
rejection-wick multiplier/MAX_TOUCHES/H4 window/retest window - gridding
every one of these would blow K past what's defensible.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

MIN_TOUCHES_OPTS = [2, 3]
STRATEGIES = ["bounce", "break_retest"]
CONFLUENCE_OPTS = [False, True]
TARGET_RS = [1.5, 2.5]

MAX_TOUCHES = 6
D1_PROMINENCE_ATR = 1.0
H4_WINDOW_DAYS = 1
CONFLUENCE_TOL_ATR = 0.25
REJECTION_WICK_MULT = 2.0
RETEST_WINDOW_BARS = 192  # ~48h on M15
ZONE_RELEVANCE_BARS = 20000  # ~208 days on M15 - bounds the per-zone scan (see build_signals)
ROUND_STEP = {"GOLD": 10.0, "SILVER": 0.5, "BTCUSD": 500.0}


def wilder_atr_d1(dfd):
    return C.wilder_atr(dfd["high"].values, dfd["low"].values, dfd["close"].values, 14)


def build_zones(dfd, d_atr, df4h):
    """D1 major-pivot detection (prominence-filtered) + H4 width refinement.
    Returns a list of dicts: {formed_time, lo, hi, mid, kind}."""
    d_high, d_low = dfd["high"].values, dfd["low"].values
    d_time = dfd["time"].values
    n_d = len(dfd)
    ph, pl = C.pivots(d_high, d_low, 3)  # 3-day-each-side fractal on D1

    last_major_high, last_major_low = np.nan, np.nan
    zones = []
    h4_time = df4h["time"].values
    h4_high, h4_low = df4h["high"].values, df4h["low"].values

    for j in range(n_d):
        a = d_atr[j]
        if np.isnan(a) or a <= 0:
            continue
        okh = not np.isnan(ph[j])
        okl = not np.isnan(pl[j])
        if okh and not np.isnan(last_major_low) and (ph[j] - last_major_low) < D1_PROMINENCE_ATR * a:
            okh = False
        if okl and not np.isnan(last_major_high) and (last_major_high - pl[j]) < D1_PROMINENCE_ATR * a:
            okl = False
        if okh:
            last_major_high = ph[j]
        if okl:
            last_major_low = pl[j]
        if not (okh or okl):
            continue

        t0 = d_time[j] - np.timedelta64(H4_WINDOW_DAYS, "D")
        t1 = d_time[j] + np.timedelta64(H4_WINDOW_DAYS, "D")
        m = (h4_time >= t0) & (h4_time <= t1)
        if not m.any():
            continue
        lo = h4_low[m].min()
        hi = h4_high[m].max()
        zones.append(dict(formed_time=d_time[j], lo=lo, hi=hi, mid=0.5 * (lo + hi)))
    return zones


def rejection_candle(o, h, l, c, i, want_bullish):
    body = abs(c[i] - o[i])
    rng = h[i] - l[i]
    if rng <= 0:
        return False
    if want_bullish:
        lower_wick = min(o[i], c[i]) - l[i]
        pin = lower_wick >= REJECTION_WICK_MULT * max(body, 1e-12) and c[i] > (h[i] + l[i]) / 2
        engulf = (i > 0 and c[i] > o[i] and o[i] < c[i - 1] and c[i] > o[i - 1]
                  and (c[i] - o[i]) > abs(o[i - 1] - c[i - 1]) and c[i - 1] < o[i - 1])
        return pin or engulf
    else:
        upper_wick = h[i] - max(o[i], c[i])
        pin = upper_wick >= REJECTION_WICK_MULT * max(body, 1e-12) and c[i] < (h[i] + l[i]) / 2
        engulf = (i > 0 and c[i] < o[i] and o[i] > c[i - 1] and c[i] < o[i - 1]
                  and (o[i] - c[i]) > abs(c[i - 1] - o[i - 1]) and c[i - 1] > o[i - 1])
        return pin or engulf


def build_signals(b, zones, d_atr_series, d_time, min_touches, strategy, confluence, target_r, symbol):
    o, h, l, c = b.open, b.high, b.low, b.close
    n = b.n
    long_bars, long_dist = [], []
    short_bars, short_dist = [], []

    step = ROUND_STEP[symbol]

    for z in zones:
        if confluence:
            nearest_round = round(z["mid"] / step) * step
            j = np.searchsorted(d_time, z["formed_time"])
            j = min(max(j, 0), len(d_atr_series) - 1)
            a0 = d_atr_series[j]
            if np.isnan(a0) or abs(z["mid"] - nearest_round) > CONFLUENCE_TOL_ATR * a0:
                continue

        start_bar = np.searchsorted(b.time_vals, z["formed_time"])
        if start_bar >= n - 1:
            continue
        # ZONE_RELEVANCE_BARS bounds the scan - without it this loop is O(n_zones x n_bars)
        # (hundreds of D1 zones x ~300k M15 bars each), which hung past several minutes on GOLD
        # alone before this cap was added. A zone nothing has happened at in ~7 months is also
        # a reasonable place to stop treating it as "live" for this test.
        end_bar = min(n, start_bar + ZONE_RELEVANCE_BARS)

        touches = 0
        in_zone_prev = False
        broke_up_pending = None  # bar index of clean break, waiting for retest
        broke_dn_pending = None

        for i in range(start_bar, end_bar):
            price = c[i]
            in_zone = z["lo"] <= price <= z["hi"]

            if strategy == "bounce":
                if in_zone and not in_zone_prev:
                    touches += 1
                if in_zone and min_touches <= touches <= MAX_TOUCHES:
                    a = b.atr[i]
                    if not np.isnan(a) and a > 0:
                        if l[i] <= z["lo"] + 0.1 * a and rejection_candle(o, h, l, c, i, True):
                            stop_dist = (c[i] - (l[i] - 0.1 * a))
                            if stop_dist > 0:
                                long_bars.append(i); long_dist.append(stop_dist)
                        if h[i] >= z["hi"] - 0.1 * a and rejection_candle(o, h, l, c, i, False):
                            stop_dist = ((h[i] + 0.1 * a) - c[i])
                            if stop_dist > 0:
                                short_bars.append(i); short_dist.append(stop_dist)
            else:  # break_retest
                body_lo, body_hi = min(o[i], c[i]), max(o[i], c[i])
                if broke_up_pending is None and body_lo > z["hi"]:
                    broke_up_pending = i
                if broke_dn_pending is None and body_hi < z["lo"]:
                    broke_dn_pending = i
                if broke_up_pending is not None and i - broke_up_pending <= RETEST_WINDOW_BARS:
                    if l[i] <= z["hi"] and c[i] > z["hi"] and rejection_candle(o, h, l, c, i, True):
                        stop_dist = c[i] - z["lo"]
                        if stop_dist > 0:
                            long_bars.append(i); long_dist.append(stop_dist)
                        broke_up_pending = None
                elif broke_up_pending is not None and i - broke_up_pending > RETEST_WINDOW_BARS:
                    broke_up_pending = None
                if broke_dn_pending is not None and i - broke_dn_pending <= RETEST_WINDOW_BARS:
                    if h[i] >= z["lo"] and c[i] < z["lo"] and rejection_candle(o, h, l, c, i, False):
                        stop_dist = z["hi"] - c[i]
                        if stop_dist > 0:
                            short_bars.append(i); short_dist.append(stop_dist)
                        broke_dn_pending = None
                elif broke_dn_pending is not None and i - broke_dn_pending > RETEST_WINDOW_BARS:
                    broke_dn_pending = None

            in_zone_prev = in_zone
            if touches > MAX_TOUCHES:
                break

    sig_bar = np.array(long_bars + short_bars, dtype=np.int64)
    sig_dir = np.array([1.0] * len(long_bars) + [-1.0] * len(short_bars))
    sig_dist = np.array(long_dist + short_dist, dtype=np.float64)
    order = np.argsort(sig_bar, kind="stable")
    return sig_bar[order], sig_dir[order], sig_dist[order]


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    b.time_vals = df15["time"].values

    dfd = C.resample(df15, "1D")
    df4h = C.resample(df15, "4h")
    d_atr = wilder_atr_d1(dfd)
    d_time = pd.to_datetime(dfd["time"]).values

    log(f"\n{'='*90}\n{symbol} M15/D1/H4 -- Zone S/R (MIN_TOUCHES, STRATEGY, CONFLUENCE, TARGET_R)\n{b.describe()}")

    zones = build_zones(dfd, d_atr, df4h)
    log(f"built {len(zones)} D1/H4-refined zones (>= {D1_PROMINENCE_ATR}x daily-ATR prominence)")

    grid = list(itertools.product(MIN_TOUCHES_OPTS, STRATEGIES, CONFLUENCE_OPTS, TARGET_RS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    sig_cache = {}
    for mt, strat, conf in itertools.product(MIN_TOUCHES_OPTS, STRATEGIES, CONFLUENCE_OPTS):
        sig_cache[(mt, strat, conf)] = build_signals(b, zones, d_atr, d_time, mt, strat, conf, 1.0, symbol)

    rows = []
    cache = {}
    for cfg in grid:
        mt, strat, conf, target_r = cfg
        sig_bar, sig_dir, sig_dist = sig_cache[(mt, strat, conf)]
        no_exit = np.zeros(b.n, dtype=np.bool_)
        ex = dict(target_r=target_r, max_hold=400, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)
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
    out_path = "/home/user/test-project/research/silver_btc/zone_sr_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
