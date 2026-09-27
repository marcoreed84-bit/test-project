"""
"BTCUSD Supertrend + EMA Trend Filter (1H)" (the user's ninth pasted
Pine v6 strategy, blitz_locked) - explicitly named and tuned FOR
Bitcoin, on the 1-HOUR timeframe: both honored here (tested on H1,
resampled losslessly from real M15, and BTC is the priority instrument,
though Gold/Silver are still checked for consistency with the rest of
this folder). Plain, non-adaptive SuperTrend(factor=1.8, ATR len=10)
flip, filtered by an EMA(200) trend-alignment gate (long only above the
EMA, short only below), optional ADX filter (OFF by default - not
tuned, kept off). Genuinely different from silver_native_ma_cross_
search.py / btc_native_search.py's bare EMA-cross tests (SuperTrend
bands react to volatility/ATR, not just two moving-average values
crossing) and from supertrend_regime_search.py (that one's multiplier
ADAPTS by regime and is gated by a 5-factor score; this one is the
plain, non-adaptive version with only a trend-EMA filter).

NO STOP-LOSS, NO TAKE-PROFIT BY DEFAULT (enableSL=false, enableTP=false
in the original) - a genuine "hold until the trend reverses" system,
preserved faithfully rather than forced onto an R-multiple template: an
effectively-unreachable SL (50x the entry bar's own ATR - large enough
that hitting it inside a single trend leg on Gold/Silver/BTC M15/H1 data
is not something a live trader would ever see) stands in for "off"
(common.py's engine always evaluates SOME stop, so this disclosed large
value is the practical equivalent of none), target_r=0 so no take-
profit level exists. The real exit mechanism is the opposite flip:
ANY bear flip closes a long, ANY bull flip closes a short, REGARDLESS
of whether that new flip itself also qualifies as a fresh entry
(EMA-filtered) - a genuinely different close-condition from the two
earlier SuperTrend/EMA-cross scripts, which only reverse-and-close on a
QUALIFYING opposite signal.

FROZEN-DEFAULTS TEST FIRST (no search - the script's own shipped
factor/ATR-length/EMA-length, exactly as given), then a modest walk-
forward search for completeness, matching every other file in this
folder.

GRID (K=27, literal): FACTOR in {1.2,1.8,2.5} x ATR_PERIOD in {7,10,14}
x EMA_LEN in {100,200,300} - the frozen defaults (1.8, 10, 200) are one
of the 27 cells, printed separately below the grid table.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

FACTORS = [1.2, 1.8, 2.5]
ATR_PERIODS = [7, 10, 14]
EMA_LENS = [100, 200, 300]
FROZEN = (1.8, 10, 200)
NO_STOP_ATR_MULT = 50.0


def compute_supertrend(h, l, c, atr, mult):
    n = len(c)
    src = (h + l) / 2.0
    st = np.full(n, np.nan)
    dirn = np.ones(n, dtype=np.int64)
    dir_now = 1
    band_now = src[0] - mult * (atr[0] if not np.isnan(atr[0]) else 0.0)
    for i in range(n):
        a = atr[i] if not np.isnan(atr[i]) else 0.0
        upper = src[i] + mult * a
        lower = src[i] - mult * a
        if dir_now == 1:
            band_now = max(lower, band_now)
            if c[i] < band_now:
                dir_now = -1
                band_now = upper
        else:
            band_now = min(upper, band_now)
            if c[i] > band_now:
                dir_now = 1
                band_now = lower
        st[i] = band_now
        dirn[i] = dir_now
    return st, dirn


def run_one(b, factor, atr_period, ema_len):
    atr = C.wilder_atr(b.high, b.low, b.close, atr_period)
    st, dirn = compute_supertrend(b.high, b.low, b.close, atr, factor)
    dir_prev = np.concatenate(([dirn[0]], dirn[:-1]))
    flip_bull = (dirn == 1) & (dir_prev == -1)
    flip_bear = (dirn == -1) & (dir_prev == 1)
    trend_ema = C.ema(b.close, ema_len)

    long_cond = flip_bull & (b.close > trend_ema)
    short_cond = flip_bear & (b.close < trend_ema)

    il = np.where(long_cond)[0]
    is_ = np.where(short_cond)[0]
    valid_l = ~np.isnan(atr[il]) & (atr[il] > 0)
    valid_s = ~np.isnan(atr[is_]) & (atr[is_] > 0)
    il, is_ = il[valid_l], is_[valid_s]
    dist_l = NO_STOP_ATR_MULT * atr[il]
    dist_s = NO_STOP_ATR_MULT * atr[is_]
    sig_bar = np.concatenate((il, is_)).astype(np.int64)
    sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
    sig_dist = np.concatenate((dist_l, dist_s))
    order = np.argsort(sig_bar, kind="stable")
    sig_bar, sig_dir, sig_dist = sig_bar[order], sig_dir[order], sig_dist[order]

    ex = dict(target_r=0.0, max_hold=100000, trail_atr=0.0, exit_long=flip_bear, exit_short=flip_bull)
    return sig_bar, sig_dir, sig_dist, ex


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    df1h = C.resample(df15, "1h")
    b = C.Bars(df1h, point, symbol)
    log(f"\n{'='*90}\n{symbol} H1 -- SuperTrend + EMA Trend Filter (FACTOR, ATR_PERIOD, EMA_LEN)\n{b.describe()}")

    fb, fd, fdist, fex = run_one(b, *FROZEN)
    exargs_f = (fex["target_r"], fex["max_hold"], fex["trail_atr"], fex["exit_long"], fex["exit_short"])
    r_is = C.sim_signals(fb, fd, fdist, b.open, b.high, b.low, b.close, b.spread_px, b.atr, *exargs_f, b.is_lo, b.is_hi)
    r_oos = C.sim_signals(fb, fd, fdist, b.open, b.high, b.low, b.close, b.spread_px, b.atr, *exargs_f, b.oos_lo, b.oos_hi)
    log(f"FROZEN DEFAULTS {FROZEN} (no search): IS n={len(r_is[3])} %PF={C.pct_pf(r_is[3]):.3f}  |  "
        f"OOS n={len(r_oos[3])} %PF={C.pct_pf(r_oos[3]):.3f}")

    grid = list(itertools.product(FACTORS, ATR_PERIODS, EMA_LENS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    for cfg in grid:
        factor, atr_period, ema_len = cfg
        sig_bar, sig_dir, sig_dist, ex = run_one(b, factor, atr_period, ema_len)
        exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          *exargs, b.is_lo, b.is_hi)
        n_tr, pnl = len(r[3]), r[3]
        if n_tr < 100:
            continue
        rows.append(dict(cfg=cfg, n=n_tr, pf=C.pct_pf(pnl), sig_bar=sig_bar, sig_dir=sig_dir, sig_dist=sig_dist, ex=ex))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=100. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    sig_bar, sig_dir, sig_dist, ex = best["sig_bar"], best["sig_dir"], best["sig_dist"], best["ex"]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
    r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                      *exargs, b.oos_lo, b.oos_hi)
    oos_pnl, oos_dir, oos_dist = r[3], r[2], r[4]
    n_oos = len(oos_pnl)
    if n_oos == 0:
        log("No OOS trades."); return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (0 OOS trades)")
    oos_pf = C.pct_pf(oos_pnl)
    log(f"OOS (untouched): n={n_oos}  win%={100*(oos_pnl>0).mean():.1f}  %PF={oos_pf:.3f}  sum%={100*oos_pnl.sum():.1f}")
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
                pctile=pctile, p1=p1, pK=pK, verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/btc_supertrend_ema_h1_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("BTCUSD", "GOLD", "SILVER")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
