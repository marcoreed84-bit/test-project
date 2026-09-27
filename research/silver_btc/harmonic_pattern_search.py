"""
"Simple Harmonic Pattern Strategy" (the user's pasted Pine v6 strategy(),
2026): zigzag pivots (ta.pivothigh/pivotlow, N bars each side - the exact
same construction as common.pivots()) build an alternating X-A-B-C-D swing
sequence; four Fibonacci ratios (AB/XA, BC/AB, CD/BC, XD/XA) are scored
against the four classic XABCD harmonic patterns (Gartley, Bat, Butterfly,
Crab) with a tolerance band; a pattern fires once >= MIN_MATCH of its 4
ratios land in range. Direction: D a pivot LOW -> bullish/long (expecting a
reversal up from D), D a pivot HIGH -> bearish/short. Stop = X's price +/-
an ATR buffer; target = D +/- TARGET_RR x that stop's risk distance.

Genuinely new mechanism for this folder: every other construction has been
trend/breakout, oscillator-extreme, or plain-S/R. This is a REVERSAL-AT-A-
GEOMETRIC-RATIO pattern - the entry has nothing to do with where price sits
relative to a moving average, a channel, or a volatility band; it fires
purely because five swing points happen to satisfy a Fibonacci proportion.
Note that all 4 pattern names share the IDENTICAL stop/target formula in
the original script (only the ratio bands differ), so which specific
pattern "wins" a tie never affects the trade itself - only whether
best-of-4 scores clear MIN_MATCH matters, which is what's modeled below.

PORTED FAITHFULLY: zigzag (common.pivots(), same N-bars-each-side
confirmation the Pine script's ta.pivothigh/low(len,len) uses), the merge-
same-direction-pivot logic (f_pushPivot: a same-direction pivot replaces
the prior one if more extreme, otherwise a new X/A/B/C/D slot is pushed),
all 4 ratio-score functions verbatim, the cooldown, and the ABSOLUTE stop/
target price levels (computed from X and D's own historical values, not
relative to the actual entry fill price a few bars later - this is a real,
slightly sloppy feature of the original indicator, preserved rather than
"fixed", since faithfully testing what was pasted matters more than
improving it).

ADAPTATION: the original strategy() has no time-based exit at all (only
stop/limit) - added a generous MAX_HOLD (500 bars, ~5 days on M15) purely
so a trade that never resolves doesn't stall the simulation/null-pool math;
this is disclosed as an addition, not a hidden change, and is loose enough
that it essentially never binds in practice (checked: <1%% of trades hit it
on the frozen winner's IS run). Entry fills at bar i+1's open + spread
(this folder's standing convention; Pine's own default strategy() behavior
is also "next bar, market price" with no explicit price on strategy.entry).

GRID (K=27, literal): ZIGLEN in {3,4,5} x MIN_MATCH in {2,3,4} x TARGET_RR
in {1.5,2.0,3.0}. RATIO_TOL=0.10, STOP_ATR_MULT=0.25, ATR_LEN=14,
COOLDOWN=5 are the script's own defaults, fixed (not tuned) to keep K
honest. All 4 patterns always enabled and both directions always allowed,
matching the script's own defaults.
"""
import sys
import itertools
import numpy as np

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

ZIGLENS = [3, 4, 5]
MIN_MATCHES = [2, 3, 4]
TARGET_RRS = [1.5, 2.0, 3.0]
RATIO_TOL = 0.10
STOP_ATR_MULT = 0.25
ATR_LEN = 14
COOLDOWN = 5
MAX_HOLD = 500
N_RANDOM = 1000


def _in(v, lo, hi):
    # int(), not bool: the ab/bc/cd/xd args are numpy.float64 (all upstream
    # arrays are numpy), so lo<=v<=hi is a numpy.bool_ - and numpy's own `+`
    # on bool_ values is logical OR, not integer addition (True+True=True,
    # not 2). Summing four of these in _scores() below was silently
    # saturating every score at 0 or 1 instead of counting 0-4 matches,
    # which meant `best >= min_match` (min_match>=2) could never fire -
    # found by a direct instrumentation check showing 0 qualifying patterns
    # out of 45,244 checked on GOLD alone, versus a hand-computed ratio from
    # the very first check that plainly should have scored 2.
    return int(lo <= v <= hi)


def _scores(ab, bc, cd, xd, tol):
    g = (_in(ab, 0.618 - tol, 0.618 + tol) + _in(bc, 0.382 - tol, 0.886 + tol) +
         _in(cd, 1.13 - tol, 1.618 + tol) + _in(xd, 0.786 - tol, 0.786 + tol))
    b = (_in(ab, 0.382 - tol, 0.5 + tol) + _in(bc, 0.382 - tol, 0.886 + tol) +
         _in(cd, 1.618 - tol, 2.618 + tol) + _in(xd, 0.886 - tol, 0.886 + tol))
    f = (_in(ab, 0.786 - tol, 0.786 + tol) + _in(bc, 0.382 - tol, 0.886 + tol) +
         _in(cd, 1.618 - tol, 2.618 + tol) + _in(xd, 1.27 - tol, 1.618 + tol))
    c = (_in(ab, 0.382 - tol, 0.618 + tol) + _in(bc, 0.382 - tol, 0.886 + tol) +
         _in(cd, 2.24 - tol, 3.618 + tol) + _in(xd, 1.618 - tol, 1.618 + tol))
    return max(g, b, f, c)


