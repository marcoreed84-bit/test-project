"""
MECHANICAL ELLIOTT WAVE (objective 5-wave impulse -> ABC correction), M15.
NOT the "EWO" momentum-oscillator proxy (ewo_rsi_exhaustion_search.py, an
already-closed question): this is the actual wave-COUNT pipeline that
real-world Elliott Wave tools use - (1) a ZigZag swing engine, (2) the three
hard textbook impulse rules applied with zero discretion, (3) a signal fired
only once the 5th wave's own pivot is CONFIRMED.

HYPOTHESIS (ONE, stated before any run, falsifiable): "A completed, rule-
valid 5-wave impulse is followed by a 3-wave CORRECTION against it." Trade:
on the bar that confirms wave 5's pivot, enter in the OPPOSITE direction of
the impulse (bull impulse ending at a confirmed high -> SHORT; bear impulse
ending at a confirmed low -> LONG). The inverse "continuation" reading is
NOT tested (testing both and keeping the better one would be K=2 dressed up
as K=1).

EXIT (fixed from Elliott theory itself, never tuned):
  stop   = wave-5 extreme (P5) +/- 0.25 x ATR(14)  - a new extreme beyond P5
           means wave 5 is extending and the "impulse is complete" claim is
           falsified. (0.25 ATR buffer = this folder's harmonic-script
           default, borrowed, not searched.)
  target = the wave-4 extreme (P4) - the textbook "corrections typically
           retrace into the territory of the previous 4th wave" target.
           Per-trade target_r = |close - P4| / stop distance; a signal whose
           close has ALREADY reached P4 at confirmation (target_r <= 0) is
           skipped (knowable at the signal bar, so no lookahead).
  max_hold = 500 bars (~5 trading days), a backstop only.
  The exit is literally common._run_one() (gap-aware stop, stop-wins-ties,
  entry at close[i] + spread[i+1]*point), called with a per-trade target_r.

(1) ZIGZAG - ATR-reversal ZigZag (the classic "reversal amount" ZigZag, with
the reversal amount expressed in ATR(14) multiples rather than % so one
setting means the same thing on Gold, Silver and BTC whose volatility in %
differs ~5x). State machine run ONCE, forward, bar by bar over CLOSED bars:
  - in an up-leg, track the running max high (ext, ext_bar) since the last
    confirmed low. If bar i prints a NEW high, ext moves and NOTHING is
    confirmed on that bar. Otherwise, if low[i] <= ext - MULT*ATR[i], the up-
    leg's extreme is CONFIRMED as a pivot high (bar ext_bar < i), stamped
    with confirm_bar = i, and a down-leg starts with ext = low[i]. Mirror
    for down-legs.
  - an OUTSIDE bar (new high AND a reversal-sized low on the same bar) is
    treated as "new high, no confirmation": the intrabar order is unknowable
    from OHLC, so the detector never assumes the favourable one.
  - a confirmed pivot is FINAL: the algorithm never revisits it. Only the
    still-open last leg (the "live" extreme) can change, and it is NEVER
    used by any signal - this is what removes both leak classes described in
    research/trendbreaker/pattern_rigor_common.py (confirm-lag AND the
    provisional-last-swing survivorship leak). Pivot confirmation needs the
    reversal amount to have actually printed, which is exactly the lag a
    real MT5/TradingView ZigZag has; that lag is paid in full here (the
    entry is the close of the confirmation bar, ~MULT ATRs away from P5).
(2) IMPULSE VALIDATOR on the last 6 confirmed pivots P0..P5 (bull: P0 low,
    P5 high; bear mirrored), evaluated ONLY on a bar where a new pivot was
    just confirmed and P5 is that pivot:
  R1 wave 2 never retraces >100% of wave 1        : P2 > P0
  R2 wave 3 is never the shortest of 1/3/5        : not (L3 < L1 and L3 < L5)
  R3 wave 4 does not enter wave-1 territory       : strict  P4 > P1
                                                    relaxed P4 > P2 (overlap
       allowed - the futures/CFD/diagonal relaxation - but wave 4 may not
       undercut the end of wave 2)
  plus structural: wave 3 ends beyond wave 1 (P3 > P1) in both modes
  optional R4 wave 5 ends beyond wave 3 (no truncation): P5 > P3
(4) ABC check - reported as a DESCRIPTIVE DIAGNOSTIC only (it needs pivots
    confirmed AFTER entry, so it cannot be a signal input): after each
    validated impulse, how often do the next three confirmed pivots form a
    textbook ABC (B does not exceed P5, C ends beyond A), versus the same
    frequency after EVERY confirmed pivot of the same type (base rate).

GRID (K=12, literal, fixed before any run): ZZ_ATR_MULT in {2,3,5}
x W4_RULE in {strict, relaxed} x REQUIRE_W5_BEYOND_W3 in {False, True}.
Everything else (ATR 14, stop buffer, wave-4 target, max hold) is fixed.
Selection = highest IS %PF with IS n>=100 (folder convention); OOS untouched.

LOOKAHEAD AUDIT (run inside this script, before any number is trusted):
  (a) structural asserts: every pivot bar < its confirm bar, pivots strictly
      alternate, signal bar == P5's confirm bar;
  (b) TRUNCATION test: for 300 random signal bars per instrument, recompute
      ATR + ZigZag + validator on data[:i+1] ONLY and require (i) the
      identical confirmed-pivot prefix and (ii) the identical signal on bar
      i (same direction, same stop, same target). Any future-data dependence
      fails this;
  (c) POSITIVE CONTROL: a deliberately leaky variant that "enters" at P5's
      own pivot bar (i.e. at the extreme, before it could be known). It must
      FAIL the truncation test and should show an absurd IS %PF - proving
      the test has teeth and showing what a leak would look like here.

DATA: GOLD trimmed to >= 2014-06-13 01:30 (CLAUDE.md contamination rule -
the earlier rows are daily/hourly bars mislabeled as M15 and would seed the
ZigZag with garbage swings) BEFORE any indicator is computed. Point size
read from each CSV's own meta header (common.load_m15 asserts it). Silver
M15 is run only if SILVER_M15_native.csv is present in common.DATA_DIR.
Splits = common.SPLITS (unchanged). %PF = common.pct_pf on pnl/entry_price.
"""
import sys
import os
import itertools
import numpy as np
import pandas as pd
from numba import njit

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C

