"""
EMA(84) / EMA(200) CROSSOVER - EXIT-PARAMETER WALK-FORWARD GRID SEARCH
(2026-11-18, follow-up to ema84_200_crossover_search.py, commit d387aba).

WHY: E1 (pure stop-and-reverse) and E2 (SAR + 2 ATR stop) were two generic
exits, not an exit search. The user asked, fairly, whether a better exit for
this exact entry exists. This script answers that with a proper walk-forward
search. It was written AFTER full-history E1 results had been shown in the
conversation, so the protection against that contamination is procedural:
the grid, the selection rule, the nulls and the verdict rule below are all
fixed in this docstring before the script was run, the selection step sees
ONLY IS bars (IS trades are force-closed at the last IS bar, so not even the
tail of an IS trade reads an OOS bar), and nothing in the grid is chosen
from any known trade or date.

ENTRY (unchanged, imported - not reimplemented): E.crosses(close) from
ema84_200_crossover_search.py, bars from E.load()/E.make_bars() (Gold M15
contamination trim at 2014-06-13 01:30 before any EMA/resample, point from
the CSV meta header, H1/H4 resampled from M15 with closed bars only).
Long on an up-cross of closed bar i, short on a down-cross, fill at close[i]
+/- spread[i+1]*point (common._run_one convention).

EXIT GRID (pre-specified; K = 25 literal configurations per series):
  F1 FIXED  stop K_sl x ATR(14), target K_tp x ATR(14), measured from the
            signal-bar close, K_sl in {1.0,1.5,2.0,3.0} x K_tp in
            {1,2,3,4}                                              -> 16
  F2 TRAIL  chandelier trail of T x ATR(14) (initial stop T x ATR, then
            trailed behind the best CLOSE since entry), no target,
            T in {1.5,2.0,3.0}                                     ->  3
  F3 TIME   close after N bars, N in {10,20,40}, either with no stop or
            with a 2.0 x ATR stop (2.0 = the folder's existing E2 /
            Gold_Stoch_200EMA_EA default, not tuned)               ->  6
  Common to ALL 25: the opposite crossover is a backstop - it closes any
  open position at that bar's close and opens the reverse trade (a position
  is never held against a fresh opposite signal). Hence every config takes
  exactly ONE trade per crossover: n is identical for all 25 configs of a
  series, so trade count cannot steer the selection.
  Stops/targets/trail are common._run_one: checked from bar i+1 (never the
  signal bar's own range), gap-aware, stop-before-target when both inside
  one bar (conservative), trail updated on bar k's CLOSE and applied from
  bar k+1. Bar counts for F3 are literal bars on each timeframe.

SELECTION RULE (fixed before running): highest IS %PF among configs with
IS n >= 100 (folder convention, ewo_rsi_exhaustion_search.py). Because n =
number of IS crosses for every config, the floor only decides whether a
series can be searched at all:
  Gold M15 (708 IS crosses), Gold H1 (195), BTC M15 (438), BTC H1 (105):
    floor met, searched normally.
  Gold H4 (53 IS crosses): CANNOT meet 100. It is the timeframe the user
    asked about, so it is searched as a declared EXCEPTION with floor 30 and
    every result for it is labelled BELOW FOLDER FLOOR / LOW POWER.
  BTC H4 (18 IS crosses): below even 30 -> NOT searched, no verdict.
  -> 5 series searched; K_total = 5 x 25 = 125.

OOS + NULLS (frozen winner only, evaluated ONCE on untouched OOS):
  A  random timing, random direction (p_long=0.5), IDENTICAL exit machinery
     (same stop/target/trail/time multiples x ATR at the random bar, same
     opposite-cross backstop, same real spread), p_fire calibrated so the
     mean random trade count matches the real OOS n.
  Ad same but direction mix matched to the real OOS long share (controls
     for "being long during a bull run" - the effect that explained E1's
     Gold OOS %PF).
  p(K=1), p(K=25) (best-of-K bootstrap from the null pool, common.best_of_k_p)
  and p(K=125) are reported for both.
VERDICT RULE (fixed before running): verdict = common.verdict(max(pA, pAd)
at K=25) - the literal grid that produced the frozen winner - with OOS
n >= 20 required; p at K=125 printed as the across-series correction. A
null whose mean count misses the real n by >10% is flagged and excluded.

BULL-RUN / REGIME CHECKS (required before any "survives" is trusted):
  long-only vs short-only %PF (IS and OOS), OOS split by entry year and
  (Gold) 2021-2023 vs 2024+, and the frozen config's own IS 2014-2020
  behaviour with its own IS null (best-of-25 corrected).

AUDITS (run before any verdict):
  (1) entry truncation (E.truncation_audit) + HTF resample truncation
      (E.resample_audit) - entry code unchanged, re-confirmed here.
  (2) EXIT truncation: for up to 300 trades of the frozen config, rebuild
      close/high/low/ATR/crosses from data[:exit_bar+1] only and re-run the
      trade; exit bar and pnl must be identical.
  (3) EXIT future-perturbation: overwrite every bar AFTER the exit bar with
      random garbage (OHLC, ATR, spread, cross arrays) and re-run; must be
      identical.
  (4) independent pure-Python re-implementation of the exit rules (written
      from the spec, not from _run_one) must reproduce every IS and OOS
      trade (exit bar + pnl) of the frozen config.
  (5) POSITIVE CONTROL: the same Python simulator with a deliberate one-bar
      peek (stop/target tested against bar k+1's high/low while deciding at
      bar k) must FAIL audit (3); its IS %PF is printed to show what such a
      leak looks like.
No real MT5 trade log exists for any 84/200 EA -> every number here is a
SIMULATOR HYPOTHESIS TEST, not a bar-matched verdict.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C
from common import _run_one, njit
import ema84_200_crossover_search as E

HUGE = E.HUGE
BIG_HOLD = 10 ** 9
K_SERIES = 25
TFS = ("M15", "H1", "H4")
FOLDER_FLOOR, H4_EXCEPTION_FLOOR = 100, 30
OOS_MIN_N, LOW_POWER_N = 20, 50
N_AUDIT = 300


def build_grid():
    g = []
    for sl in (1.0, 1.5, 2.0, 3.0):
        for tp in (1.0, 2.0, 3.0, 4.0):
            g.append(("FIXED", sl, tp, 0.0, 0))
    for tr in (1.5, 2.0, 3.0):
        g.append(("TRAIL", tr, 0.0, tr, 0))
    for nb in (10, 20, 40):
        for sl in (0.0, 2.0):
            g.append(("TIME", sl, 0.0, 0.0, nb))
    return g


GRID = build_grid()
assert len(GRID) == K_SERIES


def cfg_name(cfg):
    fam, sl, tp, tr, nb = cfg
    if fam == "FIXED":
        return f"FIXED sl={sl:g}ATR tp={tp:g}ATR"
    if fam == "TRAIL":
        return f"TRAIL {tr:g}ATR"
    return f"TIME {nb}bars " + ("no-stop" if sl == 0 else f"sl={sl:g}ATR")


def cfg_args(cfg):
    """-> (stop distance in ATR units, target_r, max_hold, trail_atr)"""
    fam, sl, tp, tr, nb = cfg
    if fam == "FIXED":
        return sl, tp / sl, BIG_HOLD, 0.0
    if fam == "TRAIL":
        return tr, 0.0, BIG_HOLD, tr
    return (HUGE if sl == 0 else sl), 0.0, nb, 0.0


# ------------------------------------------------------------------ simulation

@njit(cache=True)
def sim_window(sig_bar, sig_dir, stop_atr, o, h, l, c, sp, atr, target_r, max_hold, trail, exl, exs, lo, hi):
    """One trade per crossover whose signal bar is in [lo, hi); every trade force-closed by bar hi-1
    (n=hi passed to _run_one), so an IS run never reads an OOS bar. Entry allowed on the previous
    trade's exit bar (the opposite cross closes and reverses)."""
    m = len(sig_bar)
    eb = np.empty(m, np.int64); xb = np.empty(m, np.int64); dd = np.empty(m); pp = np.empty(m)
    cnt = 0; last_exit = -1
    for s in range(m):
        i = sig_bar[s]
        if i < lo or i >= hi or i < last_exit or i + 1 >= hi:
            continue
        if not (atr[i] > 0):
            continue
        x, pnl = _run_one(i, sig_dir[s], stop_atr * atr[i], o, h, l, c, sp, atr, hi, target_r, max_hold, trail,
                          exl, exs)
        eb[cnt] = i; xb[cnt] = x; dd[cnt] = sig_dir[s]; pp[cnt] = pnl
        cnt += 1; last_exit = x
    return eb[:cnt], xb[:cnt], dd[:cnt], pp[:cnt]


