"""
MECHANICAL ELLIOTT WAVE on HIGHER TIMEFRAMES (H4, D1) - follow-up to
elliott_wave_mechanical_search.py (M15: DOES NOT SURVIVE on Gold or BTC).

User question: "could it be different settings, higher time frames?". This
script re-runs the IDENTICAL construction - imported, not re-written - from
elliott_wave_mechanical_search.py: the same causal ATR-reversal ZigZag
(zigzag_atr), the same impulse validator (valid_impulse: R1, R2, R3
strict/relaxed, structural P3>P1, optional R4), the same single hypothesis
(fade the completed impulse on wave-5 pivot confirmation), the same exit
(stop = P5 +/- 0.25 ATR, target = P4, per-trade target_r, MAX_HOLD = 500
bars backstop, common._run_one), the same random-timing null (sim_random_var /
random_pool_var: matched trade count, real spread, (stop, target_r) pairs from
the real OOS trades), the same lookahead audit (audit()) and the same ABC
diagnostic. Only the BAR SERIES changes.

GRID per timeframe: the SAME K=12 (ZZ_ATR_MULT {2,3,5} x W4_RULE x
REQ_W5_BEYOND_W3). The ZigZag reversal amount is in ATR(14) units of the bar
series itself, so "3 ATR" already rescales with the timeframe; re-using the
M15 grid unchanged adds no new tuned choice. MAX_HOLD stays 500 BARS
(a backstop, fixed, never tuned - it is bar-count based exactly as ATR is).
HONEST FAMILY K: the timeframe itself was searched in response to the M15
failure, so per instrument the Elliott construction has now been evaluated on
12 (M15) + 12 (H4) + 12 (D1) = 36 literal configurations. Both p(K=12, this
timeframe) and p(K=36, whole Elliott family for the instrument) are reported;
the family K is the honest one for "does Elliott work on SOME timeframe".

DATA - no native H4/D1 history long enough exists in this environment
(GOLD_H4.csv starts 2022-07-04, i.e. AFTER the 2021 IS/OOS boundary; no
BTC H4/D1, no Silver data of any timeframe). H4/D1 bars are therefore built
from the staged M15 CSVs by resample_closed():
  - windows aligned to broker SERVER-time boundaries: H4 = floor to 4h
    (00,04,...,20), D1 = server midnight - the same boundaries MT5 uses
    (cross-checked below against the native GOLD_H4.csv over its overlap);
  - an M15 bar stamped t covers [t, t+15m); a window [T, T+L) contains only
    M15 bars with T <= t < T+L, so every M15 bar in it has closed by T+L;
  - a window is kept ONLY if T+L <= clock, clock = last M15 stamp + 15m:
    a still-forming final bar can never enter the test (BTC's data ends
    12:15 so its last H4 and D1 bars are dropped);
  - the first window is dropped if it starts before the first M15 bar
    (partial at the START - not a leak, just a truncated range);
  - spread = mean M15 spread in the window (common.resample convention),
    converted to price with the CSV's own meta_point.
  Gold contamination: the pre-2014-06-13 rows are 2001-2012 DAILY and 2013
  HOURLY bars, all with spread = 0 (frictionless, unknown alignment). The
  H4/D1 boundary is therefore the SAME as M15's: trimmed at 2014-06-13 01:30
  before resampling. (Pre-2014 daily rows could in principle make D1 bars,
  but with zero spread they violate the real-cost rule and would move the
  frozen split - not used.)
  Signal knowability: an HTF bar i is known at clock T_i + L, so the
  equivalent M15-side lookup is "last HTF bar whose END <= t + 15m" =
  searchsorted(htf_end, t + 15m, side="right") - 1. The CLAUDE.md pattern
  searchsorted(htf_time, t + bar_len, side="right") - 2 is checked too
  (it is never leaky; it is one bar conservative across session gaps).

LOOKAHEAD AUDIT, on top of the imported HTF-level audit():
  (a)+(b)+(c) as M15: structural asserts, truncation of the HTF arrays to
      [:i+1], deliberately-leaky positive control (entry at P5's own bar);
  (d) RESAMPLE truncation: for up to 300 signals, cut the M15 frame at the
      clock T_i + L, rebuild the HTF bars from that alone, rerun ATR +
      ZigZag + validator, require identical bars [0..i] and the identical
      signal on bar i;
  (e) RESAMPLE positive control: cut the M15 frame strictly INSIDE bar i
      and resample WITHOUT the completeness filter (the "forming bar" bug):
      the comparison must detect the mismatch; with the filter on, bar i
      must simply not exist yet.

VERDICT LABELS: "INSUFFICIENT DATA" (no combo reaches IS n>=100, or OOS
n<20) is NOT "does not survive" - it is no evidence either way.
"""
import sys
import os
import itertools
import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/silver_btc")
import common as C
import elliott_wave_mechanical_search as EW

