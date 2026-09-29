"""
Direct port of murrey_math_mt5.mq5 - a Gann-derived static price-grid
technique, unrelated to swing pivots/fractals used everywhere else this
session. Every bar, the last CALC_PERIOD bars' high/low range is snapped
to a "musical octave" scale appropriate to the instrument's own price
magnitude (DetermineFractal - same table as the source .mq5), then
divided into 8 equal eighths (0/8 through 8/8) plus two "overshoot"
lines beyond each end (-2/8, -1/8, +1/8, +2/8) - 13 levels total,
recomputed on a rolling basis (not periodically - the source recomputes
every bar off a trailing window, confirmed by reading its OnCalculate
loop). The indicator's own comments describe 4/8 as the strongest
reversal level, 2/8 and 6/8 as second-strongest, 0/8 and 8/8 as almost
never penetrated ("Ultimate" support/resistance), and the remaining
eighths as weak (stall-and-reverse or continue).

WHICH_LEVELS (grid): "major" = 4/8 only x "major_pivot" = {2/8,4/8,6/8}
x "all_eighths" = {0/8..8/8} (9 levels) - tests whether restricting to
the levels the indicator's own documentation calls strongest actually
does better than using every eighth.

MODE (grid): "fade" = an objective rejection candle (reused from
zone_sr_search.py) at a fresh approach to one of the selected levels -
the reversal read the docs describe. "break" = a fresh close-through
(reused from fractal_sr_breakout_search.py's crossing detector, which
already handles a time-varying level correctly) - tests the alternative
"if it doesn't stall, it continues" read.

GRID (K=18, literal): CALC_PERIOD in {32,64,128} x WHICH_LEVELS in
{major,major_pivot,all_eighths} x MODE in {fade,break}. Stop = 1.0x ATR,
target = 1.5R, both fixed (not gridded) to keep K defensible.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C
from zone_sr_search import rejection_candle
from fractal_sr_breakout_search import break_signals

CALC_PERIODS = [32, 64, 128]
WHICH_LEVELS_OPTS = ["major", "major_pivot", "all_eighths"]
MODES = ["fade", "break"]
STOP_ATR_MULT = 1.0
TARGET_R = 1.5
BUFFER_ATR = 0.15

LEVEL_IDX = {"major": [6], "major_pivot": [4, 6, 8], "all_eighths": list(range(2, 11))}


def determine_fractal(v):
    if v <= 250000 and v > 25000:
        return 100000.0
    if v <= 25000 and v > 2500:
        return 10000.0
    if v <= 2500 and v > 250:
        return 1000.0
    if v <= 250 and v > 25:
        return 100.0
    if v <= 25 and v > 12.5:
        return 12.5
    if v <= 12.5 and v > 6.25:
        return 12.5
    if v <= 6.25 and v > 3.125:
        return 6.25
    if v <= 3.125 and v > 1.5625:
        return 3.125
    if v <= 1.5625 and v > 0.390625:
        return 1.5625
    if v <= 0.390625 and v > 0:
        return 0.1953125
    return 0.0


def murrey_levels_at(mn_low, mx_high):
    fractal = determine_fractal(mx_high)
    if fractal <= 0:
        return None
    rng = mx_high - mn_low
    if rng <= 0:
        return None
    s = np.floor(np.log(fractal / rng) / np.log(2))
    octave = fractal * (0.5 ** s)
    mn = np.floor(mn_low / octave) * octave
    mx = mn + 2 * octave
    if (mn + octave) >= mx_high:
        mx = mn + octave

    x2 = mn + (mx - mn) / 2 if (mn_low >= 3 * (mx - mn) / 16 + mn) and (mx_high <= 9 * (mx - mn) / 16 + mn) else 0
    x1 = mn + (mx - mn) / 2 if (mn_low >= mn - (mx - mn) / 8) and (mx_high <= 5 * (mx - mn) / 8 + mn) and x2 == 0 else 0
    x4 = mn + 3 * (mx - mn) / 4 if (mn_low >= mn + 7 * (mx - mn) / 16) and (mx_high <= 13 * (mx - mn) / 16 + mn) else 0
    x5 = mx if (mn_low >= mn + 3 * (mx - mn) / 8) and (mx_high <= 9 * (mx - mn) / 8 + mn) and x4 == 0 else 0
    x3 = mn + 3 * (mx - mn) / 4 if ((mn_low >= mn + (mx - mn) / 8) and (mx_high <= 7 * (mx - mn) / 8 + mn)
                                     and x1 == 0 and x2 == 0 and x4 == 0 and x5 == 0) else 0
    x6 = mx if (x1 + x2 + x3 + x4 + x5) == 0 else 0
    final_h = x1 + x2 + x3 + x4 + x5 + x6

    y1 = mn if x1 > 0 else 0
    y2 = mn + (mx - mn) / 4 if x2 > 0 else 0
    y3 = mn + (mx - mn) / 4 if x3 > 0 else 0
    y4 = mn + (mx - mn) / 2 if x4 > 0 else 0
    y5 = mn + (mx - mn) / 2 if x5 > 0 else 0
    y6 = mn if (final_h > 0) and (y1 + y2 + y3 + y4 + y5) == 0 else 0
    final_l = y1 + y2 + y3 + y4 + y5 + y6

    dmml = (final_h - final_l) / 8
    if dmml == 0:
        return None
    return np.array([final_l + k * dmml for k in range(-2, 11)])  # 13 levels, index 2..10 = 0/8..8/8


def build_murrey_levels(high, low, calc_period):
    n = len(high)
    roll_lo = pd.Series(low).rolling(calc_period).min().values
    roll_hi = pd.Series(high).rolling(calc_period).max().values
    levels = np.full((n, 13), np.nan)
    for i in range(calc_period - 1, n):
        lv = murrey_levels_at(roll_lo[i], roll_hi[i])
        if lv is not None:
            levels[i] = lv
    return levels


def level_fade_signals(o, h, l, c, atr, level):
    n = len(c)
    long_sig = np.zeros(n, dtype=np.bool_)
    short_sig = np.zeros(n, dtype=np.bool_)
    was_near = False
    for i in range(1, n):
        lv = level[i]
        a = atr[i]
        if np.isnan(lv) or np.isnan(a) or a <= 0:
            was_near = False
            continue
        near = abs(c[i] - lv) <= BUFFER_ATR * a
        if near and not was_near:
            from_below = c[i - 1] < lv
            if from_below and rejection_candle(o, h, l, c, i, False):
                short_sig[i] = True
            elif not from_below and rejection_candle(o, h, l, c, i, True):
                long_sig[i] = True
        was_near = near
    return long_sig, short_sig


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    log(f"\n{'='*90}\n{symbol} M15 -- Murrey Math levels (CALC_PERIOD, WHICH_LEVELS, MODE)\n{b.describe()}")

    grid = list(itertools.product(CALC_PERIODS, WHICH_LEVELS_OPTS, MODES))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    levels_cache = {}
    for cp in CALC_PERIODS:
        levels_cache[cp] = build_murrey_levels(b.high, b.low, cp)

    sig_cache = {}
    for cp, which, mode in itertools.product(CALC_PERIODS, WHICH_LEVELS_OPTS, MODES):
        levels = levels_cache[cp]
        long_acc = np.zeros(b.n, dtype=np.bool_)
        short_acc = np.zeros(b.n, dtype=np.bool_)
        for idx in LEVEL_IDX[which]:
            lvl = levels[:, idx]
            if mode == "fade":
                lg, sh = level_fade_signals(b.open, b.high, b.low, b.close, b.atr, lvl)
            else:
                lg, sh = break_signals(b.close, lvl)
            long_acc |= lg
            short_acc |= sh
        sig_cache[(cp, which, mode)] = (long_acc, short_acc)

    rows = []
    cache = {}
    for cfg in grid:
        cp, which, mode = cfg
        long_sig, short_sig = sig_cache[cfg]
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        valid_l = ~np.isnan(b.atr[il]) & (b.atr[il] > 0)
        valid_s = ~np.isnan(b.atr[is_]) & (b.atr[is_] > 0)
        il, is_ = il[valid_l], is_[valid_s]
        dist_l = STOP_ATR_MULT * b.atr[il]
        dist_s = STOP_ATR_MULT * b.atr[is_]
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
    out_path = "/home/user/test-project/research/silver_btc/murrey_math_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
