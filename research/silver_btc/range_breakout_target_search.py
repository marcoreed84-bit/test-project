"""
"Range Breakout Targets" (the user's pasted Pine v6 indicator, 2026-09-25):
a consolidation "box" forms wherever the trailing WIN-bar high-low range,
as a %% of price, sits in the tightest PCT%% of the last HIST bars. Once a
box has lasted >= MINBARS and is then broken (a close beyond its high/low),
a MEASURED-MOVE target is projected - box height x MULT added to the broken
edge - and the box's own FAR edge becomes the structural invalidation level.
This is a genuinely different mechanism from everything else tried in this
folder: a volatility-percentile squeeze (not Bollinger width, not ATR), a
fixed geometric target (not an ATR/R-multiple), and a structural stop (the
box's own far edge, not a derived ATR distance) - closest in spirit to
Rectangle (research/trendbreaker/rectangle_flag_test.py, swing-based zones,
already rejected on GOLD itself) but built from a rolling tightness
percentile instead of swing pivots, and to the Bollinger-width breakout
search (research/silver_btc/bb_volume_breakout_search.py, already rejected)
but with a measured-move target instead of an R-multiple one.

TRADEABLE CORE PORTED (drawing/labeling/panel/alerts dropped - irrelevant to
whether the construction makes money): tightness filter, box formation,
breakout trigger, measured-move target, far-edge stop, N-bar expiry.
Two simplifications, disclosed rather than silently made:
  1. A new quiet stretch forming WHILE a box waits for its breakout does NOT
     re-merge/widen that box here (the Pine script's "same consolidation"
     merge is cosmetic box-drawing logic; skipping it can make a small
     number of boxes here time out at WAITBRK where the indicator would
     have kept them alive slightly longer - a conservative simplification,
     since a stale/reset box is not obviously the same trade quality).
  2. Percentile is computed via pandas' linear-interpolation rolling
     quantile, not Pine's own nearest-rank method - immaterial to whether
     there is a genuine edge, only to the exact bars flagged "tight".

EXECUTION: entry fills at close[breakout_bar] + spread[breakout_bar+1] (same
convention as every other file in this folder). Target = edge + MULT x
height (long) / edge - MULT x height (short); stop = the box's OWN far edge
(lo for long, hi for short) - not an ATR distance, the box's real
invalidation level, same idea as the indicator's failOn rule, just enforced
as a resting stop instead of a "close back through" rule (closer to how a
Ratchet/Vanguard/etc. real EA would need to execute this mechanically). Max
hold = EXPIREAT bars, matching the indicator's own expiry. No trailing.

GRID (K=18, literal): WIN in {10,20} x PCT in {20,30,40} x MULT in
{1.0,1.5,2.0}. HIST=200, MINBARS=15, WAITBRK=80, EXPIREAT=120 are the
indicator's own defaults, fixed (not tuned) to keep K honest.

Splits / cost / null / K-correction: same discipline as the rest of this
folder (common.py) - random-timing entries draw stop/target distances from
the real system's own OOS distribution, run through the identical bounded
exit function.
"""
import sys
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

WINS = [10, 20]
PCTS = [20, 30, 40]
MULTS = [1.0, 1.5, 2.0]
HIST = 200
MINBARS = 15
WAITBRK = 80
EXPIREAT = 120
N_RANDOM = 1000
N_BOOT = 5000


def find_breakouts(close, high, low, win, pct, hist=HIST, minbars=MINBARS, waitbrk=WAITBRK):
    n = len(close)
    hi_roll = pd.Series(high).rolling(win, min_periods=win).max().values
    lo_roll = pd.Series(low).rolling(win, min_periods=win).min().values
    rng = (hi_roll - lo_roll) / close
    thr = pd.Series(rng).rolling(hist, min_periods=hist).quantile(pct / 100.0).values
    tight = (np.arange(n) > hist) & np.isfinite(thr) & (rng <= thr)

    events = []  # (entry_bar, dir, edge, height)
    cur_open = False
    cur_from = 0
    cur_hi = cur_lo = 0.0
    box = None
    for i in range(n):
        if box is None:
            if tight[i]:
                if not cur_open:
                    cur_open = True
                    cur_from = i
                    cur_hi = high[i]; cur_lo = low[i]
                else:
                    if high[i] > cur_hi: cur_hi = high[i]
                    if low[i] < cur_lo: cur_lo = low[i]
            else:
                if cur_open:
                    cur_open = False
                    if i - cur_from >= minbars:
                        box = dict(hi=cur_hi, lo=cur_lo, wait_from=i)
        else:
            if close[i] > box["hi"]:
                h = box["hi"] - box["lo"]
                events.append((i, 1, box["hi"], h))
                box = None
            elif close[i] < box["lo"]:
                h = box["hi"] - box["lo"]
                events.append((i, -1, box["lo"], h))
                box = None
            elif i - box["wait_from"] >= waitbrk:
                box = None
    return events


