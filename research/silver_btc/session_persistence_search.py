"""
Session-to-session reaction test - the user's idea: "look at the different
sessions and how they react daily." Same directional-bias family as
daily_trend_persistence_search.py and htf_ma_position_search.py, but at
session granularity: does one session's move predict the NEXT session's
direction (Asian -> London, London -> New York)?

Sessions are hour buckets on the platform time already in this project's
M15 data (no separate timezone conversion available/needed - the buckets
just have to be consistent day to day, which they are since the data has
a fixed offset throughout):
  Asian:   00:00-06:59
  London:  07:00-12:59
  New York:13:00-20:59
  (21:00-23:59 excluded from session definitions - session close overlap)

SIGNAL: at the start of the destination session, look at the PRECEDING
session's own return (open->close within that session, that day). Long if
positive, short if negative. MIN_MOVE_ATR optionally requires that move to
be at least that many session-ATR to count as a "real" (not noise) session
move - the "strong" reaction idea, same shape as the MA distance filter.

Session-ATR: a Wilder-style rolling mean of that specific session's own
daily range (high-low within the session), over the trailing 14
occurrences BEFORE the current day - a properly session-scaled measure,
not the M15 ATR(14) (too tight for a multi-hour hold) or the daily ATR
(too wide for a single session).

EXIT: stop-distance x session-ATR of the DESTINATION session, or the end
of that destination session, whichever comes first.

GRID (K=12, literal): SESSION_PAIR in {Asian->London, London->NY} x
STOP_ATR_MULT in {0.5,1.0,1.5} x MIN_MOVE_ATR in {0.0,0.5}.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

SESSION_PAIRS = [(0, 1), (1, 2)]  # (source session id, destination session id)
STOP_ATR_MULTS = [0.5, 1.0, 1.5]
MIN_MOVE_ATRS = [0.0, 0.5]
SESSION_NAMES = {0: "Asian", 1: "London", 2: "NewYork"}


def session_of_hour(hour):
    sess = np.full(len(hour), -1, dtype=np.int64)
    sess[(hour >= 0) & (hour < 7)] = 0
    sess[(hour >= 7) & (hour < 13)] = 1
    sess[(hour >= 13) & (hour < 21)] = 2
    return sess


def build_session_panel(df15, b):
    hour = df15["time"].dt.hour.values
    date_arr = df15["time"].dt.date.values
    sess_id = session_of_hour(hour)
    bar_idx = np.arange(b.n)

    d = pd.DataFrame({"date": date_arr, "sess": sess_id, "bar": bar_idx,
                       "o": b.open, "h": b.high, "l": b.low, "c": b.close})
    d = d[d["sess"] >= 0]
    g = d.groupby(["date", "sess"], sort=True).agg(
        start_bar=("bar", "min"), end_bar=("bar", "max"),
        o=("o", "first"), c=("c", "last"), h=("h", "max"), l=("l", "min")).reset_index()

    dates = np.sort(d["date"].unique())
    date_to_row = {dt: i for i, dt in enumerate(dates)}
    n_days = len(dates)

    panel = {}
    for s in (0, 1, 2):
        gs = g[g["sess"] == s]
        start_bar = np.full(n_days, -1, dtype=np.int64)
        end_bar = np.full(n_days, -1, dtype=np.int64)
        ret = np.full(n_days, np.nan)
        rng = np.full(n_days, np.nan)
        for _, row in gs.iterrows():
            i = date_to_row[row["date"]]
            start_bar[i] = row["start_bar"]
            end_bar[i] = row["end_bar"]
            ret[i] = (row["c"] - row["o"]) / row["o"]
            rng[i] = row["h"] - row["l"]
        # session-ATR: Wilder-style rolling mean of this session's own range, trailing
        # 14 occurrences BEFORE today (shifted so today's own range is never used to size today's trade)
        rng_shift = np.concatenate(([np.nan], rng[:-1]))
        atr = pd.Series(rng_shift).rolling(14, min_periods=14).mean().values
        panel[s] = dict(start_bar=start_bar, end_bar=end_bar, ret=ret, rng=rng, atr=atr)
    return panel, n_days


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    panel, n_days = build_session_panel(df15, b)

    log(f"\n{'='*90}\n{symbol} M15 -- Session-to-session reaction (SESSION_PAIR, STOP_ATR_MULT, MIN_MOVE_ATR)\n{b.describe()}")

    grid = list(itertools.product(SESSION_PAIRS, STOP_ATR_MULTS, MIN_MOVE_ATRS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    cache = {}
    for cfg in grid:
        (src, dst), stop_mult, min_move = cfg
        srcp, dstp = panel[src], panel[dst]

        src_atr = srcp["atr"]
        # "strength" of the source session's move: its own range vs its own trailing session-ATR
        strength = np.where((src_atr > 0) & ~np.isnan(src_atr), srcp["rng"] / np.where(src_atr > 0, src_atr, np.nan), np.nan)

        valid = (~np.isnan(srcp["ret"])) & (srcp["start_bar"] >= 0) & (dstp["start_bar"] >= 0) & \
                (~np.isnan(dstp["atr"])) & (dstp["atr"] > 0) & (~np.isnan(strength)) & (strength >= min_move)
        idx = np.where(valid)[0]

        sig_bar = dstp["start_bar"][idx].astype(np.int64)
        sig_dir = np.sign(srcp["ret"][idx])
        sig_dist = stop_mult * dstp["atr"][idx]
        keep = sig_dir != 0
        sig_bar, sig_dir, sig_dist = sig_bar[keep], sig_dir[keep], sig_dist[keep]
        order = np.argsort(sig_bar, kind="stable")
        sig_bar, sig_dir, sig_dist = sig_bar[order], sig_dir[order], sig_dist[order]

        dst_end = dstp["end_bar"]
        dst_end_valid = dst_end[dst_end >= 0]
        exit_flag = np.zeros(b.n, dtype=np.bool_)
        exit_flag[dst_end_valid] = True

        ex = dict(target_r=0.0, max_hold=200, trail_atr=0.0, exit_long=exit_flag, exit_short=exit_flag)
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
        pair = (SESSION_NAMES[r['cfg'][0][0]], SESSION_NAMES[r['cfg'][0][1]])
        log(f"   {pair} stop={r['cfg'][1]} min_move={r['cfg'][2]}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}  win%={100*r['win']:.1f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    sig_bar, sig_dir, sig_dist, ex = cache[best["cfg"]]
    exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
    pair = (SESSION_NAMES[best['cfg'][0][0]], SESSION_NAMES[best['cfg'][0][1]])
    log(f"FROZEN WINNER (IS only): {pair} stop={best['cfg'][1]} min_move={best['cfg'][2]}  IS n={best['n']}  "
        f"IS %PF={best['pf']:.3f}  win%={100*best['win']:.1f}")

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
    out_path = "/home/user/test-project/research/silver_btc/session_persistence_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
