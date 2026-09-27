"""
"ICT Daily Liquidity Sweep" (the user's sixth pasted Pine v6 strategy,
PineGen AI): four independent liquidity-sweep triggers - the Asian
session range (00:00-08:00), the London session range (08:00-12:00), the
previous calendar day's high/low, and a rolling N-bar swing high/low -
each fires when price wicks BEYOND that level and closes back INSIDE it
(a stop-hunt/reclaim), entering immediately in the reversal direction.
Forex-flavored (pips, UTC sessions) but Asian/London/NY session structure
genuinely governs Gold/Silver/Bitcoin trading activity too, so the core
mechanism is fair to test as-is (per the user's own point that some of
these scripts carry market-specific baggage worth flagging rather than
silently porting).

Genuinely different from the earlier liquidity-sweep+BOS construction
already tested this session (research/silver_btc/smc_sweep_bos_search.py,
DOES NOT SURVIVE on both Silver/BTC): that one required a sweep AND a
SUBSEQUENT break-of-structure confirmation before entering. This one
enters immediately on the sweep-and-reclaim bar itself - simpler, fires
far more often, no confirmation delay - a mechanically distinct bet on
the same underlying idea.

PORTED FAITHFULLY: the Asian/London session-range LOCKING logic (a
session's high/low is only usable for sweep detection from the bar AFTER
that session ends for the day, not while it's still forming - reproduced
via an hour>=end_h day-transform, matching the original's aLocked/lLocked
state), the previous-day H/L (causal, previous COMPLETED calendar day
only), the swing H/L (N-bar rolling extreme, shifted one bar, excluding
the current bar - same as every other swing construction this session),
and all 4 independent sweep conditions (wick beyond + close back inside).

SIMPLIFIED, disclosed: the original scales out 50%% at TP1 (1.5R) with
the rest running to TP2 - collapsed here to a single full-position exit
at TP2 (the final target) or the original stop (never moved to
breakeven in the original - there is no BE-move logic in this script,
unlike the earlier PA Patterns script), same %%PF-per-whole-trade
convention used everywhere in this folder. This maps cleanly onto
common.py's existing R-multiple engine (dist = stop distance at the
signal bar, target_r = TP2's R-multiple) - no custom simulator needed.
The hard "close at end-of-window" time exit is approximated by a
generous MAX_HOLD safety cap rather than modeled as an exact calendar
cutoff (disclosed, same simplification used in the last two scripts).

GRID (K=27, literal): TP2_RR in {2.0,3.0,4.0} x SL_BUFFER_TICKS in
{1.0,3.0,5.0} x SWING_LENGTH in {5,10,20}. Window = all hours (the
script's own default startHour=0/endHour=23), all 4 sweep types always
enabled (the script's own defaults).
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

TP2_RRS = [2.0, 3.0, 4.0]
SL_BUFFER_TICKS = [1.0, 3.0, 5.0]
SWING_LENGTHS = [5, 10, 20]
ASIAN_START, ASIAN_END = 0, 8
LONDON_START, LONDON_END = 8, 12
WINDOW_START, WINDOW_END = 0, 23
MAX_HOLD = 200


def daily_session_extreme(hour_arr, date_arr, high_arr, low_arr, end_h):
    """Locked session high/low: NaN before that session ends for the day,
    the session's own max/min from `end_h` onward through the rest of the
    calendar day - matches the original's aLocked/lLocked state exactly."""
    start_h = ASIAN_START if end_h == ASIAN_END else LONDON_START
    df = pd.DataFrame({"date": date_arr, "hour": hour_arr, "high": high_arr, "low": low_arr})
    in_sess = (df["hour"] >= start_h) & (df["hour"] < end_h)
    day_high = df["high"].where(in_sess).groupby(df["date"]).transform("max")
    day_low = df["low"].where(in_sess).groupby(df["date"]).transform("min")
    locked_high = np.where(hour_arr >= end_h, day_high.values, np.nan)
    locked_low = np.where(hour_arr >= end_h, day_low.values, np.nan)
    return locked_high, locked_low