TF_MIN = {"H4": 240, "D1": 1440}
FAMILY_K = 36            # 12 (M15, already run) + 12 (H4) + 12 (D1) per instrument
M15 = pd.Timedelta(minutes=15)
N_RESAMPLE_AUDIT = 300


# ------------------------------------------------------------------ resampling

def resample_closed(df15, tf, clock=None, drop_partial=True):
    """Build HTF bars from M15 rows. clock = the wall-clock time at which we
    stand (default: last M15 stamp + 15m). A window [T, T+L) is kept only if
    T+L <= clock (fully closed). drop_partial=False is the deliberate BUG for
    the positive control (keeps the forming bar)."""
    L = pd.Timedelta(minutes=TF_MIN[tf])
    if clock is None:
        clock = df15["time"].iloc[-1] + M15
    t = df15["time"]
    start = t.dt.floor("4h" if tf == "H4" else "D")
    g = df15.groupby(start.values)
    out = pd.DataFrame(dict(open=g["open"].first(), high=g["high"].max(), low=g["low"].min(),
                            close=g["close"].last(), tick_volume=g["tick_volume"].sum(),
                            spread=g["spread"].mean(), n15=g["open"].size()))
    out.index.name = "time"
    out = out.reset_index()
    if drop_partial:
        out = out[out["time"] + L <= clock]
    if len(out) and out["time"].iloc[0] < t.iloc[0]:
        out = out.iloc[1:]
    return out.reset_index(drop=True)


def load_htf(symbol, tf, log=None):
    df15, point = C.load_m15(symbol)
    if symbol == "GOLD":
        n0 = len(df15)
        df15 = df15[df15["time"] >= EW.GOLD_REAL_M15_START].reset_index(drop=True)
        if log:
            log(f"[GOLD contamination filter] dropped {n0 - len(df15)} pre-{EW.GOLD_REAL_M15_START} M15-file rows "
                f"(2001-2012 daily + 2013 hourly bars, all spread=0) BEFORE resampling to {tf}")
    return df15, point


# ------------------------------------------------------------------ alignment checks

def check_vs_native_h4(df_h4, log):
    path = f"{C.DATA_DIR}/GOLD_H4.csv"
    if not os.path.exists(path):
        log("  native GOLD_H4.csv not present - alignment cross-check skipped"); return
    meta = C.read_meta(path)
    assert abs(float(meta["meta_point"]) - 0.01) < 1e-12
    nat = pd.read_csv(path, skiprows=1)
    nat["time"] = pd.to_datetime(nat["time"], format="%Y.%m.%d %H:%M:%S")
    m = nat.merge(df_h4, on="time", suffixes=("_n", "_r"))
    only_n = len(set(nat["time"]) - set(df_h4["time"]))
    only_r = len(set(df_h4.loc[df_h4["time"] >= nat["time"].iloc[0], "time"]) - set(nat["time"]))
    tol = 0.011
    ok = {c: float((np.abs(m[f"{c}_n"] - m[f"{c}_r"]) <= tol).mean()) for c in ("open", "high", "low", "close")}
    log(f"  H4 alignment vs NATIVE GOLD_H4.csv ({nat['time'].iloc[0]} -> {nat['time'].iloc[-1]}): "
        f"{len(m)} common bars, {only_n} native-only, {only_r} resampled-only; exact-match (<=1 point) "
        + ", ".join(f"{k}={100 * v:.2f}%" for k, v in ok.items()))


