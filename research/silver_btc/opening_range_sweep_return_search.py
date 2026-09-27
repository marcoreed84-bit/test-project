"""
"EE Sweep Return" (the user's seventh pasted Pine v6 strategy): an
Opening-Range (OR) sweep-and-return. The OR is the high/low of a fixed
morning window (0830-0930 America/Chicago in the original - a US futures
market-open convention); once locked, during a following signal window
(0930-1500), a break beyond either OR edge ARMS that side; if price then
closes back INSIDE the box (strictBox=true, the default) that's the
signal - short on a failed upside break, long on a failed downside break.
Same underlying idea as the Liquidity Sweep + Reclaim script already
tested (fails on all three instruments) but anchored to a single,
specific session-defined range with its own stateful arm/consume logic
and independent (not R-multiple-linked) fixed-point TP/SL, rather than 4
independent level types - different enough to test on its own rather
than assume the prior verdict carries over.

TIMEZONE: no confirmed Chicago-time offset exists for this broker's
Gold/Silver/BTC feeds, so - same approximation already used for the ICT
Liquidity Sweep script's "UTC" - the OR/signal windows are applied to
each bar's OWN timestamp hour:minute directly (broker server time),
disclosed rather than silently assumed correct. OR = 08:30-09:30,
signal window = 09:30-15:00 (the script's own default session strings).

POINTS -> ATR, a necessary adaptation (not a simplification of the
mechanism): the original's tpPts=50 / slPts=25 are raw price POINTS,
meaningless across instruments at wildly different price/volatility
scales (Gold ~$4000, Silver ~$65, BTC ~$85000) - replaced with ATR
multiples (TP_ATR_MULT, SL_ATR_MULT), matching every other construction
in this folder. Since the original sets TP and SL INDEPENDENTLY (not as
a ratio of one variable), target_r = TP_ATR_MULT / SL_ATR_MULT is passed
to common.py's existing R-multiple engine with dist = SL_ATR_MULT x ATR -
algebraically identical to computing both distances independently.

PORTED FAITHFULLY: the daily OR reset/build/lock state machine, the
arm-on-break / consume-on-return logic (including the same-bar-double-
break tie-break via close>=open), and the strictBox on/off toggle
(exposed here as a real grid axis, not fixed, since it's one of the two
genuine behavioral switches the original script actually ships).

NOT ported: fixed-contract position sizing (irrelevant to %PF), the
"Next bar close" delayed-entry mode (left at the default "Signal bar
close" to keep K honest) The EOD flatten (close at signal-window end) is
approximated by a MAX_HOLD of 24 M15 bars (~6h, close to the ~5.5h
window itself), disclosed rather than modeled as an exact calendar cutoff.

GRID (K=18, literal): TP_ATR_MULT in {1.5,2.0,3.0} x SL_ATR_MULT in
{0.5,0.75,1.0} x STRICT_BOX in {True, False}.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

TP_ATR_MULTS = [1.5, 2.0, 3.0]
SL_ATR_MULTS = [0.5, 0.75, 1.0]
STRICT_BOX_OPTS = [True, False]
OR_START_MIN, OR_END_MIN = 8 * 60 + 30, 9 * 60 + 30
WIN_START_MIN, WIN_END_MIN = 9 * 60 + 30, 15 * 60
MAX_HOLD = 24


def detect_events(minute_of_day, o, h, l, c, strict_box):
    n = len(c)
    in_or = (minute_of_day >= OR_START_MIN) & (minute_of_day < OR_END_MIN)
    in_win = (minute_of_day >= WIN_START_MIN) & (minute_of_day < WIN_END_MIN)
    in_or_prev = np.concatenate(([False], in_or[:-1]))
    or_start_event = in_or & ~in_or_prev
    or_end_event = (~in_or) & in_or_prev

    events = []
    orH = orL = np.nan
    orOK = False
    armUp = armDn = False
    last_break = 0
    for i in range(n):
        if or_start_event[i]:
            orH, orL = h[i], l[i]
            orOK = False; armUp = False; armDn = False; last_break = 0
        elif in_or[i]:
            if np.isnan(orH) or h[i] > orH:
                orH = h[i]
            if np.isnan(orL) or l[i] < orL:
                orL = l[i]
        if or_end_event[i]:
            orOK = True

        if orOK and in_win[i] and not np.isnan(orH) and not np.isnan(orL):
            broke_up = h[i] > orH
            broke_dn = l[i] < orL
            if broke_up:
                armUp = True
            if broke_dn:
                armDn = True
            if broke_up and broke_dn:
                last_break = 1 if c[i] >= o[i] else -1
            elif broke_up:
                last_break = 1
            elif broke_dn:
                last_break = -1

            if strict_box:
                inside = (c[i] < orH) and (c[i] > orL)
                ret_short = inside
                ret_long = inside
            else:
                ret_short = c[i] < orH
                ret_long = c[i] > orL

            raw_short = armUp and ret_short
            raw_long = armDn and ret_long
            short_sig = raw_short and (not raw_long or last_break == 1)
            long_sig = raw_long and (not raw_short or last_break == -1)

            if short_sig or long_sig:
                armUp = False; armDn = False; last_break = 0
                events.append((i, -1 if short_sig else 1))
    return events


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- Opening-Range Sweep + Return (TP_ATR_MULT, SL_ATR_MULT, STRICT_BOX)\n{b.describe()}")

    time_idx = pd.to_datetime(b.time)
    minute_of_day = (time_idx.hour * 60 + time_idx.minute).values

    events_cache = {}
    for strict in STRICT_BOX_OPTS:
        ev = detect_events(minute_of_day, b.open, b.high, b.low, b.close, strict)
        events_cache[strict] = np.array(ev, dtype=np.int64) if ev else np.zeros((0, 2), dtype=np.int64)
        log(f"  strict_box={strict}: {len(ev)} raw events")

    grid = list(itertools.product(TP_ATR_MULTS, SL_ATR_MULTS, STRICT_BOX_OPTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    no_exit = np.zeros(b.n, dtype=np.bool_)
    rows = []
    for cfg in grid:
        tp_mult, sl_mult, strict = cfg
        ev = events_cache[strict]
        if len(ev) == 0:
            continue
        bars_all, dirs_all = ev[:, 0], ev[:, 1].astype(float)
        dist_all = sl_mult * b.atr[bars_all]
        valid = ~np.isnan(dist_all) & (dist_all > 0)
        sig_bar, sig_dir, sig_dist = bars_all[valid], dirs_all[valid], dist_all[valid]
        target_r = tp_mult / sl_mult

        ex = dict(target_r=target_r, max_hold=MAX_HOLD, trail_atr=0.0, exit_long=no_exit, exit_short=no_exit)
        r = C.sim_signals(sig_bar, sig_dir, sig_dist, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                          ex["target_r"], ex["max_hold"], ex["trail_atr"], ex["exit_long"], ex["exit_short"],
                          b.is_lo, b.is_hi)
        n_tr, pnl = len(r[3]), r[3]
        if n_tr < 100:
            continue
        rows.append(dict(cfg=cfg, n=n_tr, pf=C.pct_pf(pnl), sig_bar=sig_bar, sig_dir=sig_dir, sig_dist=sig_dist,
                          target_r=target_r, ex=ex))

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
    out_path = "/home/user/test-project/research/silver_btc/opening_range_sweep_return_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