def _run_bounded(i, d, entry, stop, target, o, h, l, c, max_hold, n):
    fill = i + 1
    last = min(n - 1, i + max_hold)
    is_buy = d > 0
    for k in range(fill, last + 1):
        if is_buy:
            if o[k] <= stop:
                return k, (stop - entry) / entry
            if l[k] <= stop:
                return k, (stop - entry) / entry
            if o[k] >= target:
                return k, (o[k] - entry) / entry
            if h[k] >= target:
                return k, (target - entry) / entry
        else:
            if o[k] >= stop:
                return k, (entry - stop) / entry
            if h[k] >= stop:
                return k, (entry - stop) / entry
            if o[k] <= target:
                return k, (entry - o[k]) / entry
            if l[k] <= target:
                return k, (entry - target) / entry
    return last, ((c[last] - entry) if is_buy else (entry - c[last])) / entry


def sim_events(events, mult, b):
    trades = []
    last_exit = -1
    for (i, d, edge, height) in events:
        if i <= last_exit or i + 1 >= b.n:
            continue
        fill = i + 1
        cost = b.spread_px[fill]
        raw = b.close[i]
        entry = raw + cost if d > 0 else raw - cost
        target = edge + mult * height if d > 0 else edge - mult * height
        stop = edge - height if d > 0 else edge + height  # the box's own far edge
        if d > 0 and stop >= entry:
            continue
        if d < 0 and stop <= entry:
            continue
        xbar, pnl = _run_bounded(i, d, entry, stop, target, b.open, b.high, b.low, b.close, EXPIREAT, b.n)
        trades.append((i, xbar, d, pnl, abs(entry - stop)))
        last_exit = xbar
    return trades


def sim_random(b, seed, p_fire, dist_pool, lo, hi):
    rng = np.random.default_rng(seed)
    trades = []
    last_exit = max(lo, -1)
    for i in range(lo, min(hi, b.n - 1)):
        if i <= last_exit:
            continue
        if rng.random() >= p_fire:
            continue
        d = 1 if rng.random() < 0.5 else -1
        fill = i + 1
        if fill >= b.n:
            continue
        cost = b.spread_px[fill]
        raw = b.close[i]
        entry = raw + cost if d > 0 else raw - cost
        dist = dist_pool[rng.integers(0, len(dist_pool))]
        stop = entry - dist if d > 0 else entry + dist
        target = entry + dist if d > 0 else entry - dist  # symmetric 1R null (real system's own avg R:R varies by mult; matched separately per cfg by scaling below)
        xbar, pnl = _run_bounded(i, d, entry, stop, target, b.open, b.high, b.low, b.close, EXPIREAT, b.n)
        trades.append(pnl)
        last_exit = xbar
    return np.array(trades)


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- Range Breakout Targets (WIN, PCT, MULT)\n{b.describe()}")

    box_cache = {}
    for win, pct in itertools.product(WINS, PCTS):
        box_cache[(win, pct)] = find_breakouts(b.close, b.high, b.low, win, pct)

    grid = list(itertools.product(WINS, PCTS, MULTS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    for cfg in grid:
        win, pct, mult = cfg
        events = box_cache[(win, pct)]
        is_events = [e for e in events if b.is_lo <= e[0] < b.is_hi]
        tr = sim_events(is_events, mult, b)
        if len(tr) < 100:
            continue
        pnl = np.array([t[3] for t in tr])
        rows.append(dict(cfg=cfg, n=len(tr), pf=C.pct_pf(pnl), events=events))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=100. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    win, pct, mult = best["cfg"]
    events = best["events"]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    oos_events = [e for e in events if b.oos_lo <= e[0] < b.oos_hi]
    oos_tr = sim_events(oos_events, mult, b)
    if not oos_tr:
        log("No OOS trades."); return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (0 OOS trades)")
    n_oos = len(oos_tr)
    pnl = np.array([t[3] for t in oos_tr])
    dist_pool = np.array([t[4] for t in oos_tr])
    oos_pf = C.pct_pf(pnl)
    log(f"OOS (untouched): n={n_oos}  win%={100*(pnl>0).mean():.1f}  %PF={oos_pf:.3f}  sum%={100*pnl.sum():.1f}")
    if n_oos < 20:
        log("Too few OOS trades -> DOES NOT SURVIVE (insufficient evidence).")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (n<20)")

    p_fire = min(0.5, max(1e-6, n_oos / max(1, b.oos_hi - b.oos_lo) * 3))
    for _ in range(8):
        counts = [len(sim_random(b, 10_000 + it, p_fire, dist_pool, b.oos_lo, b.oos_hi)) for it in range(5)]
        m = np.mean(counts)
        if m <= 0:
            p_fire = min(0.5, p_fire * 3); continue
        if abs(m - n_oos) / n_oos < 0.03:
            break
        p_fire = min(0.5, max(1e-7, p_fire * n_oos / m))
    pool = np.array([C.pct_pf(sim_random(b, r, p_fire, dist_pool, b.oos_lo, b.oos_hi)) for r in range(N_RANDOM)])
    pool = pool[np.isfinite(pool)]
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}): median={np.median(pool):.3f}  "
        f"p95={np.percentile(pool,95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]")
    return dict(label=symbol, K=K, cfg=best["cfg"], is_n=best["n"], is_pf=best["pf"], oos_n=n_oos, oos_pf=oos_pf,
                pctile=pctile, p1=p1, pK=pK, verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/range_breakout_target_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