def check_knowability(df15, htf, tf, sig_bars, log):
    """For each signal bar i, the M15 bar on whose close bar i becomes known is the last M15 row with
    time < T_i + L. Map it back with the end-time lookup and with the CLAUDE.md pattern."""
    L = pd.Timedelta(minutes=TF_MIN[tf])
    h_time = htf["time"].values
    h_end = (htf["time"] + L).values
    t15 = df15["time"].values
    bad_exact = early_doc = leak_doc = short = 0
    for i in sig_bars:
        k = int(np.searchsorted(t15, h_end[i], side="left")) - 1   # last M15 bar inside window i
        tq = t15[k] + np.timedelta64(15, "m")                      # its close
        j_exact = int(np.searchsorted(h_end, tq, side="right")) - 1
        j_doc = int(np.searchsorted(h_time, tq, side="right")) - 2
        if tq == h_end[i]:
            bad_exact += j_exact != i          # full window: known exactly on its last M15 close
        else:
            short += 1                         # early close / missing final slots: known only at clock T_i+L,
            bad_exact += j_exact >= i          # so at the last M15 close it must NOT be known yet
        early_doc += j_doc < i
        leak_doc += j_doc > i
        # one M15 bar earlier (clock = open of the closing M15 bar), bar i must NOT yet be known
        bad_exact += int(np.searchsorted(h_end, t15[k], side="right")) - 1 >= i
    log(f"  knowability check on {len(sig_bars)} signals ({short} short windows: early close / missing final M15 "
        f"slots, known only at the window-end clock): end-time lookup errors={bad_exact}; CLAUDE.md "
        f"searchsorted(htf_time, t+15m, 'right')-2 at the last M15 close -> leaky={leak_doc}, "
        f"one-bar-conservative={early_doc} (window closed before a session gap / short window)")
    return bad_exact == 0 and leak_doc == 0


# ------------------------------------------------------------------ resample-level audit

def resample_audit(df15, tf, b_full, cfg, sigs, log, rng_seed=23):
    L = pd.Timedelta(minutes=TF_MIN[tf])
    rng = np.random.default_rng(rng_seed)
    pick = rng.choice(len(sigs), size=min(N_RESAMPLE_AUDIT, len(sigs)), replace=False)
    t15 = df15["time"].values
    htime = pd.to_datetime(b_full.time)
    fails_bar = fails_sig = 0
    leak_detect = leak_n = filt_ok = 0
    full =dict(open=b_full.open, high=b_full.high, low=b_full.low, close=b_full.close)
    for idx in pick:
        i = int(sigs[idx][0])
        clock = htime[i] + L
        cut = int(np.searchsorted(t15, np.datetime64(clock), side="left"))
        d = df15.iloc[:cut]
        h = resample_closed(d, tf, clock=clock)
        if len(h) != i + 1 or not all(np.array_equal(h[c].values.astype(float), full[c][:i + 1])
                                      for c in ("open", "high", "low", "close")):
            fails_bar += 1; fails_sig += 1; continue
        hb, hl, hc = h["high"].values.astype(float), h["low"].values.astype(float), h["close"].values.astype(float)
        atr_t = C.wilder_atr(hb, hl, hc, 14)
        s_t, _ = EW.detect(hb, hl, hc, atr_t, *cfg)
        want = sigs[idx]
        got = [s for s in s_t if s[0] == i]
        if not got or got[-1][1] != want[1] or abs(got[-1][2] - want[2]) > 1e-9 or abs(got[-1][3] - want[3]) > 1e-9:
            fails_sig += 1
        # (e) positive control: clock strictly inside bar i
        inside = df15.iloc[int(np.searchsorted(t15, np.datetime64(htime[i]), side="left")):cut]
        if len(inside) >= 2:
            kk = int(rng.integers(1, len(inside)))            # keep >=1 but < all M15 bars of bar i
            clock_in = inside["time"].iloc[kk]
            d_in = df15.iloc[:int(np.searchsorted(t15, np.datetime64(clock_in), side="left"))]
            bug = resample_closed(d_in, tf, clock=clock_in, drop_partial=False)
            good = resample_closed(d_in, tf, clock=clock_in)
            leak_n += 1
            if len(bug) == i + 1 and not all(np.isclose(bug[c].iloc[i], full[c][i]) for c in ("high", "low", "close")):
                leak_detect += 1
            filt_ok += (len(good) == i) and bool(np.all(good["time"].values == b_full.time[:i]))
    ok = fails_bar == 0 and fails_sig == 0
    log(f"  RESAMPLE truncation audit: {len(pick)} signals, M15 cut at the signal bar's close clock, HTF bars "
        f"rebuilt -> bar mismatches={fails_bar}, signal mismatches={fails_sig} "
        f"({'PASS - no future M15 data used' if ok else 'FAIL - LOOKAHEAD'})")
    log(f"  RESAMPLE positive control (forming-bar bug, clock strictly inside bar i, no completeness filter): "
        f"detected as mismatch in {leak_detect}/{leak_n} cases; with the filter ON bar i is correctly ABSENT in "
        f"{filt_ok}/{leak_n} cases")
    return ok


