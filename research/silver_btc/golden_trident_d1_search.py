"""
"Golden Trident | Swing-Anchored VWAP Trend System" (the user's tenth
pasted Pine v6 strategy) - explicitly named, designed and tuned FOR
GOLD on the DAILY timeframe, both honored here (tested on D1, resampled
losslessly from real M15; Gold prioritized, Silver/BTC still checked on
their own D1 data for consistency). LONG-ONLY BY DESIGN (allowShort
defaults false - the script's own header states this is deliberate,
"gold's dominant long-term trend", not an oversight), so the primary
test here is long-only, matching the script's own default intent.

DIRECTION MECHANISM: genuinely different from every swing/pivot
construction tried this session - `dir` is NOT a confirmed-pivot flip,
it's "which extreme was set more recently": dir=1 (up) whenever the
most recent new N-bar high (ta.highestbars(high,len)==0) happened more
recently than the most recent new N-bar low, dir=-1 otherwise. No
confirmation lag at all (today's own bar can flip it), fully
vectorizable (bar i sets a new high iff high[i] equals the trailing
N-bar rolling max) - ported exactly that way here via rolling-max/min
comparison + forward-fill of the "last flip bar" index, no loop needed.

A GENUINE FINDING WORTH FLAGGING: the script's own anchored-VWAP
(reset every time `dir` flips) is PURELY DECORATIVE in the real
strategy() code - it is plotted but never referenced by longCond,
shortCond, or any exit condition anywhere in the script. A faithful
trading test therefore has nothing to port for it; only `dir` (via the
highest/lowest-bars mechanism above), the EMA(200) trend filter, and
the ATR-based chop filter actually gate entries.

PORTED FAITHFULLY: the highest/lowest-bars direction flip, the EMA
trend filter, the chop filter ((highest(high,N)-lowest(low,N)) >
ATR(N)*mult), the edge-triggered entry (longCond & not longCond[1]),
exit on a structure flip OR the wide ATR backstop (a REAL protective
stop by design, not a "practically unreachable" placeholder like the
BTC SuperTrend script's - 8x ATR here is meant to be a genuine
catastrophe-only exit and is modeled as exactly that).

FROZEN-DEFAULTS TEST FIRST (SWING_LEN=30, ATR_STOP_MULT=8.0,
RANGE_MULT=0.8 - the script's own shipped values, no search), then a
modest walk-forward search for completeness.

GRID (K=27, literal): SWING_LEN in {20,30,45} x ATR_STOP_MULT in
{5.0,8.0,12.0} x RANGE_MULT in {0.5,0.8,1.2}. EMA_LEN=200,
ATR_CHOP_LEN=20, ATR_STOP_LEN=14 are the script's own defaults, fixed
to keep K honest. Long-only (allowShort=false, the script's own default
and explicit design intent).
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

SWING_LENS = [20, 30, 45]
ATR_STOP_MULTS = [5.0, 8.0, 12.0]
RANGE_MULTS = [0.5, 0.8, 1.2]
FROZEN = (30, 8.0, 0.8)
EMA_LEN = 200
ATR_CHOP_LEN = 20
ATR_STOP_LEN = 14


def compute_dir(high, low, swing_len):
    n = len(high)
    roll_max = pd.Series(high).rolling(swing_len, min_periods=swing_len).max().values
    roll_min = pd.Series(low).rolling(swing_len, min_periods=swing_len).min().values
    is_new_high = high >= roll_max
    is_new_low = low <= roll_min
    ph_bar = np.where(is_new_high, np.arange(n), np.nan)
    pl_bar = np.where(is_new_low, np.arange(n), np.nan)
    ph_bar = pd.Series(ph_bar).ffill().values
    pl_bar = pd.Series(pl_bar).ffill().values
    dir_ = np.where(ph_bar > pl_bar, 1, -1)
    valid = ~np.isnan(roll_max) & ~np.isnan(roll_min)
    return dir_, valid


def run_one(b, swing_len, atr_stop_mult, range_mult):
    dir_, valid = compute_dir(b.high, b.low, swing_len)
    dir_prev = np.concatenate(([dir_[0]], dir_[:-1]))

    ema_trend = C.ema(b.close, EMA_LEN)
    atr_chop = C.wilder_atr(b.high, b.low, b.close, ATR_CHOP_LEN)
    hi_n = pd.Series(b.high).rolling(ATR_CHOP_LEN, min_periods=ATR_CHOP_LEN).max().values
    lo_n = pd.Series(b.low).rolling(ATR_CHOP_LEN, min_periods=ATR_CHOP_LEN).min().values
    range_ok = (hi_n - lo_n) > atr_chop * range_mult
    atr_stop = C.wilder_atr(b.high, b.low, b.close, ATR_STOP_LEN)

    trend_long_ok = b.close > ema_trend
    long_cond = valid & (dir_ == 1) & trend_long_ok & range_ok
    long_cond_prev = np.concatenate(([False], long_cond[:-1]))
    long_trigger = long_cond & ~long_cond_prev

    flip_to_down = valid & (dir_ == -1) & (dir_prev == 1)

    il = np.where(long_trigger)[0]
    valid_l = ~np.isnan(atr_stop[il]) & (atr_stop[il] > 0)
    il = il[valid_l]
    dist_l = atr_stop_mult * atr_stop[il]
    no_exit = np.zeros(b.n, dtype=np.bool_)

    ex = dict(target_r=0.0, max_hold=100000, trail_atr=0.0, exit_long=flip_to_down, exit_short=no_exit)
    return il.astype(np.int64), np.ones(len(il)), dist_l, ex


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    df1d = C.resample(df15, "1D")
    b = C.Bars(df1d, point, symbol)
    log(f"\n{'='*90}\n{symbol} D1 -- Golden Trident, long-only (SWING_LEN, ATR_STOP_MULT, RANGE_MULT)\n{b.describe()}")

    fb, fd, fdist, fex = run_one(b, *FROZEN)
    exargs_f = (fex["target_r"], fex["max_hold"], fex["trail_atr"], fex["exit_long"], fex["exit_short"])
    r_is = C.sim_signals(fb, fd, fdist, b.open, b.high, b.low, b.close, b.spread_px, b.atr, *exargs_f, b.is_lo, b.is_hi)
    r_oos = C.sim_signals(fb, fd, fdist, b.open, b.high, b.low, b.close, b.spread_px, b.atr, *exargs_f, b.oos_lo, b.oos_hi)
    log(f"FROZEN DEFAULTS {FROZEN} (no search): IS n={len(r_is[3])} %PF={C.pct_pf(r_is[3]):.3f}  |  "
        f"OOS n={len(r_oos[3])} %PF={C.pct_pf(r_oos[3]):.3f}")

    grid = list(itertools.product(SWING_LENS, ATR_STOP_MULTS, RANGE_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=30 (D1 -> far fewer trades)\n{'='*90}")

    rows = []
    for cfg in grid:
        swing_len, atr_stop_mult, range_mult = cfg
        sig_bar, sig_dir, sig_dist, ex = run_one(b, swing_len, atr_stop_mult, range_mult)
        exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          *exargs, b.is_lo, b.is_hi)
        n_tr, pnl = len(r[3]), r[3]
        if n_tr < 30:
            continue
        rows.append(dict(cfg=cfg, n=n_tr, pf=C.pct_pf(pnl), sig_bar=sig_bar, sig_dir=sig_dir, sig_dist=sig_dist, ex=ex))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=30. Top 8 by IS %PF:")
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
    if n_oos < 15:
        log("Too few OOS trades -> DOES NOT SURVIVE (insufficient evidence).")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (n<15)")

    allowed = np.ones(b.n, dtype=np.bool_)
    pool, p_fire, mean_n = C.random_pool(b, oos_dist, n_oos, *exargs, b.oos_lo, b.oos_hi, allowed, n_draws=1000)
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
    out_path = "/home/user/test-project/research/silver_btc/golden_trident_d1_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
