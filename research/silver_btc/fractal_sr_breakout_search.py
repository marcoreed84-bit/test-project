"""
Direct port of the two uploaded MT5 indicators: Support_and_Resistance.mq5
and Support_and_Resistance_HTF.mq5. Much simpler than anything else tested
this session - no zones, no multi-touch validation, no confirmation
candle. The level is just the price of the MOST RECENT confirmed 5-bar
fractal (2 bars each side, MT5's standard iFractals window - fixed, not a
grid axis, to stay faithful to the real indicator rather than turning it
into another parameter search), held flat until a newer fractal replaces
it. A signal fires the first bar a close crosses that level, having been
on the other side the bar before (same edge-detection the .mq5 alert
logic uses - compares two consecutive closes against the SAME current
level, not against the level at each bar separately).

THREE LEVEL SOURCES (grid axis, this is the actual thing under test):
  - "m15": the fractal-level indicator computed directly on the M15 chart
    (Support_and_Resistance.mq5 as-is).
  - "h4": the SAME construction computed on H4 bars and projected onto
    M15 (Support_and_Resistance_HTF.mq5's exact job) - only the PREVIOUS,
    already-closed H4 bar's fractal is used at any M15 bar, no lookahead
    into the still-forming H4 candle.
  - "both_confirm": an M15 break that ALSO closes beyond the current H4
    level in the same direction - the natural way a trader watching both
    indicators on one chart (which is literally what the HTF file is for)
    would combine them.

EXIT: the original indicator has no trade logic at all (it's an alert
only) - ATR-multiple stop / TARGET_R multiple, same shape as every other
test this session, is added here to make it tradeable.

GRID (K=27, literal): LEVEL_SRC in {m15,h4,both_confirm} x
STOP_ATR_MULT in {0.5,1.0,1.5} x TARGET_R in {1.0,1.5,2.0}.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

FRACTAL_K = 2  # MT5 iFractals: 2 bars each side, fixed (not gridded - stay faithful to the real indicator)
LEVEL_SRCS = ["m15", "h4", "both_confirm"]
STOP_ATR_MULTS = [0.5, 1.0, 1.5]
TARGET_RS = [1.0, 1.5, 2.0]


def build_fractal_levels(h, l, k):
    """Resistance[i] = most recent confirmed fractal high as of bar i (held
    flat until replaced); Support[i] likewise for fractal lows. Exact port
    of Support_and_Resistance.mq5's Resistance[i]/Support[i] buffers."""
    ph, pl = C.pivots(h, l, k)
    n = len(h)
    res = np.full(n, np.nan)
    sup = np.full(n, np.nan)
    last_r, last_s = np.nan, np.nan
    for i in range(n):
        if not np.isnan(ph[i]):
            last_r = ph[i]
        if not np.isnan(pl[i]):
            last_s = pl[i]
        res[i] = last_r
        sup[i] = last_s
    return res, sup


def break_signals(close, level):
    """Fresh cross of the CURRENT level (same comparison the .mq5 alert
    logic uses: Close[trigger] vs Resistance[trigger], Close[trigger+1]
    vs the SAME Resistance[trigger], not the level as of trigger+1)."""
    n = len(close)
    up = np.zeros(n, dtype=np.bool_)
    dn = np.zeros(n, dtype=np.bool_)
    for i in range(1, n):
        lv = level[i]
        if np.isnan(lv):
            continue
        if close[i] > lv and close[i - 1] <= lv:
            up[i] = True
        elif close[i] < lv and close[i - 1] >= lv:
            dn[i] = True
    return up, dn


def project_h4_to_m15(h4_vals, h4_time, m15_time):
    """The HTF file's job: map each M15 bar to the PREVIOUS (already
    closed, known) H4 bar's value - no lookahead into the forming H4 bar."""
    known = np.concatenate(([np.nan], h4_vals[:-1]))
    idx = np.searchsorted(h4_time, m15_time, side="right") - 1
    idx = np.clip(idx, 0, len(h4_time) - 1)
    return known[idx]


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    time_vals = df15["time"].values

    df4h = C.resample(df15, "4h")
    h4_time = df4h["time"].values

    m15_res, m15_sup = build_fractal_levels(b.high, b.low, FRACTAL_K)
    h4_res_raw, h4_sup_raw = build_fractal_levels(df4h["high"].values, df4h["low"].values, FRACTAL_K)
    h4_res_on_m15 = project_h4_to_m15(h4_res_raw, h4_time, time_vals)
    h4_sup_on_m15 = project_h4_to_m15(h4_sup_raw, h4_time, time_vals)

    up_m15 = break_signals(b.close, m15_res)[0]
    dn_m15 = break_signals(b.close, m15_sup)[1]
    up_h4 = break_signals(b.close, h4_res_on_m15)[0]
    dn_h4 = break_signals(b.close, h4_sup_on_m15)[1]

    with np.errstate(invalid="ignore"):
        up_both = up_m15 & (b.close > h4_res_on_m15)
        dn_both = dn_m15 & (b.close < h4_sup_on_m15)

    sig_pool = {
        "m15": (up_m15, dn_m15),
        "h4": (up_h4, dn_h4),
        "both_confirm": (up_both, dn_both),
    }

    log(f"\n{'='*90}\n{symbol} M15/H4 -- Fractal S/R breakout, port of the uploaded .mq5 pair (LEVEL_SRC, STOP_ATR_MULT, TARGET_R)\n{b.describe()}")
    for src, (u, d) in sig_pool.items():
        log(f"  {src}: {u.sum()} up-breaks, {d.sum()} down-breaks (full history)")

    grid = list(itertools.product(LEVEL_SRCS, STOP_ATR_MULTS, TARGET_RS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    cache = {}
    for cfg in grid:
        src, stop_mult, target_r = cfg
        up, dn = sig_pool[src]
        il = np.where(up)[0]
        is_ = np.where(dn)[0]
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
        ex = dict(target_r=target_r, max_hold=200, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)
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
    out_path = "/home/user/test-project/research/silver_btc/fractal_sr_breakout_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
