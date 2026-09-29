"""
Higher-timeframe moving-average position test - the user's idea: "look at
where price is on the higher timeframes in relation to strong moving
averages." Same directional-bias shape as the trend-persistence test
(daily_trend_persistence_search.py) - only the signal definition changes.

SIGNAL: at each day's open, compute where the PREVIOUS day's close sits
relative to a daily-scale SMA (known before today's open, no lookahead).
Long if close > MA, short if close < MA. A "strong alignment" filter
(DIST_FILTER_ATR) optionally requires the close to be at least that many
daily-ATR away from the MA - not just barely on one side of it - to test
the "strong" part of the idea specifically.

EXIT: same as the trend-persistence test for a fair comparison - an
ATR-multiple stop or end of trading day, whichever comes first.

GRID (K=24, literal): MA_PERIOD in {20,50,100,200} x STOP_ATR_MULT in
{0.5,1.0,1.5} x DIST_FILTER_ATR in {0.0,1.0}.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

MA_PERIODS = [20, 50, 100, 200]
STOP_ATR_MULTS = [0.5, 1.0, 1.5]
DIST_FILTER_ATRS = [0.0, 1.0]


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    dfd = C.resample(df15, "1D")
    d_close, d_high, d_low = dfd["close"].values, dfd["high"].values, dfd["low"].values
    d_time = pd.to_datetime(dfd["time"]).values
    n_d = len(dfd)

    d_atr = C.wilder_atr(d_high, d_low, d_close, 14)

    date_arr = df15["time"].dt.date.values
    is_reset = np.concatenate(([True], date_arr[1:] != date_arr[:-1]))
    day_open_bar = np.where(is_reset)[0]
    d_date = pd.to_datetime(d_time).normalize()

    log(f"\n{'='*90}\n{symbol} M15/D1 -- HTF MA position (MA_PERIOD, STOP_ATR_MULT, DIST_FILTER_ATR)\n{b.describe()}")

    grid = list(itertools.product(MA_PERIODS, STOP_ATR_MULTS, DIST_FILTER_ATRS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    day_idx_of_bar = np.searchsorted(d_date, pd.to_datetime(date_arr))
    day_idx_of_bar = np.clip(day_idx_of_bar, 0, n_d - 1)

    ma_cache = {}
    for period in MA_PERIODS:
        ma_cache[period] = pd.Series(d_close).rolling(period, min_periods=period).mean().values

    rows = []
    cache = {}
    for cfg in grid:
        period, stop_mult, dist_filter = cfg
        ma = ma_cache[period]
        dist_atr = np.where((d_atr > 0) & ~np.isnan(d_atr), (d_close - ma) / np.where(d_atr > 0, d_atr, np.nan), np.nan)
        dir_d = np.where(np.isnan(ma) | np.isnan(dist_atr), np.nan,
                         np.where(dist_atr >= dist_filter, 1.0,
                                  np.where(dist_atr <= -dist_filter, -1.0, np.nan)))

        sig_bar_list, sig_dir_list, sig_dist_list = [], [], []
        for i in day_open_bar:
            d = day_idx_of_bar[i]
            if d <= 0 or d >= n_d or np.isnan(dir_d[d - 1]):
                continue
            a = d_atr[d - 1]
            if np.isnan(a) or a <= 0:
                continue
            sig_bar_list.append(i)
            sig_dir_list.append(dir_d[d - 1])
            sig_dist_list.append(stop_mult * a)
        sig_bar = np.array(sig_bar_list, dtype=np.int64)
        sig_dir = np.array(sig_dir_list, dtype=np.float64)
        sig_dist = np.array(sig_dist_list, dtype=np.float64)

        eod = np.zeros(b.n, dtype=np.bool_)
        last_bar_of_day = np.concatenate((is_reset[1:], [True]))
        eod[last_bar_of_day] = True

        ex = dict(target_r=0.0, max_hold=100, trail_atr=0.0, exit_long=eod, exit_short=eod)
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
    out_path = "/home/user/test-project/research/silver_btc/htf_ma_position_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
