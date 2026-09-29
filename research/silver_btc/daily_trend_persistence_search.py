"""
Daily/weekly trend-persistence test - the user's own hypothesis: "if
price goes uptrend it usually goes overall up for the day and vice
versa" - does the recent trailing trend (measured on daily bars, as of
yesterday's close) predict TODAY's direction?

SIGNAL: at each day's open, compute the trailing N-day close-to-close
return as of the PREVIOUS day's close (no lookahead - only data known
before today's open). If positive, go long at today's open; if
negative, go short. A daily Stochastic(14,3,3) reading (as of yesterday's
close) is tested as an alternative/filter version of the same idea,
since the user specifically asked about it.

EXIT: whichever comes first - an ATR-multiple stop (tight, per the
user's stated preference), or the end of the trading day (23:45 M15 bar,
i.e. hold the position for that one day only, matching the "for the
day" framing of the hypothesis exactly).

GRID (K=24, literal): TREND_LOOKBACK_DAYS in {1,3,5,10} x STOP_ATR_MULT
in {0.5,1.0,1.5} x SIGNAL_MODE in {"trend","stochastic"}.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

TREND_LOOKBACK_DAYS = [1, 3, 5, 10]
STOP_ATR_MULTS = [0.5, 1.0, 1.5]
SIGNAL_MODES = ["trend", "stochastic"]
STOCH_LEN, STOCH_SMOOTH, STOCH_D = 14, 3, 3


def wilder_stoch(h, l, c, k_len, k_smooth, d_len):
    ll = pd.Series(l).rolling(k_len, min_periods=k_len).min().values
    hh = pd.Series(h).rolling(k_len, min_periods=k_len).max().values
    with np.errstate(invalid="ignore", divide="ignore"):
        raw_k = 100.0 * (c - ll) / (hh - ll)
    k = pd.Series(raw_k).rolling(k_smooth, min_periods=k_smooth).mean().values
    d = pd.Series(k).rolling(d_len, min_periods=d_len).mean().values
    return k, d


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    dfd = C.resample(df15, "1D")
    d_close, d_open, d_high, d_low = dfd["close"].values, dfd["open"].values, dfd["high"].values, dfd["low"].values
    d_time = pd.to_datetime(dfd["time"]).values
    n_d = len(dfd)

    stoch_k, stoch_d = wilder_stoch(d_high, d_low, d_close, STOCH_LEN, STOCH_SMOOTH, STOCH_D)
    d_atr = C.wilder_atr(d_high, d_low, d_close, 14)  # DAILY-scale ATR - a day-long hold needs a day-scale stop,
    # not the M15 ATR(14) used everywhere else in this project (that's ~3.5 hours of range, far too tight to
    # survive a full trading day and would get stopped out almost regardless of directional accuracy)

    date_arr = df15["time"].dt.date.values
    is_reset = np.concatenate(([True], date_arr[1:] != date_arr[:-1]))
    day_open_bar = np.where(is_reset)[0]
    m15_date = pd.to_datetime(date_arr)
    d_date = pd.to_datetime(d_time).normalize()

    log(f"\n{'='*90}\n{symbol} M15/D1 -- Daily trend persistence (TREND_LOOKBACK_DAYS, STOP_ATR_MULT, SIGNAL_MODE)\n{b.describe()}")

    grid = list(itertools.product(TREND_LOOKBACK_DAYS, STOP_ATR_MULTS, SIGNAL_MODES))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    day_idx_of_bar = np.searchsorted(d_date, pd.to_datetime(date_arr))
    day_idx_of_bar = np.clip(day_idx_of_bar, 0, n_d - 1)

    rows = []
    cache = {}
    for cfg in grid:
        lookback, stop_mult, mode = cfg
        if mode == "trend":
            # trailing N-day close-to-close return, known as of yesterday's close (index d-1) -> used for day d
            trail_ret = np.full(n_d, np.nan)
            for d in range(lookback + 1, n_d):
                trail_ret[d] = (d_close[d - 1] - d_close[d - 1 - lookback]) / d_close[d - 1 - lookback]
            dir_d = np.sign(trail_ret)
        else:
            k_shift = np.concatenate(([np.nan], stoch_k[:-1]))
            dir_d = np.where(k_shift > 50, 1.0, np.where(k_shift < 50, -1.0, np.nan))

        sig_bar_list, sig_dir_list, sig_dist_list = [], [], []
        for i in day_open_bar:
            d = day_idx_of_bar[i]
            if d <= 0 or d >= n_d or np.isnan(dir_d[d]):
                continue
            a = d_atr[d - 1]  # previous day's DAILY ATR - known before today's open, no lookahead
            if np.isnan(a) or a <= 0:
                continue
            sig_bar_list.append(i)
            sig_dir_list.append(dir_d[d])
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
    out_path = "/home/user/test-project/research/silver_btc/daily_trend_persistence_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