ZZ_ATR_MULTS = [2.0, 3.0, 5.0]
W4_RULES = ["strict", "relaxed"]
REQ_W5S = [False, True]
STOP_BUF_ATR = 0.25
MAX_HOLD = 500
MIN_IS_N = 100
GOLD_REAL_M15_START = pd.Timestamp("2014-06-13 01:30")
N_AUDIT = 300


# ------------------------------------------------------------------ (1) zigzag

@njit(cache=True)
def zigzag_atr(h, l, atr, mult):
    """Causal ATR-reversal ZigZag. Returns CONFIRMED pivots only:
    (pivot_bar, pivot_price, pivot_dir (+1 high / -1 low), confirm_bar)."""
    n = len(h)
    pb = np.empty(n, np.int64); pp = np.empty(n); pd_ = np.empty(n, np.int64); pc = np.empty(n, np.int64)
    m = 0
    trend = 0
    hi = h[0]; hib = 0; lo = l[0]; lob = 0
    ext = 0.0; extb = 0
    for i in range(1, n):
        a = atr[i]
        ok = not np.isnan(a) and a > 0
        thr = mult * a if ok else 0.0
        if trend == 0:
            newhi = h[i] > hi
            newlo = l[i] < lo
            if newhi:
                hi = h[i]; hib = i
            if newlo:
                lo = l[i]; lob = i
            if not ok:
                continue
            if (not newhi) and l[i] <= hi - thr:
                pb[m] = hib; pp[m] = hi; pd_[m] = 1; pc[m] = i; m += 1
                trend = -1; ext = l[i]; extb = i
            elif (not newlo) and h[i] >= lo + thr:
                pb[m] = lob; pp[m] = lo; pd_[m] = -1; pc[m] = i; m += 1
                trend = 1; ext = h[i]; extb = i
        elif trend == 1:
            if h[i] > ext:
                ext = h[i]; extb = i          # new high: no confirmation on this bar (order unknown)
            elif ok and l[i] <= ext - thr:
                pb[m] = extb; pp[m] = ext; pd_[m] = 1; pc[m] = i; m += 1
                trend = -1; ext = l[i]; extb = i
        else:
            if l[i] < ext:
                ext = l[i]; extb = i
            elif ok and h[i] >= ext + thr:
                pb[m] = extb; pp[m] = ext; pd_[m] = -1; pc[m] = i; m += 1
                trend = 1; ext = h[i]; extb = i
    return pb[:m], pp[:m], pd_[:m], pc[:m]


