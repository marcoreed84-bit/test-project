"""
"MACD Pullback Sniper | Trend + ADX Filtered Strategy" (the user's third
pasted Pine v6 strategy(), by blitz_locked): MACD(12,26,9) signal-line
cross, gated by a 200-EMA trend filter (long only above it, short only
below), a zero-line filter (bullish crosses only below zero, bearish only
above - i.e. only the FIRST cross out of an extreme, not every cross),
and an ADX(14) minimum-strength filter. Exit: ATR(14) stop x slMult,
target at rrRatio x that same distance, OR an opposite MACD cross,
whichever comes first. Genuinely new mechanism for this folder - the
first MACD-based construction tried on Silver/Bitcoin/Gold this session
(Aurelius has an optional MACD filter, never tested as a PRIMARY signal).

Unlike the last two pasted scripts (Range Breakout Targets, Harmonic
XABCD), this one maps directly onto research/silver_btc/common.py's
existing engine with no custom simulator needed: stop/target are set
relative to the ACTUAL fill price (`strategy.position_avg_price` in the
original, i.e. a genuine R-multiple from entry - see _run_one's own
convention, which computes sl/tp the identical way), and "exit on
opposite MACD cross" is exactly a GLOBAL per-bar time-series condition -
precisely what common.py's exit_long/exit_short arrays were built for.

PORTED FAITHFULLY: MACD line/signal (EMA/EMA/EMA, ta.macd), the exact
filter logic (trend EMA, zero-line - only the FIRST cross below/above
zero counts as valid per the script's own zeroLongOk/zeroShortOk gates,
not a sustained-zone filter), ADX via common.wilder_adx (same Wilder
construction the Pine script's ta.dmi ports), the ATR stop/RR target, and
the opposite-cross exit (skipped only when the opposite cross is ALSO a
valid reversal entry, matching `and not shortSignal` / `and not
longSignal` in the original - reproduced here by simply letting a fresh
entry signal override the stale exit on the same bar, same net effect).

NOT ported (irrelevant to whether the construction has an edge): percent-
of-equity position sizing / max-leverage cap (this whole project's %PF
convention is pnl/entry_price, sizing-invariant), slippage=2 (already
covered by this folder's own real spread-cost convention), the
start/end-date input (both this project's IS and OOS windows are already
inside its default 2018-2069 range).

GRID (K=27, literal): SL_MULT in {1.5,2.0,3.0} x RR in {1.5,2.0,3.0} x
ADX_MIN in {15,20,25}. fast/slow/signal (12/26/9), trend EMA (200), ADX
length (14), ATR length (14) are the script's own defaults, fixed (not
tuned) to keep K honest. Trend filter, zero-line filter, ADX filter, and
allow-shorts are all left ON, matching the script's own defaults.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

SL_MULTS = [1.5, 2.0, 3.0]
RRS = [1.5, 2.0, 3.0]
ADX_MINS = [15.0, 20.0, 25.0]
FAST, SLOW, SIGNAL = 12, 26, 9
TREND_LEN = 200
ADX_LEN = 14
MAX_HOLD = 500


def _cross(a, b, up):
    above = a > b
    above_prev = np.concatenate(([False], above[:-1]))
    valid = ~np.isnan(a) & ~np.isnan(b)
    valid_prev = np.concatenate(([False], valid[:-1]))
    edge = above & ~above_prev if up else (~above) & above_prev
    return edge & valid & valid_prev


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- MACD Pullback Sniper (SL_MULT, RR, ADX_MIN)\n{b.describe()}")

    macd_line = C.ema(b.close, FAST) - C.ema(b.close, SLOW)
    signal_line = C.ema(macd_line, SIGNAL)
    trend_ema = C.ema(b.close, TREND_LEN)
    adx, pdi, mdi = C.wilder_adx(b.high, b.low, b.close, ADX_LEN)

    bull_cross = _cross(macd_line, signal_line, up=True)
    bear_cross = _cross(macd_line, signal_line, up=False)
    trend_long_ok = b.close > trend_ema
    trend_short_ok = b.close < trend_ema
    zero_long_ok = macd_line < 0
    zero_short_ok = macd_line > 0

    grid = list(itertools.product(SL_MULTS, RRS, ADX_MINS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    for cfg in grid:
        sl_mult, rr, adx_min = cfg
        adx_ok = adx > adx_min
        long_sig = bull_cross & trend_long_ok & zero_long_ok & adx_ok
        short_sig = bear_cross & trend_short_ok & zero_short_ok & adx_ok

        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        valid_l = ~np.isnan(b.atr[il]) & (b.atr[il] > 0)
        valid_s = ~np.isnan(b.atr[is_]) & (b.atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = sl_mult * b.atr[il]
        dist_s = sl_mult * b.atr[is_]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        sig_bar, sig_dir, sig_dist = sig_bar[order], sig_dir[order], sig_dist[order]

        ex = dict(target_r=rr, max_hold=MAX_HOLD, trail_atr=0.0, exit_long=bear_cross, exit_short=bull_cross)
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"],
                          b.is_lo, b.is_hi)
        n, pnl = len(r[3]), r[3]
        if n < 100:
            continue
        rows.append(dict(cfg=cfg, n=n, pf=C.pct_pf(pnl), sig_bar=sig_bar, sig_dir=sig_dir, sig_dist=sig_dist, ex=ex))

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
    out_path = "/home/user/test-project/research/silver_btc/macd_pullback_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
