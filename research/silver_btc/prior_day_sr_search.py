"""
Previous-day support/resistance test - the user's idea: "previous day's
support and resistance, overall strong support and resistance." Same
rigor pipeline as the rest of this folder.

LEVELS: rolling high/low over the trailing LOOKBACK_DAYS full days (known
before today opens, no lookahead) - LOOKBACK_DAYS=1 is literally
yesterday's high/low; 3 and 5 approximate "stronger" (more-tested,
multi-day) levels the same way this project's other tests use a longer
lookback as a proxy for "strength".

SIGNAL (first qualifying bar each day, within the first 64 M15 bars ~ 16h
of the session):
  - MODE="break": price CLOSES beyond the level (> level_high + buffer, or
    < level_low - buffer) -> trade in the breakout direction.
  - MODE="fade": price's HIGH/LOW TOUCHES the level band (within buffer)
    without closing through it -> trade against the level (short at
    resistance, long at support) - the classic "S/R holds" hypothesis.
Buffer = 0.15 x ATR(14) on both variants, so a "touch"/"break" isn't just
noise around the exact level price.

EXIT: fixed 1.5R target or ATR-multiple stop, first to hit, max hold 200
bars (~50h) - same target/stop shape as vwap_reset_direction/fade_search.py
for a fair comparison against those other "does a level predict direction"
tests already run this session.

GRID (K=18, literal): LOOKBACK_DAYS in {1,3,5} x MODE in {fade,break} x
STOP_ATR_MULT in {0.5,1.0,1.5}.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

LOOKBACK_DAYS = [1, 3, 5]
MODES = ["fade", "break"]
STOP_ATR_MULTS = [0.5, 1.0, 1.5]
TARGET_R = 1.5
BUFFER_ATR = 0.15
SIGNAL_WINDOW_BARS = 64


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    dfd = C.resample(df15, "1D")
    d_high, d_low = dfd["high"].values, dfd["low"].values
    d_time = pd.to_datetime(dfd["time"]).values
    n_d = len(dfd)

    date_arr = df15["time"].dt.date.values
    is_reset = np.concatenate(([True], date_arr[1:] != date_arr[:-1]))
    d_date = pd.to_datetime(d_time).normalize()
    day_idx_of_bar = np.clip(np.searchsorted(d_date, pd.to_datetime(date_arr)), 0, n_d - 1)
    reset_bar = np.where(is_reset, np.arange(b.n), -1)
    reset_bar = np.maximum.accumulate(reset_bar)
    bars_since_reset = np.arange(b.n) - reset_bar

    log(f"\n{'='*90}\n{symbol} M15/D1 -- Prior-day S/R (LOOKBACK_DAYS, MODE, STOP_ATR_MULT)\n{b.describe()}")

    grid = list(itertools.product(LOOKBACK_DAYS, MODES, STOP_ATR_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    level_cache = {}
    for lookback in LOOKBACK_DAYS:
        roll_high = pd.Series(d_high).rolling(lookback, min_periods=lookback).max().values
        roll_low = pd.Series(d_low).rolling(lookback, min_periods=lookback).min().values
        # shift by 1 day: today's level is the rolling high/low ending YESTERDAY
        lvl_high = np.concatenate(([np.nan], roll_high[:-1]))
        lvl_low = np.concatenate(([np.nan], roll_low[:-1]))
        level_cache[lookback] = (lvl_high, lvl_low)

    rows = []
    cache = {}
    for cfg in grid:
        lookback, mode, stop_mult = cfg
        lvl_high_d, lvl_low_d = level_cache[lookback]
        lvl_high = lvl_high_d[day_idx_of_bar]
        lvl_low = lvl_low_d[day_idx_of_bar]
        buf = BUFFER_ATR * b.atr
        in_window = (bars_since_reset >= 1) & (bars_since_reset <= SIGNAL_WINDOW_BARS)

        with np.errstate(invalid="ignore"):
            if mode == "break":
                long_cand = (b.close > lvl_high + buf) & in_window
                short_cand = (b.close < lvl_low - buf) & in_window
            else:  # fade
                touch_high = (b.high >= lvl_high - buf) & (b.close < lvl_high) & in_window
                touch_low = (b.low <= lvl_low + buf) & (b.close > lvl_low) & in_window
                long_cand = touch_low
                short_cand = touch_high

        day_id = np.cumsum(is_reset)
        cand = long_cand | short_cand
        dfb = pd.DataFrame({"day": day_id, "cand": cand.astype(np.int64)})
        cum_in_day = dfb.groupby("day")["cand"].cumsum().values
        first_of_day = cand & (cum_in_day == 1)

        long_sig = first_of_day & long_cand
        short_sig = first_of_day & short_cand

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
    out_path = "/home/user/test-project/research/silver_btc/prior_day_sr_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
