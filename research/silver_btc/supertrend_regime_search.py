"""
"SuperTrend Regime Confluence" (the user's fifth pasted Pine v6 strategy,
DefinedEdge): a SuperTrend band whose ATR multiplier ADAPTS to a 3-way
regime classification (trending / ranging / volatile, from ADX + an
ATR-vs-its-own-average ratio), entered only on a band-FLIP bar, gated by
a transparent 5-factor 0-100 composite score (volume surge, displacement
beyond the band, EMA-trend alignment, regime quality, prior band distance
held) plus trend/regime/volume filters and a cooldown. ATR stop, R:R
target, always stop-and-reverse on an opposite QUALIFYING signal (any
non-qualifying flip just updates the band silently, per the original's
own logic - it doesn't close a position). Genuinely new mechanism for
this folder: a REGIME-ADAPTIVE trailing band (the stop distance itself
changes shape depending on trend/range/volatility state) gated by an
explicit multi-factor confluence score, not a single fixed-shape filter.

PORTED FAITHFULLY: Wilder ATR/ADX (both already in common.py, matching
Pine's ta.atr/ta.rma-based DMI construction), the regime classifier, the
adaptive-multiplier formula and its 0.5x-2x clamp, the recursive
SuperTrend band itself (inherently sequential - a single explicit O(n)
loop, same convention as this session's other stateful indicators), the
exact 5-factor scoring formula and thresholds, the cooldown, and the
stop-and-reverse-on-qualifying-opposite-signal behavior (a filtered flip
that fails score/trend/regime/volume just updates the band, exactly as
in the original, where only `longEntry`/`shortEntry` trigger a close).

NOT ported (irrelevant to whether the construction has an edge): percent-
of-equity / risk-% position sizing and the no-leverage cap (this
project's %%PF convention is sizing-invariant), the backtest-window input
(both this project's IS/OOS windows already fall inside 2015-2035).
Trailing stop (i_trail) is left OFF, its own default.

GRID (K=27, literal): MIN_SCORE in {50,65,80} x TP_RR in {2.0,2.5,3.0} x
SL_ATR_MULT in {4.0,6.0,8.0}. ATR length (10), base multiplier (3.0),
regime lookback (40), ADX length/threshold (14/20), trend EMA (50),
volume MA (20), cooldown (5) are the script's own defaults, fixed to
keep K honest. Trend/regime/volume filters and both directions stay ON,
matching the script's own defaults; SL mode = ATR, TP mode = RR (both
the script's defaults).
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

MIN_SCORES = [50, 65, 80]
TP_RRS = [2.0, 2.5, 3.0]
SL_ATR_MULTS = [4.0, 6.0, 8.0]

ATR_LEN = 10
BASE_MULT = 3.0
REGIME_LEN = 40
ADX_LEN = 14
ADX_THR = 20.0
TREND_LEN = 50
VOL_LEN = 20
COOLDOWN = 5
MAX_HOLD = 1000


def compute_supertrend(o, h, l, c, atr, adapt_mult):
    """Recursive by construction (each bar's band depends on the last) -
    matches the Pine script's own var-based recursion bar-for-bar."""
    n = len(c)
    src = (h + l) / 2.0
    st_band = np.full(n, np.nan)
    st_dir = np.ones(n, dtype=np.int64)
    dir_now = 1
    band_now = src[0] - adapt_mult[0] * atr[0]
    for i in range(n):
        a = atr[i] if not np.isnan(atr[i]) else 0.0
        upper = src[i] + adapt_mult[i] * a
        lower = src[i] - adapt_mult[i] * a
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
        st_band[i] = band_now
        st_dir[i] = dir_now
    return st_band, st_dir


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- SuperTrend Regime Confluence (MIN_SCORE, TP_RR, SL_ATR_MULT)\n{b.describe()}")

    atr = C.wilder_atr(b.high, b.low, b.close, ATR_LEN)
    atr_ma = C.sma(atr, REGIME_LEN)
    with np.errstate(invalid="ignore", divide="ignore"):
        atr_ratio = np.where(atr_ma > 0, atr / atr_ma, 1.0)
    adx, pdi, mdi = C.wilder_adx(b.high, b.low, b.close, ADX_LEN)

    regime = np.ones(b.n, dtype=np.int64)
    regime[atr_ratio > 1.4] = 2
    ranging = (adx < ADX_THR) & (atr_ratio < 0.9) & (regime != 2)
    regime[ranging] = 0

    adapt_mult = np.full(b.n, BASE_MULT)
    adapt_mult[regime == 2] = BASE_MULT * (1.0 + (atr_ratio[regime == 2] - 1.0) * 0.4)
    adapt_mult[regime == 0] = BASE_MULT * 0.85
    adapt_mult = np.clip(adapt_mult, BASE_MULT * 0.5, BASE_MULT * 2.0)
    adapt_mult = np.nan_to_num(adapt_mult, nan=BASE_MULT)

    st_band, st_dir = compute_supertrend(b.open, b.high, b.low, b.close, atr, adapt_mult)
    dir_prev = np.concatenate(([st_dir[0]], st_dir[:-1]))
    flip = st_dir != dir_prev

    trend_ma = C.ema(b.close, TREND_LEN)
    trend_up = b.close > trend_ma
    trend_dn = b.close < trend_ma
    vol_ma = C.sma(b.vol, VOL_LEN)

    safe_atr = np.where(atr > 0, atr, 0.001)
    v_rat = np.where(vol_ma > 0, b.vol / vol_ma, 1.0)
    f1 = np.select([v_rat >= 2.5, v_rat >= 1.5, v_rat >= 1.0], [20, 14, 8], default=3)
    disp_bull = (b.close - st_band) / safe_atr
    disp_bear = (st_band - b.close) / safe_atr
    f2_bull = np.select([disp_bull >= 1.5, disp_bull >= 0.8, disp_bull >= 0.3, disp_bull > 0],
                        [25, 18, 12, 5], default=0)
    f2_bear = np.select([disp_bear >= 1.5, disp_bear >= 0.8, disp_bear >= 0.3, disp_bear > 0],
                        [25, 18, 12, 5], default=0)
    ema_dist = np.abs(b.close - trend_ma) / safe_atr
    aligned_bull = trend_up
    aligned_bear = trend_dn
    f3_bull = np.where(aligned_bull & (ema_dist > 0.5), 20, np.where(aligned_bull, 14, np.where(ema_dist < 0.3, 8, 2)))
    f3_bear = np.where(aligned_bear & (ema_dist > 0.5), 20, np.where(aligned_bear, 14, np.where(ema_dist < 0.3, 8, 2)))
    f4 = np.select([regime == 1, regime == 2], [15, 8], default=3)
    band_prev = np.concatenate(([np.nan], st_band[:-1]))
    close_prev = np.concatenate(([np.nan], b.close[:-1]))
    prev_dist = np.abs(close_prev - band_prev) / safe_atr
    prev_dist = np.nan_to_num(prev_dist, nan=0.0)
    f5 = np.select([prev_dist >= 2.0, prev_dist >= 1.0, prev_dist >= 0.5], [20, 14, 8], default=3)

    score_bull = np.clip(np.round(f1 + f2_bull + f3_bull + f4 + f5), 0, 100)
    score_bear = np.clip(np.round(f1 + f2_bear + f3_bear + f4 + f5), 0, 100)

    grid = list(itertools.product(MIN_SCORES, TP_RRS, SL_ATR_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    for cfg in grid:
        min_score, tp_rr, sl_mult = cfg
        pass_reg = regime != 0
        pass_vol = b.vol > vol_ma
        long_ok = flip & (st_dir == 1) & (score_bull >= min_score) & trend_up & pass_reg & pass_vol
        short_ok = flip & (st_dir == -1) & (score_bear >= min_score) & trend_dn & pass_reg & pass_vol

        # cooldown: greedily walk bars in order, only keep a signal if >COOLDOWN
        # bars since the last kept signal (either direction) - matches the
        # original's single shared lastEntryBar counter across both sides.
        idx = np.where(long_ok | short_ok)[0]
        if len(idx) == 0:
            continue
        kept = []
        last_bar = -10 ** 9
        for i in idx:
            if i - last_bar > COOLDOWN:
                kept.append(i)
                last_bar = i
        kept = np.array(kept, dtype=np.int64)
        dirs = np.where(long_ok[kept], 1.0, -1.0)
        dist = sl_mult * atr[kept]
        valid = ~np.isnan(dist) & (dist > 0)
        sig_bar, sig_dir, sig_dist = kept[valid], dirs[valid], dist[valid]
        order = np.argsort(sig_bar, kind="stable")
        sig_bar, sig_dir, sig_dist = sig_bar[order], sig_dir[order], sig_dist[order]

        exit_long = np.zeros(b.n, dtype=np.bool_)
        exit_short = np.zeros(b.n, dtype=np.bool_)
        exit_long[sig_bar[sig_dir < 0]] = True
        exit_short[sig_bar[sig_dir > 0]] = True

        ex = dict(target_r=tp_rr, max_hold=MAX_HOLD, trail_atr=0.0, exit_long=exit_long, exit_short=exit_short)
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"],
                          b.is_lo, b.is_hi)
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
    out_path = "/home/user/test-project/research/silver_btc/supertrend_regime_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