@njit(cache=True)
def sim_rand(seed, p_fire, p_long, stop_atr, o, h, l, c, sp, atr, target_r, max_hold, trail, exl, exs, lo, hi,
             allowed):
    """Null: random bar + random direction, the IDENTICAL exit (same multiples, same cross backstop,
    same spread, same window cap). One position at a time."""
    np.random.seed(seed)
    out = np.empty(hi - lo); cnt = 0; last_exit = -1
    for i in range(lo, hi - 1):
        if i <= last_exit or not allowed[i] or not (atr[i] > 0):
            continue
        if np.random.random() >= p_fire:
            continue
        d = 1.0 if np.random.random() < p_long else -1.0
        x, pnl = _run_one(i, d, stop_atr * atr[i], o, h, l, c, sp, atr, hi, target_r, max_hold, trail, exl, exs)
        out[cnt] = pnl; cnt += 1; last_exit = x
    return out[:cnt]


def run_cfg(b, sb, sd, exl, exs, cfg, lo, hi):
    s_atr, tr_r, mh, trail = cfg_args(cfg)
    return sim_window(sb, sd, s_atr, b.open, b.high, b.low, b.close, b.spread_px, b.atr, tr_r, mh, trail,
                      exl, exs, lo, hi)


def null_pool(b, cfg, exl, exs, lo, hi, target_n, allowed, p_long=0.5, seed0=0, n_draws=C.N_RANDOM):
    s_atr, tr_r, mh, trail = cfg_args(cfg)
    args = (s_atr, b.open, b.high, b.low, b.close, b.spread_px, b.atr, tr_r, mh, trail, exl, exs, lo, hi, allowed)
    p_fire = min(0.5, max(1e-6, 3 * target_n / max(1, allowed[lo:hi].sum())))
    for it in range(10):
        m = np.mean([len(sim_rand(seed0 + 10_000 + it * 10 + r, p_fire, p_long, *args)) for r in range(5)])
        if m <= 0:
            p_fire = min(0.5, p_fire * 3); continue
        if abs(m - target_n) / target_n < 0.03:
            break
        p_fire = min(0.5, max(1e-7, p_fire * target_n / m))
    pool, ns = [], []
    for r in range(n_draws):
        t = sim_rand(seed0 + r, p_fire, p_long, *args)
        ns.append(len(t)); pool.append(C.pct_pf(t))
    pool = np.array(pool)
    return pool[np.isfinite(pool)], float(np.mean(ns))