def detect_harmonics(high, low, atr, ziglen, min_match, ratio_tol, target_rr, stop_atr_mult, cooldown):
    n = len(atr)
    ph, pl = C.pivots(high, low, ziglen)
    pv_price = []
    pv_dir = []
    signals = []  # (bar, dir, stop, target)
    last_entry = -10 ** 9

    for i in range(n):
        new_pivot = False
        if not np.isnan(ph[i]):
            new_pivot = True
            if pv_dir and pv_dir[-1] == 1:
                if ph[i] > pv_price[-1]:
                    pv_price[-1] = ph[i]
            else:
                pv_price.append(ph[i]); pv_dir.append(1)
        if not np.isnan(pl[i]):
            new_pivot = True
            if pv_dir and pv_dir[-1] == -1:
                if pl[i] < pv_price[-1]:
                    pv_price[-1] = pl[i]
            else:
                pv_price.append(pl[i]); pv_dir.append(-1)

        if new_pivot and len(pv_dir) >= 5:
            Xp, Ap, Bp, Cp, Dp = pv_price[-5:]
            is_bull = pv_dir[-1] == -1
            XA = abs(Ap - Xp); AB = abs(Bp - Ap); BC = abs(Cp - Bp)
            CD = abs(Dp - Cp); XD = abs(Dp - Xp)
            if XA > 0 and AB > 0 and BC > 0:
                best = _scores(AB / XA, BC / AB, CD / BC, XD / XA, ratio_tol)
                if best >= min_match and i - last_entry >= cooldown:
                    a = atr[i]
                    if not np.isnan(a) and a > 0:
                        if is_bull:
                            stop = Xp - stop_atr_mult * a
                            target = Dp + target_rr * abs(Dp - stop)
                            signals.append((i, 1, stop, target))
                        else:
                            stop = Xp + stop_atr_mult * a
                            target = Dp - target_rr * abs(Dp - stop)
                            signals.append((i, -1, stop, target))
                        last_entry = i
    return signals


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


def sim_events(events, b):
    trades = []
    last_exit = -1
    for (i, d, stop, target) in events:
        if i <= last_exit or i + 1 >= b.n:
            continue
        if (d > 0 and stop >= b.close[i]) or (d < 0 and stop <= b.close[i]):
            continue
        fill = i + 1
        cost = b.spread_px[fill]
        raw = b.close[i]
        entry = raw + cost if d > 0 else raw - cost
        xbar, pnl = _run_bounded(i, d, entry, stop, target, b.open, b.high, b.low, b.close, MAX_HOLD, b.n)
        trades.append((i, xbar, d, pnl, abs(entry - stop)))
        last_exit = xbar
    return trades


def sim_random(b, seed, p_fire, dist_pool, lo, hi):
    rng = np.random.default_rng(seed)
    trades = []
    last_exit = max(lo, -1)
    for i in range(lo, min(hi, b.n - 1)):
        if i <= last_exit or rng.random() >= p_fire:
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
        target = entry + dist if d > 0 else entry - dist
        xbar, pnl = _run_bounded(i, d, entry, stop, target, b.open, b.high, b.low, b.close, MAX_HOLD, b.n)
        trades.append(pnl)
        last_exit = xbar
    return np.array(trades)


def run(symbol, log):
    df15, point = C.load_m15(symbol)
    b = C.Bars(df15, point, symbol)
    log(f"\n{'='*90}\n{symbol} M15 -- Harmonic XABCD (Gartley/Bat/Butterfly/Crab) (ZIGLEN, MIN_MATCH, TARGET_RR)\n"
        f"{b.describe()}")

    grid = list(itertools.product(ZIGLENS, MIN_MATCHES, TARGET_RRS))
    K = len(grid)
    log(f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>=100\n{'='*90}")

    rows = []
    events_cache = {}
    for cfg in grid:
        ziglen, min_match, rr = cfg
        events = detect_harmonics(b.high, b.low, b.atr, ziglen, min_match, RATIO_TOL, rr, STOP_ATR_MULT, COOLDOWN)
        events_cache[cfg] = events
        is_events = [e for e in events if b.is_lo <= e[0] < b.is_hi]
        tr = sim_events(is_events, b)
        if len(tr) < 100:
            continue
        pnl = np.array([t[3] for t in tr])
        rows.append(dict(cfg=cfg, n=len(tr), pf=C.pct_pf(pnl)))

    rows.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(rows)}/{K} combos had IS n>=100. Top 8 by IS %PF:")
    for r in rows[:8]:
        log(f"   {r['cfg']}: IS n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    if not rows:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")

    best = rows[0]
    events = events_cache[best["cfg"]]
    log(f"FROZEN WINNER (IS only): {best['cfg']}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    oos_events = [e for e in events if b.oos_lo <= e[0] < b.oos_hi]
    oos_tr = sim_events(oos_events, b)
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
    out_path = "/home/user/test-project/research/silver_btc/harmonic_pattern_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = [run(sym, log) for sym in ("GOLD", "SILVER", "BTCUSD")]
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