# ------------------------------------------------------------------ (2) impulse validator

def valid_impulse(p, d5, w4_rule, req_w5):
    """p = prices P0..P5 of the last 6 confirmed pivots; d5 = +1 if P5 is a high
    (bull impulse), -1 if a low (bear). Mirror bear into bull space."""
    q = [x * d5 for x in p]  # bear impulse -> negate prices -> same inequalities
    P0, P1, P2, P3, P4, P5 = q
    L1, L3, L5 = P1 - P0, P3 - P2, P5 - P4
    if not (L1 > 0 and L3 > 0 and L5 > 0):
        return False
    if not (P2 > P0):                       # R1
        return False
    if L3 < L1 and L3 < L5:                 # R2
        return False
    if not (P3 > P1):                       # structural: wave 3 beyond wave 1
        return False
    if w4_rule == "strict":
        if not (P4 > P1):                   # R3 strict
            return False
    else:
        if not (P4 > P2):                   # R3 relaxed
            return False
    if req_w5 and not (P5 > P3):            # R4 optional
        return False
    return True


def detect(high, low, close, atr, mult, w4_rule, req_w5, leaky=False):
    """Signals on wave-5 confirmation. Returns list of (bar, dir, dist, target_r, pivot_index_of_P5)
    plus the pivot arrays. leaky=True is the deliberate POSITIVE-CONTROL bug: signal stamped at
    P5's own pivot bar, entering at that bar's close (unknowable at the time)."""
    pb, pp, pdir, pc = zigzag_atr(high, low, atr, mult)
    sigs = []
    for k in range(5, len(pb)):
        p = [pp[k - 5 + j] for j in range(6)]
        d5 = int(pdir[k])
        if not valid_impulse(p, d5, w4_rule, req_w5):
            continue
        i = int(pb[k]) if leaky else int(pc[k])
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        trade_dir = -d5                       # correction AGAINST the impulse
        raw = close[i]
        P4, P5 = p[4], p[5]
        if trade_dir < 0:
            stop = P5 + STOP_BUF_ATR * a
            dist = stop - raw
            tgt_dist = raw - P4
        else:
            stop = P5 - STOP_BUF_ATR * a
            dist = raw - stop
            tgt_dist = P4 - raw
        if dist <= 0 or tgt_dist <= 0:
            continue
        sigs.append((i, float(trade_dir), float(dist), float(tgt_dist / dist), k))
    sigs.sort(key=lambda s: s[0])
    return sigs, (pb, pp, pdir, pc)


# ------------------------------------------------------------------ engine (per-trade target_r, SAME _run_one)

@njit(cache=True)
def sim_signals_var(sig_bar, sig_dir, sig_dist, sig_tr, o, h, l, c, sp, atr, max_hold, exl, exs, lo, hi):
    n = len(c); m = len(sig_bar)
    eb = np.empty(m, np.int64); dd = np.empty(m); pp = np.empty(m); sa = np.empty(m); tr = np.empty(m)
    cnt = 0; last_exit = -1
    for s in range(m):
        i = sig_bar[s]
        if i < lo or i >= hi or i <= last_exit or i + 1 >= n:
            continue
        if np.isnan(atr[i]) or atr[i] <= 0 or sig_dist[s] <= 0:
            continue
        xbar, pnl = C._run_one(i, sig_dir[s], sig_dist[s], o, h, l, c, sp, atr, n, sig_tr[s], max_hold, 0.0, exl, exs)
        eb[cnt] = i; dd[cnt] = sig_dir[s]; pp[cnt] = pnl; sa[cnt] = sig_dist[s] / atr[i]; tr[cnt] = sig_tr[s]
        cnt += 1; last_exit = xbar
    return eb[:cnt], dd[:cnt], pp[:cnt], sa[:cnt], tr[:cnt]