# ------------------------------------------------------------------ exit audits

def ref_trade(i, d, stop_atr, target_r, max_hold, trail, o, h, l, c, sp, atr, exl, exs, n, peek=False):
    """Independent pure-Python implementation of the exit spec (docstring), NOT copied from _run_one.
    peek=True is the deliberate leak: bar k's stop/target are tested against bar k+1's range."""
    raw = c[i]; dist = stop_atr * atr[i]; long_ = d > 0
    entry = raw + sp[i + 1] if long_ else raw - sp[i + 1]
    stop = raw - dist if long_ else raw + dist
    tgt = (raw + target_r * dist if long_ else raw - target_r * dist) if target_r > 0 else None
    best = raw
    end = min(n - 1, i + max_hold)
    px, xbar = c[end], end
    for k in range(i + 1, end + 1):
        kk = min(k + 1, n - 1) if peek else k
        hi_k, lo_k, op = h[kk], l[kk], o[k]
        if long_:
            hit_stop = (op <= stop, lo_k <= stop)
            hit_tgt = (tgt is not None and op >= tgt, tgt is not None and hi_k >= tgt)
        else:
            hit_stop = (op >= stop, hi_k >= stop)
            hit_tgt = (tgt is not None and op <= tgt, tgt is not None and lo_k <= tgt)
        if hit_stop[0]:
            px, xbar = op, k; break
        if hit_stop[1]:
            px, xbar = stop, k; break
        if hit_tgt[0]:
            px, xbar = op, k; break
        if hit_tgt[1]:
            px, xbar = tgt, k; break
        if (exl[k] if long_ else exs[k]):
            px, xbar = c[k], k; break
        if trail > 0 and np.isfinite(atr[k]):
            best = max(best, c[k]) if long_ else min(best, c[k])
            ns = best - trail * atr[k] if long_ else best + trail * atr[k]
            stop = max(stop, ns) if long_ else min(stop, ns)
    pnl = (px - entry) if long_ else (entry - px)
    return xbar, pnl / entry


