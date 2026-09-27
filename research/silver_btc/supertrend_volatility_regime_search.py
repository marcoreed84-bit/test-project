"""
"Supertrend + Volatility Regime Switch" (the user's eleventh pasted
Pine v6 strategy): a plain SuperTrend flip whose ATR MULTIPLIER
switches width by ADX regime - tight (1.75x) while trending, wide
(4.5x) while choppy, with hysteresis (a middle ADX band between the two
thresholds holds the last regime rather than flapping). New entries are
blocked outright during a choppy bar (the RAW instantaneous ADX<chop_th
check, not the hysteresis-smoothed regime). No stop-loss or take-profit
by default (useTrailing=false) - a genuine hold-until-opposite-
qualifying-flip system, same as the BTC SuperTrend+EMA script's default
behavior, modeled the same way here (a practically-unreachable stop
stands in for "none", target_r=0). Third distinct SuperTrend variant
tested this session: supertrend_regime_search.py used a 5-factor 0-100
confluence SCORE with a fixed EMA(50) trend filter; btc_supertrend_
ema_h1_search.py used a fixed factor with an EMA(200) filter; this one
has no trend-EMA at all - only the ADX-driven band-width switch and an
entry-time chop block.

PORTED FAITHFULLY: Wilder ADX (common.wilder_adx, matching ta.dmi), the
hysteresis regime state machine (vectorized: a regime code that only
updates on a crossing of either threshold, forward-filled through the
neutral band in between), the tight/wide multiplier switch feeding a
per-bar-varying SuperTrend band (same recursive construction as the
other two SuperTrend scripts, now with a bar-varying multiplier array),
the RAW (non-hysteresis) chop entry-block, and the "opposite qualifying
signal closes the position" exit (exit_long = the short-signal array,
exit_short = the long-signal array - both gated by the same entries-
allowed chop block, since that's exactly what strategy.entry's auto-
reverse-and-close behavior does here).

GRID (K=27, literal): ADX_TREND_TH in {20,25,30} x TIGHT_MULT in
{1.25,1.75,2.5} x WIDE_MULT in {3.5,4.5,6.0}. ADX_CHOP_TH=20,
ATR_LEN=10 are the script's own defaults, fixed to keep K honest;
disableChop=true and flattenOnChop=false/useTrailing=false (both
script defaults) are also left as-is.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

ADX_TREND_THS = [20.0, 25.0, 30.0]
TIGHT_MULTS = [1.25, 1.75, 2.5]
WIDE_MULTS = [3.5, 4.5, 6.0]
ADX_CHOP_TH = 20.0
ADX_LEN = 14
ATR_LEN = 10
NO_STOP_ATR_MULT = 50.0


def compute_supertrend_var_mult(h, l, c, atr, mult_arr):
    n = len(c)
    src = (h + l) / 2.0
    st = np.full(n, np.nan)
    dirn = np.ones(n, dtype=np.int64)
    dir_now = 1
    band_now = src[0] - mult_arr[0] * (atr[0] if not np.isnan(atr[0]) else 0.0)
    for i in range(n):
        a = atr[i] if not np.isnan(atr[i]) else 0.0
        m = mult_arr[i]
        upper = src[i] + m * a
        lower = src[i] - m * a
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


def run_one(b, adx, trend_th, tight_mult, wide_mult):
    trending = adx > trend_th
    choppy = adx < ADX_CHOP_TH
    code = np.where(trending, 1.0, np.where(choppy, -1.0, np.nan))
    code = pd.Series(code).ffill().fillna(1.0).values  # var regime starts effectively "trending-multiplier" (tightMult default)
    mult_arr = np.where(code == 1.0, tight_mult, wide_mult)

    atr = C.wilder_atr(b.high, b.low, b.close, ATR_LEN)
    st, dirn = compute_supertrend_var_mult(b.high, b.low, b.close, atr, mult_arr)
    dir_prev = np.concatenate(([dirn[0]], dirn[:-1]))
    bull_flip = (dirn == 1) & (dir_prev == -1)
    bear_flip = (dirn == -1) & (dir_prev == 1)

    entries_allowed = ~choppy  # disableChop=true fixed: raw instantaneous ADX check, not hysteresis regime
    long_sig = bull_flip & entries_allowed
    short_sig = bear_flip & entries_allowed

    il = np.where(long_sig)[0]
    is_ = np.where(short_sig)[0]
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

    ex = dict(target_r=0.0, max_hold=100000, trail_atr=0.0, exit_long=short_sig, exit_short=long_sig)
    return sig_bar, sig_dir, sig_dist, ex


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- SuperTrend + Volatility Regime Switch (ADX_TREND_TH, TIGHT_MULT, WIDE_MULT)\n"
        f"{b.describe()}")

    adx, pdi, mdi = C.wilder_adx(b.high, b.low, b.close, ADX_LEN)

    grid = list(itertools.product(ADX_TREND_THS, TIGHT_MULTS, WIDE_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    for cfg in grid:
        trend_th, tight_mult, wide_mult = cfg
        sig_bar, sig_dir, sig_dist, ex = run_one(b, adx, trend_th, tight_mult, wide_mult)
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
    out_path = "/home/user/test-project/research/silver_btc/supertrend_volatility_regime_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
