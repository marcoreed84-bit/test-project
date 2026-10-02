"""
NEW hypothesis (2026-10-02, requested directly): swing-pivot support/
resistance levels traded as a classic mean-reversion FADE on H4 and D1 -
these two timeframes currently have nothing worth trading (H&S is real but
too rare: 19 H4 trades / 2 D1 trades over ~2.8 real years).

Construction (pre-specified in full before running, no peeking at results
mid-build):
  - A "level" = a confirmed swing high/low from find_swings() (reused
    directly from h4_touch_reaction_test.py - the real EA's own 5-bar-
    each-side fractal convention, SWING_MIN_ATR-deduped). A pivot found by
    find_swings() at bar idx is only KNOWABLE in real time once its own
    N=PIVOT_STRENGTH confirming bars have printed, i.e. live_from =
    idx + PIVOT_STRENGTH - this project got burned by lookahead bugs of
    exactly this shape before (touch_reaction_corrected.py fix #4), so it's
    applied here from the start rather than discovered as a bug later.
  - A level stays LIVE from live_from until price CLOSES beyond it by more
    than TOUCH_TOL_ATR (same tolerance reused for both the touch/reject
    trigger and the break/invalidate trigger - no separate break-tolerance
    constant exists in the pre-registered grid, so one shared ATR
    tolerance governs both "how close counts as a touch" and "how far
    beyond counts as broken"; this is disclosed, not hidden).
  - Entry (fade/rejection): for a swing-HIGH level, SHORT when a bar's HIGH
    comes within TOUCH_TOL_ATR of the level AND that same bar's CLOSE
    rejects back below (level - TOUCH_TOL_ATR) - mirror for a swing-LOW
    level -> LONG. One trade open at a time globally (last_exit gating,
    same sequenced-book convention as every other construction test in
    this repo, e.g. hs_next_round_test.py); a level fires repeatedly,
    classic "S/R holds until it doesn't", until it breaks.
  - Exit: stop = level +/- STOP_ATR (beyond the level, away from price);
    target = entry +/- RR x risk (symmetric R:R, risk = |entry-stop|).
    Fill convention: entry = signal bar's own CLOSE +/- next bar's real
    spread (same convention as sr_multilevel_range_trade_test.py / the
    H&S scripts - decision confirmed at the close, spread paid on the fill
    tick right after); stop/target then walked forward from the next bar.

Grid (K=8, searched on IS only, frozen once, reported OOS once):
  TOUCH_TOL_ATR in {0.15, 0.30}, STOP_ATR in {0.5, 1.0}, RR in {1.5, 2.5}

Methodology: chronological 70% IS / 30% OOS split BY COUNT of the realized
trade list, same convention as head_shoulders_target_test.py's own walk-
forward section (order = trades sorted by entry bar, cutoff_rank =
int(n*0.7)). Random-timing null built on the FROZEN OOS trades only: same
exit mechanism (stop_pct/target_pct taken directly from each real trade's
OWN entry/stop/target - i.e. derived from the real swing-level price, not
some close-only stand-in, the exact bug class CLAUDE.md flags from
touch_reaction_corrected.py's control fix #5), replayed at random bars with
random direction, same real spread, matched count.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import pandas as pd
import engine as E
from h4_touch_reaction_test import sma_atr, find_swings, PIVOT_STRENGTH, ATR_PERIOD

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
H4_TRIM_START = "2013-05-09"   # before this, GOLD_H4.csv is one bar/day mislabeled as H4 - already confirmed this session
MAX_HOLD_BARS = 2000
N_RANDOM = 2000

TOUCH_TOL_GRID = (0.15, 0.30)
STOP_ATR_GRID = (0.5, 1.0)
RR_GRID = (1.5, 2.5)


def read_meta_point(path):
    """Reads meta_point straight from the CSV's own header line - never
    hardcoded (CLAUDE.md: hardcoding this caused a real 10x spread-overcharge
    bug on Silver earlier in this project)."""
    with open(path) as f:
        header = f.readline().strip().split(",")
    d = dict(zip(header[0::2], header[1::2]))
    return float(d["meta_point"])


def daily_mean_spread(h4):
    """D1 has no native spread column (derive_d1_from_h4 only pulls OHLC) -
    this aggregates H4's own real spread column by calendar day, the same
    'aggregate the natural way' convention engine.resample_m15_from_m5 uses
    for M15's spread (mean, not sum - spread isn't additive)."""
    d = h4.copy()
    d["date"] = d["time"].dt.date
    return d.groupby("date")["spread"].mean().reset_index().rename(columns={"spread": "spread"})


# ---------------------------- construction ----------------------------

def build_levels(o, h, l, c, atr, n):
    zIdx, zType, zPx = find_swings(o, h, l, c, atr, body=False)
    levels = []
    for idx, typ, px in zip(zIdx, zType, zPx):
        live_from = idx + PIVOT_STRENGTH
        if live_from < n:
            levels.append((live_from, typ, px))
    return levels, len(zIdx)


def generate_events(levels, h, l, c, atr, n, touch_tol):
    """Vectorized per-level scan: find the first bar (if any) the level
    breaks (close beyond it by > touch_tol*ATR, same side as continuation),
    then collect every touch-and-reject bar before that break."""
    events = []
    for live_from, typ, px in levels:
        c_seg = c[live_from:n]
        atr_seg = atr[live_from:n]
        if typ == 1:   # swing HIGH -> resistance -> fades SHORT
            h_seg = h[live_from:n]
            break_mask = c_seg > (px + touch_tol * atr_seg)
        else:            # swing LOW -> support -> fades LONG
            l_seg = l[live_from:n]
            break_mask = c_seg < (px - touch_tol * atr_seg)

        first_break_rel = int(np.argmax(break_mask)) if break_mask.any() else len(break_mask)
        if first_break_rel == 0:
            continue   # breaks the instant it's confirmed - never actually live

        if typ == 1:
            thresh = px - touch_tol * atr_seg[:first_break_rel]
            touch_mask = (h_seg[:first_break_rel] >= thresh) & (c_seg[:first_break_rel] <= thresh)
        else:
            thresh = px + touch_tol * atr_seg[:first_break_rel]
            touch_mask = (l_seg[:first_break_rel] <= thresh) & (c_seg[:first_break_rel] >= thresh)

        for rel in np.where(touch_mask)[0]:
            q = live_from + int(rel)
            d = -1 if typ == 1 else 1   # -1 short (resistance), +1 long (support)
            events.append((q, d, px, float(atr[q])))
    events.sort(key=lambda e: e[0])
    return events


def simulate_trades(events, o, h, l, c, spread, point, n, stop_atr, rr, max_hold=MAX_HOLD_BARS):
    trades = []
    last_exit = -1
    for q, d, lvl, atrq in events:
        if q < last_exit:
            continue
        fill_i = q + 1
        if fill_i >= n or atrq <= 0 or np.isnan(atrq):
            continue
        raw = c[q]
        sp_cost = spread[fill_i] * point
        entry = raw + sp_cost if d > 0 else raw - sp_cost
        stop = (lvl - stop_atr * atrq) if d > 0 else (lvl + stop_atr * atrq)
        if (d > 0 and stop >= entry) or (d < 0 and stop <= entry):
            continue   # degenerate (level too close / entry already past stop) - skip
        risk = abs(entry - stop)
        target = entry + rr * risk if d > 0 else entry - rr * risk

        cap = min(fill_i + max_hold, n)
        exit_bar, exit_px = None, None
        for k in range(fill_i, cap):
            hit_stop = (l[k] <= stop) if d > 0 else (h[k] >= stop)
            hit_target = (h[k] >= target) if d > 0 else (l[k] <= target)
            if hit_stop:
                exit_bar, exit_px = k, stop; break
            if hit_target:
                exit_bar, exit_px = k, target; break
        if exit_bar is None:
            exit_bar = max(cap - 1, fill_i)
            exit_px = c[min(exit_bar, n - 1)]

        pnl = (exit_px - entry) if d > 0 else (entry - exit_px)
        trades.append(dict(entry_bar=q, exit_bar=exit_bar, dir=d, entry=entry, stop=stop,
                            target=target, pnl=pnl, pnl_pct=pnl / entry))
        last_exit = exit_bar
    return trades


def pct_pf(trades):
    arr = np.array([t["pnl_pct"] for t in trades])
    if len(arr) == 0:
        return float("nan")
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def split_is_oos(trades, is_frac=0.7):
    order = sorted(range(len(trades)), key=lambda i: trades[i]["entry_bar"])
    cutoff = int(len(trades) * is_frac)
    is_t = [trades[i] for i in order[:cutoff]]
    oos_t = [trades[i] for i in order[cutoff:]]
    return is_t, oos_t


def summarize(trades, label):
    n_ = len(trades)
    if n_ == 0:
        print(f"    {label}: n=0"); return
    arr = np.array([t["pnl_pct"] for t in trades])
    wins = int((arr > 0).sum())
    print(f"    {label}: n={n_}  win%={100*wins/n_:.1f}  %PF={pct_pf(trades):.3f}  net%={100*arr.sum():.2f}")


# ---------------------------- random-timing null ----------------------------

def random_timing_null(real_trades, o, h, l, c, spread, point, n, rng, n_runs=N_RANDOM, max_hold=MAX_HOLD_BARS):
    """Matched-bracket null: each REAL trade's own risk_pct/target_pct
    (derived from its actual entry/stop/target prices - i.e. structurally
    anchored to the real swing-level price the stop was set beyond, NOT a
    close-only stand-in) replayed at a random bar with a random direction,
    same real spread, same walk-forward exit mechanism. Matched count per
    draw = len(real_trades)."""
    specs = [(abs(t["entry"] - t["stop"]) / t["entry"],
              abs(t["target"] - t["entry"]) / t["entry"]) for t in real_trades]
    lo, hi = 1, n - max_hold - 2
    if hi <= lo or not specs:
        return np.array([])
    pfs = []
    for _ in range(n_runs):
        pnl_pcts = []
        for risk_pct, target_pct in specs:
            q0 = int(rng.integers(lo, hi))
            d = 1 if rng.random() < 0.5 else -1
            fill_i = q0 + 1
            raw = c[q0]
            sp_cost = spread[fill_i] * point
            entry = raw + sp_cost if d > 0 else raw - sp_cost
            stop = entry * (1 - risk_pct) if d > 0 else entry * (1 + risk_pct)
            target = entry * (1 + target_pct) if d > 0 else entry * (1 - target_pct)
            cap = min(fill_i + max_hold, n)
            exit_px = None
            for k in range(fill_i, cap):
                hit_stop = (l[k] <= stop) if d > 0 else (h[k] >= stop)
                hit_target = (h[k] >= target) if d > 0 else (l[k] <= target)
                if hit_stop:
                    exit_px = stop; break
                if hit_target:
                    exit_px = target; break
            if exit_px is None:
                exit_px = c[min(max(cap - 1, fill_i), n - 1)]
            pnl = (exit_px - entry) if d > 0 else (entry - exit_px)
            pnl_pcts.append(pnl / entry)
        arr = np.array(pnl_pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        pfs.append(gw / gl if gl > 0 else np.nan)
    return np.array(pfs)


# ---------------------------- driver ----------------------------

def run(label, o, h, l, c, spread, atr, point, n):
    print(f"\n{'='*78}\n{label}: n={n} bars")
    levels, n_swings = build_levels(o, h, l, c, atr, n)
    print(f"  swings found: {n_swings}  usable levels (confirmable before data ends): {len(levels)}")

    grid_results = {}
    for touch_tol in TOUCH_TOL_GRID:
        events = generate_events(levels, h, l, c, atr, n, touch_tol)
        for stop_atr in STOP_ATR_GRID:
            for rr in RR_GRID:
                trades = simulate_trades(events, o, h, l, c, spread, point, n, stop_atr, rr)
                grid_results[(touch_tol, stop_atr, rr)] = trades

    print(f"\n  GRID (K={len(grid_results)}, IS-only selection):")
    best_key, best_is_pf, best_is, best_oos = None, -np.inf, None, None
    for key, trades in grid_results.items():
        is_t, oos_t = split_is_oos(trades)
        is_pf = pct_pf(is_t) if len(is_t) >= 8 else float("nan")
        print(f"    TOUCH_TOL={key[0]:.2f} STOP_ATR={key[1]:.1f} RR={key[2]:.1f}  "
              f"n_total={len(trades)}  IS n={len(is_t)} %PF={is_pf:.3f}  OOS n={len(oos_t)}")
        if np.isfinite(is_pf) and is_pf > best_is_pf:
            best_is_pf, best_key, best_is, best_oos = is_pf, key, is_t, oos_t

    if best_key is None:
        print("  no grid combo had >=8 IS trades - cannot select, nothing to report"); return

    print(f"\n  FROZEN (best IS %PF): TOUCH_TOL_ATR={best_key[0]} STOP_ATR={best_key[1]} RR={best_key[2]}  "
          f"(chosen on IS only, K={len(grid_results)})")
    summarize(best_is, "IN-SAMPLE  (search set, not the verdict)")
    summarize(best_oos, "OUT-OF-SAMPLE (untouched, the verdict)")

    if len(best_oos) < 8:
        print("  OOS n<8 - too few to conclude anything, DOES NOT SURVIVE (insufficient evidence)")
        return

    rng = np.random.default_rng(42)
    null_pfs = random_timing_null(best_oos, o, h, l, c, spread, point, n, rng)
    null_pfs = null_pfs[np.isfinite(null_pfs)]
    real_pf = pct_pf(best_oos)
    pctile = 100 * (null_pfs < real_pf).mean()
    p_val = (null_pfs >= real_pf).mean()
    print(f"\n  RANDOM-TIMING NULL on frozen OOS (matched brackets, random bar+direction, real spread, "
          f"{len(null_pfs)} draws):")
    print(f"    null %PF: median={np.median(null_pfs):.3f}  p90={np.percentile(null_pfs,90):.3f}  "
          f"p95={np.percentile(null_pfs,95):.3f}")
    verdict = "SURVIVES (p<0.05)" if p_val < 0.05 else ("borderline (p<0.15)" if p_val < 0.15 else "DOES NOT SURVIVE")
    print(f"    REAL OOS %PF={real_pf:.3f} -> {pctile:.1f}th percentile of null, one-sided p={p_val:.4f}  [{verdict}]")


if __name__ == "__main__":
    point = read_meta_point(f"{DATA_DIR}/GOLD_H4.csv")
    print(f"GOLD meta_point (read from CSV header) = {point}")

    h4_full = E.load_h4()
    h4 = h4_full[h4_full["time"] >= H4_TRIM_START].reset_index(drop=True)
    print(f"H4 trimmed to >= {H4_TRIM_START}: {h4['time'].iloc[0]} -> {h4['time'].iloc[-1]} ({len(h4)} bars, "
          f"full export was {len(h4_full)} bars before trim)")

    o4 = h4["open"].values; h4h = h4["high"].values; l4 = h4["low"].values; c4 = h4["close"].values
    sp4 = h4["spread"].values.astype(float)
    atr4 = sma_atr(h4h, l4, c4, ATR_PERIOD)
    run("H4 (real GOLD H4 export, trimmed)", o4, h4h, l4, c4, sp4, atr4, point, len(h4))

    d1 = E.derive_d1_from_h4(h4)
    dsp = daily_mean_spread(h4)
    d1 = d1.merge(dsp, on="date", how="left")
    d1["time"] = pd.to_datetime(d1["date"])
    d1 = d1.sort_values("time").reset_index(drop=True)
    print(f"\nD1 (derived from trimmed H4): {d1['time'].iloc[0]} -> {d1['time'].iloc[-1]} ({len(d1)} bars)")

    o1 = d1["open"].values; h1 = d1["high"].values; l1 = d1["low"].values; c1 = d1["close"].values
    sp1 = d1["spread"].values.astype(float)
    atr1 = sma_atr(h1, l1, c1, ATR_PERIOD)
    run("D1 (derived from real GOLD H4, trimmed)", o1, h1, l1, c1, sp1, atr1, point, len(d1))