@njit(cache=True)
def sim_random_var(seed, p_fire, p_long, pool_atr, pool_tr, o, h, l, c, sp, atr, max_hold, exl, exs, lo, hi):
    """Random timing + direction; (stop-ATR, target_r) drawn as a PAIR from the real
    system's own OOS trades, run through the identical _run_one."""
    np.random.seed(seed)
    n = len(c); out = np.empty(hi - lo); cnt = 0; last_exit = -1; npool = len(pool_atr)
    for i in range(lo, min(hi, n - 1)):
        if i <= last_exit:
            continue
        if np.isnan(atr[i]) or atr[i] <= 0:
            continue
        if np.random.random() >= p_fire:
            continue
        d = 1.0 if np.random.random() < p_long else -1.0
        j = np.random.randint(0, npool)
        xbar, pnl = C._run_one(i, d, pool_atr[j] * atr[i], o, h, l, c, sp, atr, n, pool_tr[j], max_hold, 0.0, exl, exs)
        out[cnt] = pnl; cnt += 1; last_exit = xbar
    return out[:cnt]


def random_pool_var(b, pool_atr, pool_tr, target_n, lo, hi, p_long=0.5, n_draws=C.N_RANDOM, seed0=0):
    z = np.zeros(b.n, dtype=np.bool_)
    args = (b.open, b.high, b.low, b.close, b.spread_px, b.atr, MAX_HOLD, z, z, lo, hi)
    p_fire = min(0.5, max(1e-6, target_n / max(1, hi - lo) * 3))
    for it in range(8):
        m = np.mean([len(sim_random_var(seed0 + 10_000 + it * 10 + r, p_fire, p_long, pool_atr, pool_tr, *args))
                     for r in range(5)])
        if m <= 0:
            p_fire = min(0.5, p_fire * 3); continue
        if abs(m - target_n) / target_n < 0.03:
            break
        p_fire = min(0.5, max(1e-7, p_fire * target_n / m))
    pool, ns = [], []
    for r in range(n_draws):
        t = sim_random_var(seed0 + r, p_fire, p_long, pool_atr, pool_tr, *args)
        ns.append(len(t)); pool.append(C.pct_pf(t))
    pool = np.array(pool)
    return pool[np.isfinite(pool)], p_fire, float(np.mean(ns))


def run_sigs(b, sigs, lo, hi):
    z = np.zeros(b.n, dtype=np.bool_)
    if not sigs:
        e = np.empty(0)
        return np.empty(0, np.int64), e, e, e, e
    sb = np.array([s[0] for s in sigs], np.int64); sd = np.array([s[1] for s in sigs])
    sdist = np.array([s[2] for s in sigs]); stt = np.array([s[3] for s in sigs])
    return sim_signals_var(sb, sd, sdist, stt, b.open, b.high, b.low, b.close, b.spread_px, b.atr, MAX_HOLD,
                           z, z, lo, hi)


# ------------------------------------------------------------------ lookahead audit

def audit(b, cfg, sigs, piv, log, label="REAL", rng_seed=11):
    mult, w4, r5 = cfg
    pb, pp, pdir, pc = piv
    # (a) structural
    assert np.all(pb < pc), "pivot confirmed on/before its own bar"
    assert np.all(np.diff(pb) > 0) and np.all(np.diff(pc) >= 0), "pivots not time-ordered"
    assert np.all(pdir[1:] != pdir[:-1]), "pivots do not alternate"
    # (b) truncation
    rng = np.random.default_rng(rng_seed)
    bars = np.array([s[0] for s in sigs])
    pick = rng.choice(len(sigs), size=min(N_AUDIT, len(sigs)), replace=False)
    fails_sig = fails_piv = 0
    for idx in pick:
        i = int(bars[idx])
        h, l, c = b.high[:i + 1], b.low[:i + 1], b.close[:i + 1]
        atr_t = C.wilder_atr(h, l, c, 14)
        s_t, piv_t = detect(h, l, c, atr_t, mult, w4, r5, leaky=(label != "REAL"))
        # confirmed-pivot prefix must be identical
        m = len(piv_t[0])
        known = pc <= i
        if not (known.sum() == m and np.array_equal(pb[known], piv_t[0]) and np.allclose(pp[known], piv_t[1])):
            fails_piv += 1
        want = sigs[idx]
        got = [s for s in s_t if s[0] == i]
        if not got or got[-1][1] != want[1] or abs(got[-1][2] - want[2]) > 1e-9 or abs(got[-1][3] - want[3]) > 1e-9:
            fails_sig += 1
    log(f"  lookahead audit [{label}]: structural asserts OK; truncation test on {len(pick)} signals -> "
        f"signal mismatches={fails_sig}, pivot-prefix mismatches={fails_piv} "
        f"({'PASS - no future dependence' if fails_sig == 0 and fails_piv == 0 else 'FAIL - LOOKAHEAD'})")
    return fails_sig == 0 and fails_piv == 0