def ref_window(b, sb, sd, exl, exs, cfg, lo, hi, peek=False):
    s_atr, tr_r, mh, trail = cfg_args(cfg)
    out = []; last = -1
    for i, d in zip(sb, sd):
        if i < lo or i >= hi or i < last or i + 1 >= hi or not (b.atr[i] > 0):
            continue
        x, p = ref_trade(i, d, s_atr, tr_r, mh, trail, b.open, b.high, b.low, b.close, b.spread_px, b.atr,
                         exl, exs, hi, peek)
        out.append((i, x, d, p)); last = x
    return out


def exit_audits(b, sb, sd, exl, exs, cfg, log, tag):
    s_atr, tr_r, mh, trail = cfg_args(cfg)
    ok = True
    # (4) independent re-implementation, every IS and OOS trade
    for side, lo, hi in (("IS", b.is_lo, b.is_hi), ("OOS", b.oos_lo, b.oos_hi)):
        eb, xb, dd, pp = run_cfg(b, sb, sd, exl, exs, cfg, lo, hi)
        ref = ref_window(b, sb, sd, exl, exs, cfg, lo, hi)
        same = len(ref) == len(eb) and all(r[0] == e and r[1] == x and abs(r[3] - p) < 1e-12
                                           for r, e, x, p in zip(ref, eb, xb, pp))
        ok &= same
        log(f"  [{tag}] independent Python exit re-implementation, {side}: {len(ref)} vs {len(eb)} trades, "
            f"{'ALL IDENTICAL (exit bar + pnl)' if same else 'MISMATCH'}")
    eb, xb, dd, pp = run_cfg(b, sb, sd, exl, exs, cfg, b.is_lo, b.n)
    rng = np.random.default_rng(5)
    pick = rng.choice(len(eb), size=min(N_AUDIT, len(eb)), replace=False)
    bad_t = bad_p = 0
    for j in pick:
        i, x, d = int(eb[j]), int(xb[j]), dd[j]
        ref_x, ref_p = _run_one(i, d, s_atr * b.atr[i], b.open, b.high, b.low, b.close, b.spread_px, b.atr, b.n,
                                tr_r, mh, trail, exl, exs)
        # (2) truncation: everything rebuilt from data[:x+1]
        hh, ll, cc = b.high[:x + 1], b.low[:x + 1], b.close[:x + 1]
        at = C.wilder_atr(hh, ll, cc, 14)
        u, dn_ = E.crosses(cc)
        tx, tp_ = _run_one(i, d, s_atr * at[i], b.open[:x + 1], hh, ll, cc, b.spread_px[:x + 1], at, x + 1,
                           tr_r, mh, trail, dn_.astype(np.bool_), u.astype(np.bool_))
        bad_t += not (tx == ref_x and abs(tp_ - ref_p) < 1e-12)
        # (3) perturb every bar after x
        o2, h2, l2, c2, s2, a2 = (arr.copy() for arr in (b.open, b.high, b.low, b.close, b.spread_px, b.atr))
        el2, es2 = exl.copy(), exs.copy()
        m = b.n - x - 1
        if m > 0:
            junk = c2[x] * (1 + rng.normal(0, 0.05, m))
            o2[x + 1:] = junk; c2[x + 1:] = junk[::-1]
            h2[x + 1:] = junk * 1.2; l2[x + 1:] = junk * 0.8
            s2[x + 1:] = rng.random(m); a2[x + 1:] = rng.random(m) * c2[x]
            el2[x + 1:] = rng.random(m) < 0.5; es2[x + 1:] = rng.random(m) < 0.5
        px, pp2 = _run_one(i, d, s_atr * b.atr[i], o2, h2, l2, c2, s2, a2, b.n, tr_r, mh, trail, el2, es2)
        bad_p += not (px == ref_x and abs(pp2 - ref_p) < 1e-12)
    ok &= bad_t == 0 and bad_p == 0
    log(f"  [{tag}] EXIT truncation (OHLC/ATR/crosses rebuilt from data[:exit_bar+1], {len(pick)} trades): "
        f"mismatches={bad_t} -> {'PASS' if bad_t == 0 else 'FAIL - LOOKAHEAD'}")
    log(f"  [{tag}] EXIT future-perturbation (all bars after the exit bar replaced by garbage, {len(pick)} trades): "
        f"mismatches={bad_p} -> {'PASS' if bad_p == 0 else 'FAIL - LOOKAHEAD'}")
    # (5) positive control: one-bar peek must be caught by the perturbation test
    leak = ref_window(b, sb, sd, exl, exs, cfg, b.is_lo, b.n, peek=True)
    caught = 0; tried = 0
    for (i, x, d, p) in [leak[j] for j in rng.choice(len(leak), size=min(100, len(leak)), replace=False)]:
        if x + 1 >= b.n:
            continue
        tried += 1
        o2, h2, l2 = b.open.copy(), b.high.copy(), b.low.copy()
        h2[x + 1:] = b.close[x] * 0.5; l2[x + 1:] = b.close[x] * 0.5   # garbage after x
        x2, p2 = ref_trade(i, d, s_atr, tr_r, mh, trail, o2, h2, l2, b.close, b.spread_px, b.atr, exl, exs, b.n,
                           peek=True)
        caught += not (x2 == x and abs(p2 - p) < 1e-12)
    leak_is = [p for (i, x, d, p) in leak if i < b.is_hi]
    log(f"  [{tag}] POSITIVE CONTROL (stop/target tested on bar k+1's range): perturbation test caught it on "
        f"{caught}/{tried} trades ({'DETECTED as required' if caught > 0 else 'NOT DETECTED - audit is blind'}); "
        f"leaky IS %PF={C.pct_pf(leak_is):.3f} (what a one-bar peek would look like)")
    ok &= caught > 0
    return ok


