"""
Shared rigor plumbing for the 2026-09-26 "Art of Trend Analysis" textbook
batch (Errante Academy): fan_principle_test.py, price_channel_test.py,
andrews_pitchfork_test.py, diamond_reversal_test.py, plus the gate/filter
tests on the four KEPT EAs (new_pattern_gate_*.py).

Nothing here is a new methodology - every piece is a direct re-use of the
conventions already established in this directory:
  - swing detection: h4_touch_reaction_test.find_swings() (PIVOT_STRENGTH=5,
    SWING_MIN_ATR=1.0, high/low extremes, MT5-style SMA ATR(14)) - ported
    line for line into causal_swing_events() below, which additionally
    records WHEN each swing-list state became knowable (see LOOKAHEAD).
  - bracket walk: hs_next_round_test.walk()/pnl_of() semantics (stop wins a
    same-bar stop/target tie, HORIZON exit at close), vectorized with numpy
    slices for speed - verified byte-identical against walk()/pnl_of() by
    self_check() below.
  - %PF (pnl / entry price), never raw points.
  - random-timing baseline: quasimodo_test.random_timing_baseline() - each
    real trade's own stop%/target% bracket, same direction, replayed at a
    uniformly random bar of the SAME dataset.
  - best-of-K: multiple_testing_correction_test.best_of_k_test() /
    msg/random_timing_test.py - pool of single random-timing %PF draws,
    2000 bootstrap resamples of K draws, max taken.

LOOKAHEAD (the Wolfe Wave / Bump-and-Run bug class, taken one step
further): find_swings() run over the WHOLE series returns the FINAL zigzag.
Two separate leaks follow from using that list naively:
  (1) a pivot at bar i needs bars i+1..i+PIVOT_STRENGTH to be confirmed, so
      it is not knowable before bar i+PIVOT_STRENGTH closes (the CONFIRM_LAG
      fix already applied in wolfe_wave_test.py / quasimodo_test.py);
  (2) the zigzag's LAST swing is provisional - add_swing() REPLACES it
      whenever a more extreme same-type pivot arrives before the next
      opposite swing. The final list therefore silently "knows" which
      provisional extreme survived: a pattern whose 5th point later got
      replaced (i.e. the move kept going and would have stopped out a real
      trade) simply disappears from the final list, and a new pattern at
      the replaced extreme appears instead - a survivorship leak that the
      CONFIRM_LAG fix alone does not remove.
causal_swing_events() removes BOTH: it replays find_swings() bar by bar and
emits a snapshot of the swing list every time it changes, stamped with the
bar at which that snapshot became knowable (pivot bar + PIVOT_STRENGTH).
Every new detector in this batch consumes those snapshots in time order, so
a setup can only ever use swings that were known - in the state they were
known in - at the moment it is evaluated.

DATA (disclosed, found while building this batch): load_h4() and
load_m15_native() both contain COARSER bars mislabeled as the nominal
timeframe before the broker's real history starts - load_h4() is one bar
per DAY from 2001-06 until 2013-05-13 (260 bars/yr, not ~1540), and
load_m15_native() is DAILY bars until 2013-05 and then HOURLY bars until
2014-06-13 01:30 (the same boundary already known for M5). The real
native-M15 history is therefore ~12.3 years (2014-06 -> 2026-09), not 25,
and real H4 is ~13.4 years. load_h4_real()/load_m15_real() below cut both
series at the first genuine bar of their nominal timeframe; all new tests
in this batch use them.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import (sma_atr, ext_px, ATR_PERIOD, BREAK_TOL_ATR,
                                    BREAK_CONFIRM_CLOSES, PIVOT_STRENGTH, SWING_MIN_ATR)

MAX_HORIZON_CAP = 400
STOP_BUFFER = 1.0
REAL_H4_START = pd.Timestamp("2013-05-13")
REAL_M15_START = pd.Timestamp("2014-06-13 01:30")
N_POOL = 600
N_BOOT = 2000
K_LIST = (1, 15, 30, 50, 100)


# ------------------------------------------------------------------ data

def load_h4_real():
    h4 = E.load_h4()
    return h4[h4["time"] >= REAL_H4_START].reset_index(drop=True)


def load_m15_real():
    m15 = E.load_m15_native()
    return m15[m15["time"] >= REAL_M15_START].reset_index(drop=True)


def arrays(df):
    o = df["open"].values.astype(float); h = df["high"].values.astype(float)
    l = df["low"].values.astype(float); c = df["close"].values.astype(float)
    atr = sma_atr(h, l, o, ATR_PERIOD)   # same call convention as every trendbreaker test
    return o, h, l, c, atr


# ------------------------------------------------------------------ causal swings

def causal_swing_events(o, h, l, c, atr, N=PIVOT_STRENGTH, body=False, tail=12):
    """find_swings() (h4_touch_reaction_test.py) replayed bar by bar.
    Returns (events, final) where events is a time-ordered list of
    (known_bar, tail_swings) - tail_swings = tuple of the last `tail`
    (idx, type, px) swings AS KNOWN at the close of known_bar = pivot bar
    + N - and final = the (zIdx, zType, zPx) that find_swings() itself
    returns (used only by self_check())."""
    n = len(c)
    zIdx, zType, zPx = [], [], []
    last_closed = n - 2
    events = []

    def ep(i, dir_):
        return ext_px(o[i], h[i], l[i], c[i], dir_, body)

    def add_swing(typ, idx, px, min_leg):
        if zType and zType[-1] == typ:
            more = (px > zPx[-1]) if typ == 1 else (px < zPx[-1])
            if more:
                zIdx[-1] = idx; zPx[-1] = px
                return True
            return False
        if zPx and abs(px - zPx[-1]) < min_leg:
            return False
        zIdx.append(idx); zType.append(typ); zPx.append(px)
        return True

    for i in range(N, last_closed - N + 1):
        hi, lo = ep(i, -1), ep(i, 1)
        isH = isL = True
        for m in range(1, N + 1):
            if ep(i - m, -1) >= hi or ep(i + m, -1) > hi:
                isH = False
            if ep(i - m, 1) <= lo or ep(i + m, 1) < lo:
                isL = False
            if not isH and not isL:
                break
        if not (isH or isL):
            continue
        min_leg = SWING_MIN_ATR * atr[i]
        changed = False
        if isH and isL:
            if zType and zType[-1] == 1:
                changed |= add_swing(-1, i, lo, min_leg); changed |= add_swing(1, i, hi, min_leg)
            else:
                changed |= add_swing(1, i, hi, min_leg); changed |= add_swing(-1, i, lo, min_leg)
        elif isH:
            changed = add_swing(1, i, hi, min_leg)
        else:
            changed = add_swing(-1, i, lo, min_leg)
        if changed:
            k = max(0, len(zIdx) - tail)
            events.append((i + N, tuple(zip(zIdx[k:], zType[k:], zPx[k:]))))
    return events, (zIdx, zType, zPx)


# ------------------------------------------------------------------ bracket walk

def walk_fast(h, l, top, start_bar, max_horizon, stop, target):
    """Vectorized hs_next_round_test.walk(): same outcome, same exit bar."""
    if max_horizon <= start_bar:
        return "HORIZON", max_horizon
    hs = h[start_bar + 1:max_horizon + 1]
    ls = l[start_bar + 1:max_horizon + 1]
    if top:
        hit_s = hs >= stop; hit_t = ls <= target
    else:
        hit_s = ls <= stop; hit_t = hs >= target
    m = len(hs)
    s = int(np.argmax(hit_s)) if hit_s.any() else m
    t = int(np.argmax(hit_t)) if hit_t.any() else m
    if s == m and t == m:
        return "HORIZON", max_horizon
    if s <= t:
        return "STOP", start_bar + 1 + s
    return "TARGET", start_bar + 1 + t


def pnl_pct_of(outcome, entry, stop, target, c, exit_bar, top):
    if outcome == "TARGET":
        pnl = abs(target - entry)
    elif outcome == "STOP":
        pnl = -abs(entry - stop)
    else:
        fp = c[min(exit_bar, len(c) - 1)]
        pnl = (entry - fp) if top else (fp - entry)
    return pnl / entry


def eval_book_pct(trades, h, l, c, times=None):
    """quasimodo_test.eval_book_pct(): single position, sorted by entry bar,
    a new entry is skipped while the previous trade is still open."""
    trades = sorted(trades, key=lambda b: b["brk_q"])
    results, last_exit = [], -1
    for b in trades:
        if b["brk_q"] < last_exit:
            continue
        outcome, exit_bar = walk_fast(h, l, b["top"], b["brk_q"], b["max_horizon"], b["stop"], b["target"])
        pp = pnl_pct_of(outcome, b["brk_price"], b["stop"], b["target"], c, exit_bar, b["top"])
        r = dict(brk_q=b["brk_q"], exit_bar=exit_bar, top=b["top"], outcome=outcome, pnl_pct=pp,
                 stop_pct=abs(b["brk_price"] - b["stop"]) / b["brk_price"],
                 target_pct=abs(b["target"] - b["brk_price"]) / b["brk_price"])
        for k in ("tag",):
            if k in b:
                r[k] = b[k]
        if times is not None:
            r["time"] = times[b["brk_q"]]
        results.append(r)
        last_exit = exit_bar
    return results


def make_trade(top, q, entry, stop, target, n):
    """Validates bracket geometry; returns None if stop/target are on the
    wrong side of entry (same rejection rule as every pattern test here)."""
    if top:
        if not (target < entry < stop):
            return None
    else:
        if not (stop < entry < target):
            return None
    return dict(top=top, brk_q=q, brk_price=entry, stop=stop, target=target,
                max_horizon=min(n - 1, q + MAX_HORIZON_CAP))


def pct_pf_list(pcts):
    arr = np.asarray(pcts, dtype=float)
    if len(arr) == 0:
        return float("nan")
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def pct_pf(results):
    return pct_pf_list([r["pnl_pct"] for r in results])


# ------------------------------------------------------------------ random timing + best-of-K

def random_timing_pool(real_results, h, l, c, rng, n_runs=N_POOL, warmup=MAX_HORIZON_CAP):
    """quasimodo_test.random_timing_baseline(), vectorized walk: each real
    trade's own stop%/target% bracket, same direction, at a uniformly random
    bar of the same dataset. One %PF per run."""
    n = len(c)
    lo, hi = warmup, n - MAX_HORIZON_CAP - 1
    tops = [r["top"] for r in real_results]
    sp = [r["stop_pct"] for r in real_results]
    tp = [r["target_pct"] for r in real_results]
    pfs = []
    for _ in range(n_runs):
        qs = rng.integers(lo, hi, size=len(real_results))
        pcts = []
        for q0, top, s_pct, t_pct in zip(qs, tops, sp, tp):
            q0 = int(q0)
            entry = c[q0]
            stop = entry * (1 + s_pct) if top else entry * (1 - s_pct)
            target = entry * (1 - t_pct) if top else entry * (1 + t_pct)
            mh = min(n - 1, q0 + MAX_HORIZON_CAP)
            oc, eb = walk_fast(h, l, top, q0, mh, stop, target)
            pcts.append(pnl_pct_of(oc, entry, stop, target, c, eb, top))
        pfs.append(pct_pf_list(pcts))
    pfs = np.array(pfs)
    return pfs[~np.isnan(pfs) & ~np.isinf(pfs)]


def best_of_k(real_pf, pool, k_list=K_LIST, seed=7, n_boot=N_BOOT):
    rng = np.random.default_rng(seed)
    rows = []
    for K in k_list:
        best = pool[rng.integers(0, len(pool), size=(n_boot, K))].max(axis=1)
        rows.append(dict(K=K, med=float(np.median(best)), p95=float(np.percentile(best, 95)),
                         p=float((best >= real_pf).mean())))
    return rows


def rigor_report(label, res, h, l, c, rng_seed=42, k_list=K_LIST, n_runs=N_POOL, min_n=20):
    """Prints the standard block and returns a summary dict for the verdict
    table. min_n: below this, the pattern is reported as too-small-to-judge
    rather than forced through a significance test."""
    n = len(res)
    out = dict(label=label, n=n, pf=float("nan"), pctile=float("nan"), p=float("nan"), rows=[])
    if n == 0:
        print(f"  {label}: n=0"); return out
    arr = np.array([r["pnl_pct"] for r in res])
    real_pf = pct_pf(res)
    out["pf"] = real_pf
    win = 100 * (arr > 0).mean()
    half = n // 2
    pf1, pf2 = pct_pf(res[:half]), pct_pf(res[half:])
    n_short = sum(1 for r in res if r["top"])
    print(f"  {label}: n={n} ({n_short} short / {n - n_short} long)  win%={win:.1f}  net%={100*arr.sum():.2f}  "
          f"%PF={real_pf:.3f}   [1st half %PF={pf1:.3f}, 2nd half %PF={pf2:.3f}]")
    if n < min_n:
        print(f"    n={n} < {min_n}: too few trades for the random-timing test to mean anything - NOT forced.")
        out["small"] = True
        return out
    pool = random_timing_pool(res, h, l, c, np.random.default_rng(rng_seed), n_runs=n_runs)
    pctile = 100 * (pool < real_pf).mean()
    p_val = (pool >= real_pf).mean()
    out.update(pctile=pctile, p=p_val, pool_med=float(np.median(pool)))
    print(f"    random-timing (same bracket, same dir, {len(pool)} draws): median={np.median(pool):.3f}  "
          f"p95={np.percentile(pool,95):.3f}  -> REAL at {pctile:.1f}th pct (p={p_val:.3f})")
    rows = best_of_k(real_pf, pool, k_list)
    out["rows"] = rows
    for r in rows:
        v = "SURVIVES" if r["p"] < 0.05 else ("borderline" if r["p"] < 0.15 else "fails")
        print(f"    K={r['K']:>4}: best-of-K median={r['med']:.3f}  p95={r['p95']:.3f}  p={r['p']:.3f}  [{v}]")
    surv = [r["K"] for r in rows if r["p"] < 0.05]
    out["k_survived"] = max(surv) if surv else 0
    return out


def verdict_table(summaries, decision_k):
    print("\n" + "=" * 110)
    print(f"VERDICT TABLE (decision threshold: survive best-of-K at K={decision_k}, p<0.05)")
    print("=" * 110)
    print(f"{'variant':<58} {'n':>5} {'%PF':>7} {'pctile':>7} {'p(K=1)':>7} {'K surv':>7}  verdict")
    for s in summaries:
        if s.get("small") or s["n"] == 0:
            print(f"{s['label']:<58} {s['n']:>5} {s['pf']:>7.3f} {'-':>7} {'-':>7} {'-':>7}  TOO FEW (n<20) - inconclusive")
            continue
        ks = s.get("k_survived", 0)
        p1 = s["rows"][0]["p"] if s["rows"] else float("nan")
        v = "KEEP" if ks >= decision_k else "REJECT"
        print(f"{s['label']:<58} {s['n']:>5} {s['pf']:>7.3f} {s['pctile']:>7.1f} {p1:>7.3f} {ks:>7}  {v}")


# ------------------------------------------------------------------ helpers shared by detectors

def break_scan(c, atr, line_fn, bull, q_from, q_to, tol=BREAK_TOL_ATR, confirm=BREAK_CONFIRM_CLOSES):
    """First bar q in [q_from, q_to) completing `confirm` consecutive closes
    beyond line_fn(q) by tol*ATR (bull: above, bear: below). -1 if none.
    Same BREAK_TOL_ATR/BREAK_CONFIRM_CLOSES convention as every pattern test."""
    run_ = 0
    for q in range(max(q_from, 0), min(q_to, len(c))):
        lv = line_fn(q)
        beyond = (c[q] - lv) if bull else (lv - c[q])
        if beyond > tol * atr[q]:
            run_ += 1
            if run_ >= confirm:
                return q
        else:
            run_ = 0
    return -1


def self_check():
    """causal_swing_events' final state == find_swings(); walk_fast ==
    walk() - run on a slice of real H4 data."""
    from h4_touch_reaction_test import find_swings
    from hs_next_round_test import walk, pnl_of
    df = load_h4_real().iloc[:6000].reset_index(drop=True)
    o, h, l, c, atr = arrays(df)
    ref = find_swings(o, h, l, c, atr, body=False)
    _, fin = causal_swing_events(o, h, l, c, atr)
    assert list(ref[0]) == list(fin[0]) and list(ref[2]) == list(fin[2]), "swing replay mismatch"
    rng = np.random.default_rng(0)
    for _ in range(3000):
        q = int(rng.integers(20, len(c) - 500)); top = bool(rng.random() < 0.5)
        e = c[q]; a = atr[q] * rng.uniform(0.5, 4)
        stop, tgt = (e + a, e - 1.5 * a) if top else (e - a, e + 1.5 * a)
        mh = min(len(c) - 1, q + 400)
        r1 = walk(h, l, top, q, mh, stop, tgt); r2 = walk_fast(h, l, top, q, mh, stop, tgt)
        assert r1 == r2, (r1, r2)
        a1 = pnl_of(r1[0], e, stop, tgt, c, r1[1], top) / e
        a2 = pnl_pct_of(r2[0], e, stop, tgt, c, r2[1], top)
        assert abs(a1 - a2) < 1e-12, (a1, a2)
    print("self_check OK: causal swing replay == find_swings(), walk_fast == walk()")


if __name__ == "__main__":
    self_check()