# ------------------------------------------------------------------ ABC diagnostic

def abc_diagnostic(piv, sigs, lo, hi, log):
    pb, pp, pdir, pc = piv
    def is_abc(k):  # pivot k = "P5"/origin; next three pivots = A, B, C
        if k + 3 >= len(pb):
            return None
        d = pdir[k]; o, A, B, Cc = pp[k] * d, pp[k + 1] * d, pp[k + 2] * d, pp[k + 3] * d
        return (B < o) and (Cc < A)
    imp = [s[4] for s in sigs if lo <= s[0] < hi]
    base = [k for k in range(len(pb)) if lo <= pc[k] < hi]
    fi = [is_abc(k) for k in imp]; fi = [x for x in fi if x is not None]
    fb = [is_abc(k) for k in base]; fb = [x for x in fb if x is not None]
    if fi and fb:
        log(f"  ABC diagnostic (descriptive, NOT a signal input): textbook ABC follows a valid impulse "
            f"{100 * np.mean(fi):.1f}% of {len(fi)} vs {100 * np.mean(fb):.1f}% after ANY confirmed pivot "
            f"(base rate, n={len(fb)})")


# ------------------------------------------------------------------ main pipeline

def run(symbol, log):
    df15, point = C.load_m15(symbol)
    if symbol == "GOLD":
        n0 = len(df15)
        df15 = df15[df15["time"] >= GOLD_REAL_M15_START].reset_index(drop=True)
        log(f"\n[GOLD contamination filter] dropped {n0 - len(df15)} pre-{GOLD_REAL_M15_START} rows "
            f"(daily/hourly bars mislabeled M15) BEFORE computing ATR/ZigZag")
    b = C.Bars(df15, point, symbol)
    grid = list(itertools.product(ZZ_ATR_MULTS, W4_RULES, REQ_W5S))
    K = len(grid)
    log(f"\n{'=' * 90}\n{symbol} M15 -- Mechanical Elliott 5-wave impulse -> fade into ABC "
        f"(ZZ_ATR_MULT, W4_RULE, REQ_W5_BEYOND_W3)\n{b.describe()}\npoint={point} (from CSV meta header)\n"
        f"GRID K={K} (literal grid size); selection = highest IS %PF with IS n>={MIN_IS_N}\n{'=' * 90}")

    rows, cache = [], {}
    for cfg in grid:
        sigs, piv = detect(b.high, b.low, b.close, b.atr, *cfg)
        cache[cfg] = (sigs, piv)
        r = run_sigs(b, sigs, b.is_lo, b.is_hi)
        npiv_is = int(((piv[3] >= b.is_lo) & (piv[3] < b.is_hi)).sum())
        rows.append(dict(cfg=cfg, n=len(r[2]), pf=C.pct_pf(r[2]), npiv=npiv_is,
                         nsig=sum(1 for s in sigs if b.is_lo <= s[0] < b.is_hi)))
    log("all combos (IS): cfg -> confirmed pivots / valid-impulse signals / trades taken / IS %PF")
    for r in rows:
        log(f"   {r['cfg']}: pivots={r['npiv']:>6}  signals={r['nsig']:>5}  n={r['n']:>5}  IS %PF={r['pf']:.3f}")
    valid = [r for r in rows if r["n"] >= MIN_IS_N and np.isfinite(r["pf"])]
    valid.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(valid)}/{K} combos had IS n>={MIN_IS_N}; {sum(r['pf'] > 1 for r in valid)} have IS %PF > 1.0")
    if not valid:
        log("NO combo cleared the IS trade-count floor -> DOES NOT SURVIVE.")
        return dict(label=symbol, K=K, verdict="DOES NOT SURVIVE (no valid IS combo)")
    best = valid[0]; cfg = best["cfg"]
    sigs, piv = cache[cfg]
    log(f"FROZEN WINNER (IS only): {cfg}  IS n={best['n']}  IS %PF={best['pf']:.3f}")

    # --- lookahead audit BEFORE trusting anything
    ok = audit(b, cfg, sigs, piv, log, "REAL")
    leak_sigs, leak_piv = detect(b.high, b.low, b.close, b.atr, *cfg, leaky=True)
    lr = run_sigs(b, leak_sigs, b.is_lo, b.is_hi)
    log(f"  positive control (DELIBERATELY LEAKY: enter at P5's own pivot bar): IS n={len(lr[2])} "
        f"IS %PF={C.pct_pf(lr[2]):.3f}  <- what a pivot-confirmation leak would look like")
    audit(b, cfg, leak_sigs, leak_piv, log, "LEAKY control (must FAIL)")
    if not ok:
        log("LOOKAHEAD AUDIT FAILED -> results NOT trustworthy.")
        return dict(label=symbol, K=K, verdict="INVALID (lookahead audit failed)")

    # --- IS-side selection-bias check
    is_r = run_sigs(b, sigs, b.is_lo, b.is_hi)
    is_pool, _, _ = random_pool_var(b, is_r[3], is_r[4], len(is_r[2]), b.is_lo, b.is_hi, seed0=500_000)
    p_is_k, med_is_k = C.best_of_k_p(is_pool, best["pf"], K)
    log(f"IS sanity: random-timing IS pool median={np.median(is_pool):.3f}; IS winner vs best-of-{K} random "
        f"(median {med_is_k:.3f}): p={p_is_k:.4f}")

    # --- OOS (untouched)
    r = run_sigs(b, sigs, b.oos_lo, b.oos_hi)
    oos_dir, oos_pnl, oos_atr, oos_tr = r[1], r[2], r[3], r[4]
    n_oos = len(oos_pnl); oos_pf = C.pct_pf(oos_pnl)
    res = dict(label=symbol, K=K, cfg=cfg, is_n=best["n"], is_pf=round(best["pf"], 3), oos_n=n_oos,
               oos_pf=round(float(oos_pf), 3) if n_oos else None, p_is_k=p_is_k)
    if n_oos == 0:
        log("No OOS trades."); res["verdict"] = "DOES NOT SURVIVE (0 OOS trades)"; return res
    longf = float((oos_dir > 0).mean())
    lp, spn = oos_pnl[oos_dir > 0], oos_pnl[oos_dir < 0]
    log(f"OOS (untouched): n={n_oos}  win%={100 * (oos_pnl > 0).mean():.1f}  %PF={oos_pf:.3f}  "
        f"sum%={100 * oos_pnl.sum():.1f}  long%={100 * longf:.0f} (long %PF={C.pct_pf(lp):.3f} n={len(lp)}, "
        f"short %PF={C.pct_pf(spn):.3f} n={len(spn)})  median stop={np.median(oos_atr):.2f} ATR, "
        f"median target_r={np.median(oos_tr):.2f}")
    abc_diagnostic(piv, sigs, b.is_lo, b.is_hi, lambda s: log(s.replace("ABC diagnostic", "ABC diagnostic IS")))
    abc_diagnostic(piv, sigs, b.oos_lo, b.oos_hi, lambda s: log(s.replace("ABC diagnostic", "ABC diagnostic OOS")))
    if n_oos < 20:
        log("Too few OOS trades -> DOES NOT SURVIVE (insufficient evidence).")
        res["verdict"] = "DOES NOT SURVIVE (n<20)"; return res
    pool, p_fire, mean_n = random_pool_var(b, oos_atr, oos_tr, n_oos, b.oos_lo, b.oos_hi)
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f} vs real {n_oos}; "
        f"same _run_one exit, real spread, (stop,target_r) pairs from real OOS trades): "
        f"median={np.median(pool):.3f}  p95={np.percentile(pool, 95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]")
    dpool, _, _ = random_pool_var(b, oos_atr, oos_tr, n_oos, b.oos_lo, b.oos_hi, p_long=longf, seed0=900_000)
    p1d = float((dpool >= oos_pf).mean())
    log(f"supplementary direction-matched null (p_long={longf:.2f}): median={np.median(dpool):.3f}  p(K=1)={p1d:.4f}")
    res.update(pctile=round(pctile, 1), p1=p1, pK=pK, p1_dir=p1d,
               verdict=C.verdict(pK) if p1 < 0.05 else C.verdict(max(p1, pK)))
    return res


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/elliott_wave_mechanical_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = []
    for sym in ("GOLD", "SILVER", "BTCUSD"):
        if not os.path.exists(f"{C.DATA_DIR}/{sym}_M15_native.csv"):
            log(f"\n{'=' * 90}\n{sym}: {sym}_M15_native.csv NOT PRESENT in {C.DATA_DIR} -> NOT RUN (no verdict).")
            results.append(dict(label=sym, verdict="NOT RUN (data file absent)"))
            continue
        results.append(run(sym, log))
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