# ------------------------------------------------------------------ reporting helpers

def side_stats(b, eb, xb, dd, pp):
    lp, spp = pp[dd > 0], pp[dd < 0]
    hold = xb - eb
    return (f"n={len(pp)} win%={100 * (pp > 0).mean():.1f} %PF={C.pct_pf(pp):.3f} sum%={100 * pp.sum():.1f} | "
            f"LONG n={len(lp)} %PF={C.pct_pf(lp):.3f} sum%={100 * lp.sum():.1f} | SHORT n={len(spp)} "
            f"%PF={C.pct_pf(spp):.3f} sum%={100 * spp.sum():.1f} | median hold={np.median(hold):.0f} bars")


def by_period(b, eb, dd, pp, log, symbol):
    yrs = pd.to_datetime(b.time[eb]).year
    parts = []
    for y in sorted(set(yrs)):
        m = yrs == y
        parts.append(f"{y}: n={m.sum()} %PF={C.pct_pf(pp[m]):.2f} sum%={100 * pp[m].sum():+.1f}")
    log("      by entry year: " + "; ".join(parts))
    if symbol == "GOLD":
        for lab, m in (("2021-2023", yrs < 2024), ("2024+", yrs >= 2024)):
            if m.sum():
                log(f"      {lab}: n={m.sum()} %PF={C.pct_pf(pp[m]):.3f} (long %PF={C.pct_pf(pp[m & (dd > 0)]):.3f} "
                    f"n={(m & (dd > 0)).sum()}, short %PF={C.pct_pf(pp[m & (dd < 0)]):.3f} n={(m & (dd < 0)).sum()})")