# ------------------------------------------------------------------ helpers

def exit_stats(b, sigs, lo, hi):
    """Hold length and share of trades closed by the MAX_HOLD backstop (frozen winner, OOS)."""
    z = np.zeros(b.n, dtype=np.bool_)
    holds, timed, last_exit = [], 0, -1
    for s in sigs:
        i = s[0]
        if i < lo or i >= hi or i <= last_exit or i + 1 >= b.n or not (b.atr[i] > 0):
            continue
        xb, _ = C._run_one(i, s[1], s[2], b.open, b.high, b.low, b.close, b.spread_px, b.atr, b.n, s[3],
                           EW.MAX_HOLD, 0.0, z, z)
        holds.append(xb - i); timed += (xb == min(b.n - 1, i + EW.MAX_HOLD)); last_exit = xb
    return (float(np.median(holds)) if holds else float("nan")), timed, len(holds)


# ------------------------------------------------------------------ pipeline

def run_tf(symbol, tf, log):
    df15, point = load_htf(symbol, tf, log)
    htf = resample_closed(df15, tf)
    b = C.Bars(htf, point, symbol)
    grid = list(itertools.product(EW.ZZ_ATR_MULTS, EW.W4_RULES, EW.REQ_W5S))
    K = len(grid)
    exp15 = TF_MIN[tf] // 15
    log(f"\n{'=' * 90}\n{symbol} {tf} (resampled from M15, closed bars only) -- Mechanical Elliott 5-wave impulse "
        f"-> fade into ABC\n{b.describe()}\npoint={point} (from CSV meta header); median M15 bars per {tf} bar="
        f"{int(htf['n15'].median())} (nominal {exp15}); {tf} bars with < half the nominal M15 count: "
        f"{int((htf['n15'] < exp15 / 2).sum())}\nGRID K={K} per timeframe (same as M15); honest family K="
        f"{FAMILY_K} (M15+H4+D1); selection = highest IS %PF with IS n>={EW.MIN_IS_N}\n{'=' * 90}")
    if symbol == "GOLD" and tf == "H4":
        check_vs_native_h4(htf, log)

    rows, cache = [], {}
    for cfg in grid:
        sigs, piv = EW.detect(b.high, b.low, b.close, b.atr, *cfg)
        cache[cfg] = (sigs, piv)
        r = EW.run_sigs(b, sigs, b.is_lo, b.is_hi)
        rows.append(dict(cfg=cfg, n=len(r[2]), pf=C.pct_pf(r[2]),
                         npiv=int(((piv[3] >= b.is_lo) & (piv[3] < b.is_hi)).sum()),
                         nsig=sum(1 for s in sigs if b.is_lo <= s[0] < b.is_hi),
                         nsig_oos=sum(1 for s in sigs if b.oos_lo <= s[0] < b.oos_hi)))
    log("all combos (IS): cfg -> confirmed pivots / valid-impulse signals / trades taken / IS %PF "
        "[OOS signal COUNT only, no OOS performance looked at]")
    for r in rows:
        log(f"   {r['cfg']}: pivots={r['npiv']:>5}  signals={r['nsig']:>4}  n={r['n']:>4}  IS %PF={r['pf']:.3f}"
            f"   [OOS signals={r['nsig_oos']}]")
    valid = [r for r in rows if r["n"] >= EW.MIN_IS_N and np.isfinite(r["pf"])]
    valid.sort(key=lambda r: r["pf"], reverse=True)
    log(f"{len(valid)}/{K} combos had IS n>={EW.MIN_IS_N}; {sum(r['pf'] > 1 for r in valid)} have IS %PF > 1.0")

    # The lookahead audit is run on the combo that would be frozen, or (if none qualifies) on the
    # combo with the most IS trades, so the causality claim is checked at every timeframe.
    if valid:
        best = valid[0]
    else:
        best = max(rows, key=lambda r: r["n"])
    cfg = best["cfg"]
    sigs, piv = cache[cfg]
    if not valid:
        log(f"(audit-only combo, NOT a frozen winner: {cfg}, the max-IS-trade combo, IS n={best['n']})")
    else:
        log(f"FROZEN WINNER (IS only): {cfg}  IS n={best['n']}  IS %PF={best['pf']:.3f}")
    ok = True
    if len(sigs) >= 1:
        ok = EW.audit(b, cfg, sigs, piv, log, "REAL")
        leak_sigs, leak_piv = EW.detect(b.high, b.low, b.close, b.atr, *cfg, leaky=True)
        lr = EW.run_sigs(b, leak_sigs, b.is_lo, b.is_hi)
        log(f"  positive control (DELIBERATELY LEAKY: enter at P5's own pivot bar): IS n={len(lr[2])} "
            f"IS %PF={C.pct_pf(lr[2]):.3f}  <- what a pivot-confirmation leak would look like")
        EW.audit(b, cfg, leak_sigs, leak_piv, log, "LEAKY control (must FAIL)")
        ok &= resample_audit(df15, tf, b, cfg, sigs, log)
        ok &= check_knowability(df15, htf, tf, [s[0] for s in sigs], log)
    if not ok:
        log("LOOKAHEAD AUDIT FAILED -> results NOT trustworthy.")
        return dict(label=f"{symbol} {tf}", K=K, verdict="INVALID (lookahead audit failed)")
    if not valid:
        log(f"NO combo reached IS n>={EW.MIN_IS_N} (max IS n={best['n']}) -> INSUFFICIENT DATA for a meaningful "
            f"verdict at {tf}. The threshold is NOT lowered; OOS performance is not examined.")
        return dict(label=f"{symbol} {tf}", K=K, max_is_n=best["n"],
                    verdict="INSUFFICIENT DATA (no combo reaches IS n>=100) - no verdict either way")

    is_r = EW.run_sigs(b, sigs, b.is_lo, b.is_hi)
    is_pool, _, _ = EW.random_pool_var(b, is_r[3], is_r[4], len(is_r[2]), b.is_lo, b.is_hi, seed0=500_000)
    p_is_k, med_is_k = C.best_of_k_p(is_pool, best["pf"], K)
    log(f"IS sanity: random-timing IS pool median={np.median(is_pool):.3f}; IS winner vs best-of-{K} random "
        f"(median {med_is_k:.3f}): p={p_is_k:.4f}")

    r = EW.run_sigs(b, sigs, b.oos_lo, b.oos_hi)
    oos_dir, oos_pnl, oos_atr, oos_tr = r[1], r[2], r[3], r[4]
    n_oos = len(oos_pnl); oos_pf = C.pct_pf(oos_pnl)
    res = dict(label=f"{symbol} {tf}", K=K, cfg=cfg, is_n=best["n"], is_pf=round(float(best["pf"]), 3),
               oos_n=n_oos, oos_pf=round(float(oos_pf), 3) if n_oos else None, p_is_k=p_is_k)
    if n_oos == 0:
        log("No OOS trades -> INSUFFICIENT DATA."); res["verdict"] = "INSUFFICIENT DATA (0 OOS trades)"; return res
    longf = float((oos_dir > 0).mean())
    lp, spn = oos_pnl[oos_dir > 0], oos_pnl[oos_dir < 0]
    mh, timed, nt = exit_stats(b, sigs, b.oos_lo, b.oos_hi)
    log(f"OOS (untouched): n={n_oos}  win%={100 * (oos_pnl > 0).mean():.1f}  %PF={oos_pf:.3f}  "
        f"sum%={100 * oos_pnl.sum():.1f}  long%={100 * longf:.0f} (long %PF={C.pct_pf(lp):.3f} n={len(lp)}, "
        f"short %PF={C.pct_pf(spn):.3f} n={len(spn)})  median stop={np.median(oos_atr):.2f} ATR, "
        f"median target_r={np.median(oos_tr):.2f}; median hold={mh:.0f} bars, MAX_HOLD backstop exits={timed}/{nt}")
    EW.abc_diagnostic(piv, sigs, b.is_lo, b.is_hi, lambda s: log(s.replace("ABC diagnostic", "ABC diagnostic IS")))
    EW.abc_diagnostic(piv, sigs, b.oos_lo, b.oos_hi, lambda s: log(s.replace("ABC diagnostic", "ABC diagnostic OOS")))
    if n_oos < 20:
        log(f"OOS n={n_oos} < 20 -> INSUFFICIENT DATA for a meaningful null comparison (no verdict either way).")
        res["verdict"] = "INSUFFICIENT DATA (OOS n<20)"; return res
    pool, p_fire, mean_n = EW.random_pool_var(b, oos_atr, oos_tr, n_oos, b.oos_lo, b.oos_hi)
    pctile = 100 * (pool < oos_pf).mean()
    p1 = float((pool >= oos_pf).mean())
    pK, medK = C.best_of_k_p(pool, oos_pf, K)
    pF, medF = C.best_of_k_p(pool, oos_pf, FAMILY_K)
    log(f"random-timing OOS null ({len(pool)} draws, p_fire={p_fire:.5f}, mean n={mean_n:.0f} vs real {n_oos}; "
        f"same _run_one exit, real spread, (stop,target_r) pairs from real OOS trades): "
        f"median={np.median(pool):.3f}  p95={np.percentile(pool, 95):.3f}")
    log(f"REAL OOS %PF={oos_pf:.3f} -> {pctile:.1f}th percentile; p(K=1)={p1:.4f} [{C.verdict(p1)}]; "
        f"p(K={K})={pK:.4f} (best-of-K median {medK:.3f}) [{C.verdict(pK)}]; "
        f"p(family K={FAMILY_K})={pF:.4f} (median {medF:.3f}) [{C.verdict(pF)}]")
    dpool, _, _ = EW.random_pool_var(b, oos_atr, oos_tr, n_oos, b.oos_lo, b.oos_hi, p_long=longf, seed0=900_000)
    p1d = float((dpool >= oos_pf).mean())
    log(f"supplementary direction-matched null (p_long={longf:.2f}): median={np.median(dpool):.3f}  p(K=1)={p1d:.4f}")
    res.update(pctile=round(float(pctile), 1), p1=p1, pK=pK, pFamily=pF, p1_dir=p1d,
               verdict=C.verdict(max(p1, pK, pF)))
    return res


if __name__ == "__main__":
    out_path = "/home/user/test-project/research/silver_btc/elliott_wave_mechanical_htf_output.txt"
    lines = []

    def log(s=""):
        print(s, flush=True); lines.append(s)

    results = []
    for sym in ("GOLD", "SILVER", "BTCUSD"):
        if not os.path.exists(f"{C.DATA_DIR}/{sym}_M15_native.csv"):
            log(f"\n{'=' * 90}\n{sym}: no {sym} data of any timeframe in this environment -> NOT RUN (no verdict).")
            results.append(dict(label=sym, verdict="NOT RUN (no data)"))
            continue
        for tf in ("H4", "D1"):
            results.append(run_tf(sym, tf, log))
    log("\nSUMMARY")
    for r in results:
        log(f"  {r}")
    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")
