"""
Direct port of SupportResistance.mq5's "box" construction - genuinely
different from everything else tested this session: it builds a RANGE
(support AND resistance together), not a single level or line.

RESISTANCE(i) = the highest high over the trailing PERIOD bars, but only
if that same high is ALSO the highest over a longer PERIOD+OVERLOOK
window (i.e. going back OVERLOOK bars further doesn't turn up anything
higher - confirms the recent high is a genuine, not-yet-exceeded
extreme). SUPPORT(i) mirrors this on the low side. Once both are valid
and price is contained comfortably between them (the .mq5's own
BounceUp/BounceBack gating), a "box" locks in at [support, resistance]
and keeps redrawing every bar price stays inside it. The box breaks (and
a fresh one starts hunting) the moment price closes outside either edge.

FAITHFULNESS NOTE: the source .mq5 has its own real quirk in the
BounceUp/BounceBack gating - it calls Support() with the HIGH array and
Resistance() with the LOW array in one branch each (not the box's actual
stored levels, which DO use the correct arrays - only the gate that
decides whether to START tracking a new box is affected). This is ported
exactly as written, bugs included, since the point is to test what the
real indicator actually does, not a cleaned-up reinterpretation of it.

SIGNAL: a breakout of an active box - low breaks below support (short) or
high breaks above resistance (long), at the bar it happens. Stop = the
box's own width (risk the full range against you, a construction-native
distance rather than a generic ATR guess).

GRID (K=27, literal): PERIOD in {10,20,40} x OVERLOOK in {5,10,20} x
TARGET_R in {1.0,1.5,2.0}.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

PERIODS = [10, 20, 40]
OVERLOOKS = [5, 10, 20]
TARGET_RS = [1.0, 1.5, 2.0]


def confirmed_extreme(arr, period, overlook, is_max):
    s = pd.Series(arr)
    if is_max:
        near = s.rolling(period).max()
        far = s.rolling(period + overlook).max()
    else:
        near = s.rolling(period).min()
        far = s.rolling(period + overlook).min()
    valid = (near.values == far.values)
    out = np.where(valid, near.values, 0.0)
    out[: period + overlook - 1] = np.nan
    return out


def build_box_signals(o, h, l, c, period, overlook):
    n = len(c)
    resistance = confirmed_extreme(h, period, overlook, True)
    support = confirmed_extreme(l, period, overlook, False)
    # bug-faithful gating quantities: Support() fed the HIGH array, Resistance() fed the LOW array
    sup_via_high = confirmed_extreme(h, period, overlook, False)
    res_via_low = confirmed_extreme(l, period, overlook, True)

    with np.errstate(invalid="ignore"):
        bounce_up = (sup_via_high * 3 + resistance) / 4 < c
        bounce_back = (support + res_via_low * 3) / 4 > c

    long_sig = np.zeros(n, dtype=np.bool_)
    short_sig = np.zeros(n, dtype=np.bool_)
    box_dist = np.zeros(n, dtype=np.float64)

    box_active = False
    savedmin = savedmax = 0.0
    for i in range(n):
        if np.isnan(resistance[i]) or np.isnan(support[i]):
            box_active = False
            continue
        if not box_active:
            if support[i] != 0 and resistance[i] != 0 and bounce_back[i] and bounce_up[i]:
                savedmin, savedmax = support[i], resistance[i]
                box_active = True
        else:
            if l[i] > savedmin and h[i] < savedmax:
                pass  # box holds
            else:
                width = savedmax - savedmin
                if l[i] <= savedmin and width > 0:
                    short_sig[i] = True
                    box_dist[i] = width
                if h[i] >= savedmax and width > 0:
                    long_sig[i] = True
                    box_dist[i] = width
                box_active = False
    return long_sig, short_sig, box_dist


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)

    log(f"\n{'='*90}\n{symbol} M15 -- Box breakout, port of SupportResistance.mq5 (PERIOD, OVERLOOK, TARGET_R)\n{b.describe()}")

    grid = list(itertools.product(PERIODS, OVERLOOKS, TARGET_RS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    sig_cache = {}
    for period, overlook in itertools.product(PERIODS, OVERLOOKS):
        sig_cache[(period, overlook)] = build_box_signals(b.open, b.high, b.low, b.close, period, overlook)

    rows = []
    cache = {}
    for cfg in grid:
        period, overlook, target_r = cfg
        long_sig, short_sig, box_dist = sig_cache[(period, overlook)]
        il = np.where(long_sig)[0]
        is_ = np.where(short_sig)[0]
        sig_bar = np.concatenate((il, is_)).astype(np.int64)
        sig_dir = np.concatenate((np.ones(len(il)), -np.ones(len(is_))))
        sig_dist = np.concatenate((box_dist[il], box_dist[is_]))
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
    out_path = "/home/user/test-project/research/silver_btc/box_breakout_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