def prev_day_extreme(date_arr, high_arr, low_arr):
    daily = pd.DataFrame({"date": date_arr, "high": high_arr, "low": low_arr}) \
        .groupby("date").agg(high=("high", "max"), low=("low", "min")).reset_index()
    daily["pdHigh"] = daily["high"].shift(1)
    daily["pdLow"] = daily["low"].shift(1)
    map_h = dict(zip(daily["date"], daily["pdHigh"]))
    map_l = dict(zip(daily["date"], daily["pdLow"]))
    pd_high = pd.Series(date_arr).map(map_h).values.astype(float)
    pd_low = pd.Series(date_arr).map(map_l).values.astype(float)
    return pd_high, pd_low


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- Liquidity Sweep + Reclaim (TP2_RR, SL_BUFFER_TICKS, SWING_LENGTH)\n{b.describe()}")

    time_idx = pd.to_datetime(b.time)
    hour_arr = time_idx.hour.values
    date_arr = time_idx.normalize().values

    a_high, a_low = daily_session_extreme(hour_arr, date_arr, b.high, b.low, ASIAN_END)
    l_high, l_low = daily_session_extreme(hour_arr, date_arr, b.high, b.low, LONDON_END)
    pd_high, pd_low = prev_day_extreme(date_arr, b.high, b.low)
    in_window = (hour_arr >= WINDOW_START) & (hour_arr < WINDOW_END)

    with np.errstate(invalid="ignore"):
        asian_ssl = in_window & ~np.isnan(a_low) & (b.low < a_low) & (b.close > a_low)
        asian_bsl = in_window & ~np.isnan(a_high) & (b.high > a_high) & (b.close < a_high)
        london_ssl = in_window & ~np.isnan(l_low) & (b.low < l_low) & (b.close > l_low)
        london_bsl = in_window & ~np.isnan(l_high) & (b.high > l_high) & (b.close < l_high)
        pd_ssl = in_window & ~np.isnan(pd_low) & (b.low < pd_low) & (b.close > pd_low)
        pd_bsl = in_window & ~np.isnan(pd_high) & (b.high > pd_high) & (b.close < pd_high)

    swing_cache = {}
    for sw in SWING_LENGTHS:
        sw_high = pd.Series(b.high).rolling(sw, min_periods=sw).max().shift(1).values
        sw_low = pd.Series(b.low).rolling(sw, min_periods=sw).min().shift(1).values
        with np.errstate(invalid="ignore"):
            swing_ssl = in_window & ~np.isnan(sw_low) & (b.low < sw_low) & (b.close > sw_low)
            swing_bsl = in_window & ~np.isnan(sw_high) & (b.high > sw_high) & (b.close < sw_high)
        swing_cache[sw] = (swing_ssl, swing_bsl)

    grid = list(itertools.product(TP2_RRS, SL_BUFFER_TICKS, SWING_LENGTHS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    for cfg in grid:
        tp2_rr, sl_buf_ticks, sw = cfg
        swing_ssl, swing_bsl = swing_cache[sw]
        go_long = asian_ssl | pd_ssl | london_ssl | swing_ssl
        go_short = asian_bsl | pd_bsl | london_bsl | swing_bsl

        buf = sl_buf_ticks * b.point
        il = np.where(go_long)[0]
        is_ = np.where(go_short)[0]
        sl_l = b.low[il] - buf
        dist_l = b.close[il] - sl_l
        sl_s = b.high[is_] + buf
        dist_s = sl_s - b.close[is_]
        valid_l = dist_l > 0
        valid_s = dist_s > 0
        il, dist_l = il[valid_l], dist_l[valid_l]
        is_, dist_s = is_[valid_s], dist_s[valid_s]

        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((dist_l, dist_s))
        order = np.argsort(sig_bar, kind="stable")
        sig_bar, sig_dir, sig_dist = sig_bar[order], sig_dir[order], sig_dist[order]

        no_exit = np.zeros(b.n, dtype=np.bool_)
        ex = dict(target_r=tp2_rr, max_hold=MAX_HOLD, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)
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
    out_path = "/home/user/test-project/research/silver_btc/liquidity_sweep_reclaim_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
