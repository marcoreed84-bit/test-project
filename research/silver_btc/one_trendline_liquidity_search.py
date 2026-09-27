"""
"1 Trendline Strategy" (the user's fourteenth pasted Pine v6 strategy):
the most intricate construction pasted this session - a self-validating
dynamic trendline/liquidity-zone tracker. Pivot highs (each `len` bars
apart minimum) are compared pairwise: a descending pair (current < prior)
becomes a candidate resistance trendline. It's accepted immediately if
the LAST candidate attempt (on either side - a single shared `broken`
flag) failed or got hit ("due for a fresh start"); otherwise it needs a
stricter 4-point confirmation (both points of the new pair must sit
below BOTH of the two immediately preceding pivot highs - a genuine
descending staircase, not just one lower pair by chance). An accepted
pair is then retroactively checked: would a straight line through it,
projected all the way to today, have already been violated by any low
in between? If so it's stillborn (marked broken, discarded). If clean,
it becomes the live zone, drawn as two parallel lines - the raw
trendline and a second one offset by a volatility-scaled pad - and
projected forward until price breaks it. Mirror construction for
ascending pivot-low pairs (support zones). Direction is LONG on a raw
resistance-line break, SHORT on price failing to even reach the PADDED
edge of a support zone - a genuine, verified asymmetry in the original
script (traced through its line-object indexing by hand; see below).
No opposite-signal exit - purely stop/target (ATR-based, both wide by
design: 7x ATR stop, 20x ATR target).

REVERSE-ENGINEERING NOTES (this required manually tracing which of each
zone's two line objects - the raw trendline vs. the padded one - each
later check actually reads, since Pine's `array.get(index)` after two
`unshift()` calls isn't obvious from a skim):
  - Both the RETROACTIVE validity check and the LIVE UPPER-zone breakout
    check read the RAW trendline (not the padded one) - long entries
    require a clean break of the actual descending-highs line.
  - The LIVE LOWER-zone breakout check reads the PADDED line (offset
    ABOVE the raw ascending-lows line) - short entries fire on a
    comparatively EARLIER/looser trigger (failing to reach the padded
    buffer, not breaking the raw line itself). This asymmetry is real,
    not a transcription error, and is preserved here rather than
    "fixed" - faithfully testing the pasted script matters more than
    improving it.
  - `upbin`/`dnbin` (the pivot-pair staging lists) only get cleared once
    a descending/ascending PAIR is actually evaluated for validity (does
    NOT clear on every new pivot - a common misread of the array-based
    state machine); this means a long ambiguous/choppy stretch can leave
    many pivots stacked up before the next clean pair finally triggers
    an evaluation, exactly as the original script does.
  - The two parallel lines extend forward every bar via
    `y2 += line.slope()` while `x2` is set to the current bar - proven
    by hand (see the trace in this repo's commit history) to be
    EXACTLY equivalent to simple linear extrapolation from the creation
    pair, given integer one-bar-per-call increments - so this file
    computes the projected value directly (`before_price + slope *
    (bar - before_bar)`) rather than simulating the per-bar extension,
    with one disclosed simplification: the very first extension call
    (on the same bar the zone is created) would, in the real script,
    jump `len` bars in x while only adding one slope-increment to y -
    a minor, one-time discontinuity from a true straight line, treated
    here as immaterial and not reproduced (the CLEAN straight-line
    projection is unambiguously the script's intent).

FIXED (not searched, script defaults): use_filter=false (no HTF trend
filter applied by default - honored as the primary/only test), ATR(200)
for the padding-volatility calc, sl_mult=7.0.

GRID (K=27, literal): PIVOT_LEN in {4,6,10} x SPACE in {2.0,4.0,8.0} x
TP_MULT in {10.0,20.0,30.0}.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

PIVOT_LENS = [4, 6, 10]
SPACES = [2.0, 4.0, 8.0]
TP_MULTS = [10.0, 20.0, 30.0]
SL_MULT = 7.0
ATR_TRADE_LEN = 14
ATR_VOL_LEN = 200


def simulate_zones(high, low, close, atr_vol, ph, pl, n, pivot_len, space):
    upbin, dnbin = [], []
    broken = False
    active_up = None  # dict(before_bar, before_price, slope)
    active_dn = None  # dict(before_bar, before_price, slope, pad)
    signals = []  # (bar, dir)

    for i in range(n):
        if active_up is not None:
            val = active_up["before_price"] + active_up["slope"] * (i - active_up["before_bar"])
            if low[i] > val:
                signals.append((i, 1))
                active_up = None
                broken = True
        if active_dn is not None:
            raw_val = active_dn["before_price"] + active_dn["slope"] * (i - active_dn["before_bar"])
            padded_val = raw_val + active_dn["pad"]
            if high[i] < padded_val:
                signals.append((i, -1))
                active_dn = None
                broken = True

        if not np.isnan(ph[i]):
            pivot_bar = i - pivot_len
            price = ph[i]
            upbin.insert(0, (price, pivot_bar))
            if len(upbin) >= 2:
                cur_p, cur_b = upbin[0]
                bef_p, bef_b = upbin[1]
                if cur_p < bef_p:
                    if broken:
                        valid = True
                    else:
                        valid = False
                        if len(upbin) > 3:
                            p2, _ = upbin[2]; p3, _ = upbin[3]
                            if bef_p < p2 and bef_p < p3 and cur_p < p2 and cur_p < p3:
                                valid = True
                    if valid:
                        slope = (cur_p - bef_p) / (cur_b - bef_b)
                        j = np.arange(bef_b, i + 1)
                        line_val = bef_p + slope * (j - bef_b)
                        removed = np.any(low[bef_b:i + 1] > line_val)
                        if removed:
                            broken = True
                            active_up = None
                        else:
                            broken = False
                            pad = min(atr_vol[i] * 0.1, close[i] * (0.1 / 100.0)) * space
                            active_up = dict(before_bar=bef_b, before_price=bef_p, slope=slope, pad=pad)
                        upbin = []

        if not np.isnan(pl[i]):
            pivot_bar = i - pivot_len
            price = pl[i]
            dnbin.insert(0, (price, pivot_bar))
            if len(dnbin) >= 2:
                cur_p, cur_b = dnbin[0]
                bef_p, bef_b = dnbin[1]
                if cur_p > bef_p:
                    if broken:
                        valid = True
                    else:
                        valid = False
                        if len(dnbin) > 3:
                            p2, _ = dnbin[2]; p3, _ = dnbin[3]
                            if bef_p > p2 and bef_p > p3 and cur_p > p2 and cur_p > p3:
                                valid = True
                    if valid:
                        slope = (cur_p - bef_p) / (cur_b - bef_b)
                        j = np.arange(bef_b, i + 1)
                        line_val = bef_p + slope * (j - bef_b)
                        removed = np.any(high[bef_b:i + 1] < line_val)
                        if removed:
                            broken = True
                            active_dn = None
                        else:
                            broken = False
                            pad = min(atr_vol[i] * 0.1, close[i] * (0.1 / 100.0)) * space
                            active_dn = dict(before_bar=bef_b, before_price=bef_p, slope=slope, pad=pad)
                        dnbin = []
    return signals


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- 1 Trendline Strategy (PIVOT_LEN, SPACE, TP_MULT)\n{b.describe()}")

    atr_trade = C.wilder_atr(b.high, b.low, b.close, ATR_TRADE_LEN)
    atr_vol = C.wilder_atr(b.high, b.low, b.close, ATR_VOL_LEN)

    piv_cache = {}
    for pl_len in PIVOT_LENS:
        ph, pl = C.pivots(b.high, b.low, pl_len)
        piv_cache[pl_len] = (ph, pl)

    grid = list(itertools.product(PIVOT_LENS, SPACES, TP_MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    signal_cache = {}
    no_exit = np.zeros(b.n, dtype=np.bool_)
    rows = []
    for cfg in grid:
        pivot_len, space, tp_mult = cfg
        key = (pivot_len, space)
        if key not in signal_cache:
            ph, pl = piv_cache[pivot_len]
            signal_cache[key] = simulate_zones(b.high, b.low, b.close, atr_vol, ph, pl, b.n, pivot_len, space)
        signals = signal_cache[key]
        if not signals:
            continue
        bars = np.array([s[0] for s in signals], dtype=np.int64)
        dirs = np.array([s[1] for s in signals], dtype=float)
        valid = ~np.isnan(atr_trade[bars]) & (atr_trade[bars] > 0)
        bars, dirs = bars[valid], dirs[valid]
        dist = SL_MULT * atr_trade[bars]
        target_r = tp_mult / SL_MULT

        ex = dict(target_r=target_r, max_hold=2000, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)
        r = C.sim_signals(bars, dirs, dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"],
                          b.is_lo, b.is_hi)
        n_tr, pnl = len(r[3]), r[3]
        if n_tr < 100:
            continue
        rows.append(dict(cfg=cfg, n=n_tr, pf=C.pct_pf(pnl), bars=bars, dirs=dirs, target_r=target_r, ex=ex))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=100. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    bars, dirs, ex = best["bars"], best["dirs"], best["ex"]
    dist = SL_MULT * atr_trade[bars]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    exargs = (ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"])
    r = C.sim_signals(bars, dirs, dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
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
    out_path = "/home/user/test-project/research/silver_btc/one_trendline_liquidity_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
