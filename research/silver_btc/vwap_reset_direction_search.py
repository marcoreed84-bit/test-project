"""
VWAP-reset directional signal - tested at the user's explicit request,
same rigor pipeline as everything else in this folder (walk-forward IS/
OOS split, random-timing null with real spread, honest best-of-K).

IDEA: each new calendar day resets the session VWAP (cumulative typical-
price*volume from that day's first bar - reused directly from
research/aurelius/engine.py's session_vwap(), the same construction
already real-MT5-validated against Aurelius_EA.mq5's SessionVWAP()).
Within a window after the reset, the FIRST bar whose close is clearly
above/below that day's VWAP by a buffer (x ATR) is taken as that day's
directional signal - long if above, short if below. One signal per day
by construction (first qualifying bar only).

DESIGN GOAL, per the user's own stated risk preference (different from
most systems in this project, which favor a low win-rate / big-winner
shape): a RELATIVELY TIGHT stop and a real chance of a shorter target,
prioritizing win rate / hit rate over R:R. The grid below spans stop
distances tighter than this project's usual 1.5-4x ATR range, and target
R-multiples that include <=1 (a genuinely different shape than every
other construction tested this session).

GRID (K=27, literal): STOP_ATR_MULT in {0.3,0.5,0.8} x TARGET_R in
{0.5,1.0,1.5} x VWAP_BUFFER_ATR in {0.1,0.2,0.3}. Signal window fixed at
32 bars (~8h on M15, most of a trading day) after each daily reset, to
keep K honest.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import common as C
from engine import session_vwap

SIGNAL_WINDOW_BARS = 32
STOP_ATR_MULTS = [0.3, 0.5, 0.8]
TARGET_RS = [0.5, 1.0, 1.5]
VWAP_BUFFER_ATRS = [0.1, 0.2, 0.3]


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    vwap = session_vwap(df15)
    date_arr = df15["time"].dt.date.values
    is_reset = np.concatenate(([True], date_arr[1:] != date_arr[:-1]))
    reset_bar = np.where(is_reset, np.arange(b.n), -1)
    reset_bar = np.maximum.accumulate(reset_bar)
    bars_since_reset = np.arange(b.n) - reset_bar

    log(f"\n{'='*90}\n{symbol} M15 -- VWAP-reset direction (STOP_ATR_MULT, TARGET_R, VWAP_BUFFER_ATR)\n{b.describe()}")

    grid = list(itertools.product(STOP_ATR_MULTS, TARGET_RS, VWAP_BUFFER_ATRS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    cache = {}
    for cfg in grid:
        stop_mult, target_r, buf_mult = cfg
        buf = buf_mult * b.atr
        with np.errstate(invalid="ignore"):
            above = b.close > (vwap + buf)
            below = b.close < (vwap - buf)
        in_window = (bars_since_reset >= 1) & (bars_since_reset <= SIGNAL_WINDOW_BARS)
        cand = (above | below) & in_window

        # first qualifying bar per day only
        day_id = np.cumsum(is_reset)
        dfb = pd.DataFrame({"day": day_id, "cand": cand.astype(np.int64)})
        cum_in_day = dfb.groupby("day")["cand"].cumsum().values
        first_of_day = cand & (cum_in_day == 1)

        long_sig = first_of_day & above
        short_sig = first_of_day & below

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
        ex = dict(target_r=target_r, max_hold=2000, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)
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
    out_path = "/home/user/test-project/research/silver_btc/vwap_reset_direction_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