# ------------------------------------------------------------------ pipeline

def run_series(df15, point, symbol, tf, log, k_total):
    b = E.make_bars(df15, point, symbol, tf)
    up, dn = E.crosses(b.close)
    sb = np.where(up | dn)[0].astype(np.int64)
    sd = np.where(up[sb], 1.0, -1.0)
    exl, exs = dn.astype(np.bool_), up.astype(np.bool_)
    n_is_cross = int((up | dn)[b.is_lo:b.is_hi].sum())
    floor = FOLDER_FLOOR if tf != "H4" else H4_EXCEPTION_FLOOR
    log(f"\n{'=' * 110}\n{symbol} {tf} - EMA({E.FAST})xEMA({E.SLOW}) entry, exit grid K={K_SERIES}\n{b.describe()}\n"
        f"point={point}; IS crosses={n_is_cross} OOS crosses={int((up | dn)[b.oos_lo:].sum())}; IS floor={floor}"
        f"{' (DECLARED H4 EXCEPTION, below folder floor 100)' if floor != FOLDER_FLOOR else ''}\n{'=' * 110}")
    res = dict(series=f"{symbol} {tf}")
    if n_is_cross < floor:
        log(f"  IS crosses {n_is_cross} < {floor} -> NOT SEARCHED (pre-declared), no verdict, not in K.")
        res["verdict"] = "NOT SEARCHED (IS n too small)"; return res, False
    # entry audits (entry code unchanged; re-confirm on these exact bars)
    ok = E.truncation_audit(b.close, up, dn, log, f"{tf} entry")
    if tf != "M15":
        ok &= E.resample_audit(df15, tf, b, up, dn, log)

    # ---- IS search (IS bars only)
    rows = []
    for cfg in GRID:
        eb, xb, dd, pp = run_cfg(b, sb, sd, exl, exs, cfg, b.is_lo, b.is_hi)
        rows.append(dict(cfg=cfg, n=len(pp), pf=C.pct_pf(pp), win=100 * (pp > 0).mean() if len(pp) else np.nan))
    log(f"  IS grid (all {K_SERIES}, IS bars only; trades force-closed at the last IS bar):")
    for r in sorted(rows, key=lambda r: -r["pf"]):
        log(f"     {cfg_name(r['cfg']):<28} IS n={r['n']:>4}  win%={r['win']:5.1f}  IS %PF={r['pf']:.3f}")
    valid = [r for r in rows if r["n"] >= floor and np.isfinite(r["pf"])]
    best = max(valid, key=lambda r: r["pf"])
    cfg = best["cfg"]
    log(f"  FROZEN IS WINNER: {cfg_name(cfg)}  IS n={best['n']}  IS %PF={best['pf']:.3f}  "
        f"({sum(r['pf'] > 1 for r in valid)}/{len(valid)} grid configs had IS %PF > 1)")
    res.update(cfg=cfg_name(cfg), is_n=best["n"], is_pf=best["pf"])

    # ---- exit audits on the frozen config
    ok &= exit_audits(b, sb, sd, exl, exs, cfg, log, f"{tf} exit")
    res["audit"] = "PASS" if ok else "FAIL"
    if not ok:
        log("  AUDIT FAILED -> results for this series NOT trustworthy")

    allowed = (np.arange(b.n) >= E.WARM) & np.isfinite(b.atr)
    # ---- IS behaviour of the frozen config (2014-2020 for Gold): own null, best-of-25 corrected
    eb, xb, dd, pp = run_cfg(b, sb, sd, exl, exs, cfg, b.is_lo, b.is_hi)
    log(f"  IS  frozen: {side_stats(b, eb, xb, dd, pp)}; buy&hold={E.drift(b, b.is_lo, b.is_hi):+.1f}%")
    by_period(b, eb, dd, pp, log, "")
    ipool, imn = null_pool(b, cfg, exl, exs, b.is_lo, b.is_hi, len(pp), allowed, seed0=500_000)
    p_is1 = float((ipool >= best["pf"]).mean()); p_isk, med_isk = C.best_of_k_p(ipool, best["pf"], K_SERIES)
    log(f"      IS null A (mean n={imn:.0f} vs {len(pp)}): median={np.median(ipool):.3f} -> IS winner p(K=1)={p_is1:.4f}, "
        f"vs best-of-{K_SERIES} random (median {med_isk:.3f}) p={p_isk:.4f}")
    res.update(p_is1=p_is1, p_isk=p_isk)

    # ---- OOS, evaluated once
    eb, xb, dd, pp = run_cfg(b, sb, sd, exl, exs, cfg, b.oos_lo, b.oos_hi)
    n, pf = len(pp), C.pct_pf(pp)
    res.update(oos_n=n, oos_pf=pf, oos_long_pf=C.pct_pf(pp[dd > 0]), oos_short_pf=C.pct_pf(pp[dd < 0]))
    log(f"  OOS frozen (untouched): {side_stats(b, eb, xb, dd, pp)}; buy&hold={E.drift(b, b.oos_lo, b.oos_hi):+.1f}%")
    by_period(b, eb, dd, pp, log, symbol)
    if n < OOS_MIN_N:
        log(f"  OOS n={n} < {OOS_MIN_N} -> INSUFFICIENT DATA"); res["verdict"] = "INSUFFICIENT DATA"; return res, True
    longf = float((dd > 0).mean())
    ps = {}
    for lab, pl, s0 in (("A", 0.5, 0), ("Ad", longf, 900_000)):
        pool, mn = null_pool(b, cfg, exl, exs, b.oos_lo, b.oos_hi, n, allowed, p_long=pl, seed0=s0)
        p1 = float((pool >= pf).mean())
        pk, medk = C.best_of_k_p(pool, pf, K_SERIES)
        pt, medt = C.best_of_k_p(pool, pf, k_total)
        match = abs(mn - n) / n <= 0.10
        ps[lab] = (p1, pk, pt, match, 100 * float((pool < pf).mean()))
        log(f"      null {lab} (random timing, p_long={pl:.2f}, same exit + cross backstop + real spread; {len(pool)} "
            f"draws, mean n={mn:.0f} vs {n}{'' if match else ' -> n-MISMATCH, excluded'}): median={np.median(pool):.3f} "
            f"p95={np.percentile(pool, 95):.3f} -> real at {ps[lab][4]:.1f}th pct; p(K=1)={p1:.4f} "
            f"p(K={K_SERIES})={pk:.4f} (best-of-K median {medk:.3f}) p(K={k_total})={pt:.4f}")
    use = [v for v in ps.values() if v[3]] or list(ps.values())
    pk = max(v[1] for v in use)
    v = C.verdict(pk)
    if floor != FOLDER_FLOOR or n < LOW_POWER_N:
        v += " (LOW POWER" + ("; below folder IS floor" if floor != FOLDER_FLOOR else "") + ")"
    res.update(pA1=ps["A"][0], pAd1=ps["Ad"][0], pAk=ps["A"][1], pAdk=ps["Ad"][1], pAt=ps["A"][2],
               pAdt=ps["Ad"][2], pctA=ps["A"][4], pctAd=ps["Ad"][4], verdict=v)
    log(f"  VERDICT (worse of A/Ad at K={K_SERIES}): {v}")

    # ---- post-hoc diagnostic, NOT used for selection: OOS of every grid config
    oos_all = []
    for c2 in GRID:
        r = run_cfg(b, sb, sd, exl, exs, c2, b.oos_lo, b.oos_hi)
        oos_all.append((C.pct_pf(r[3]), cfg_name(c2)))
    oos_all.sort(reverse=True)
    pf_arr = np.array([x[0] for x in oos_all])
    log(f"  DIAGNOSTIC ONLY (not used for selection; shows whether the frozen pick was unlucky): OOS %PF across all "
        f"{K_SERIES} configs: median={np.median(pf_arr):.3f}, {int((pf_arr > 1).sum())}/{K_SERIES} > 1.0; hindsight-best "
        f"{oos_all[0][1]} OOS %PF={oos_all[0][0]:.3f} (picked with hindsight: compare to the best-of-{K_SERIES} "
        f"null median above, not to p(K=1))")
    res["hind"] = f"{oos_all[0][1]} {oos_all[0][0]:.3f}"
    res["oos_med_grid"] = float(np.median(pf_arr))
    return res, True


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/ema84_200_exit_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    log(f"EXIT GRID (K={K_SERIES} per series): " + "; ".join(cfg_name(g) for g in GRID))
    # pre-declared searched series: Gold M15/H1/H4(exception), BTC M15/H1 -> 5 series
    K_TOTAL = 5 * K_SERIES
    log(f"Series searched (pre-declared): GOLD M15, H1, H4 (exception floor 30), BTCUSD M15, H1; BTCUSD H4 not searched "
        f"(18 IS crosses). K_total = {K_TOTAL}.")
    allres = []
    for sym in ("GOLD", "BTCUSD"):
        df15, point = E.load(sym, log)
        for tf in TFS:
            r, _ = run_series(df15, point, sym, tf, log, K_TOTAL)
            allres.append(r)
    log(f"\n{'=' * 110}\nSUMMARY (verdict = worse of null A / Ad at K={K_SERIES}; p at K={K_TOTAL} = across all searched "
        f"series)\n{'=' * 110}")
    log(f"{'series':<12}{'frozen IS winner':<28}{'aud':>5}{'IS n':>6}{'IS%PF':>7}{'ISp25':>7}{'OOS n':>7}{'OOS%PF':>8}"
        f"{'L %PF':>7}{'S %PF':>7}{'pctA':>6}{'pA1':>7}{'pAd1':>7}{'pA25':>7}{'pAd25':>7}{'pA125':>7}{'pAd125':>7}  verdict")
    for r in allres:
        g = lambda k, f="{:.3f}": (f.format(r[k]) if k in r and r[k] == r[k] else "-")
        log(f"{r['series']:<12}{r.get('cfg', '-'):<28}{r.get('audit', '-'):>5}{r.get('is_n', '-'):>6}{g('is_pf'):>7}"
            f"{g('p_isk'):>7}{r.get('oos_n', '-'):>7}{g('oos_pf'):>8}{g('oos_long_pf'):>7}{g('oos_short_pf'):>7}"
            f"{g('pctA', '{:.0f}'):>6}{g('pA1'):>7}{g('pAd1'):>7}{g('pAk'):>7}{g('pAdk'):>7}{g('pAt'):>7}{g('pAdt'):>7}"
            f"  {r['verdict']}")
    log("Diagnostic (NOT selection): median OOS %PF over the whole grid / hindsight-best config per series:")
    for r in allres:
        if "hind" in r:
            log(f"   {r['series']:<12} grid median OOS %PF={r['oos_med_grid']:.3f}; hindsight-best {r['hind']}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
