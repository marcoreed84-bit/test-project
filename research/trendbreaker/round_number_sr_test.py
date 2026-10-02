"""
NEW HYPOTHESIS (not yet tried this session): round-number psychological price
levels as support/resistance on H4 and D1 - distinct from swing-pivot S/R
(h4/d1_touch_reaction_test.py, BuildLine-fitted diagonals) and prior-period
high/low S/R (SRDistanceATR in engine.py), both tested separately. Real
evidence: Osler (2003, J. Finance 58(5)) and Osler (2005, J. Int'l Money &
Finance 24(2)) found stop-loss/take-profit orders cluster at round numbers in
real bank FX order books, causing real measurable price reactions there. That
was already surfaced once tonight as a stop-PLACEMENT idea (avoid stops near
round numbers); this is different - round numbers as an ENTRY TRIGGER (does
price actually react AT them), not yet tested.

CAVEAT (disclosed honestly regardless of result): Osler's evidence is FX, not
gold. Gold's price in this project's real data window moves from ~$1900 to
~$4500+, so "round numbers" mean very different things in scale early vs late
in the sample (a $50 increment is ~2.6% of price at $1900 but ~1.1% at $4500).
Results are reported split by sub-period as well as pooled so a scale-drift
artifact would be visible rather than hidden inside one pooled number.

CONSTRUCTION (pre-specified, no peeking - this IS the one test):
Round levels at $INCREMENT multiples (grid: $25, $50). A level is always
"live" (round numbers don't expire/confirm like swing pivots - every
increment near current price is a candidate every bar).

Entry (same-bar fade/rejection):
  SHORT: this bar's HIGH comes within TOUCH_TOL_ATR*ATR of the nearest round
         level above (from below), AND this bar's CLOSE ends back below
         (level - TOUCH_TOL_ATR*ATR).
  LONG:  this bar's LOW comes within TOUCH_TOL_ATR*ATR of the nearest round
         level below (from above), AND this bar's CLOSE ends back above
         (level + TOUCH_TOL_ATR*ATR).
  One trade at a time (skip overlapping signals while a trade is open).
  A bar triggering both conditions at once (ambiguous) is skipped entirely.

Exit: stop = level +/- STOP_ATR*ATR (beyond the level), target = RR x risk
(symmetric R:R, same framing as the other exit constructions tested
tonight). Entry fills at the NEXT bar's open + real spread (GOLD_H4.csv's
own spread column, in points, converted via meta_point read from that
CSV's own header - never hardcoded). Within the holding bar, STOP is
checked before TARGET if both would trigger on the same bar (conservative).
Time-stop at HORIZON_BARS if neither stop nor target is hit.

GRID (K=16, honestly larger than the other two S/R tests since INCREMENT is
a real free parameter here): INCREMENT in {25,50} x TOUCH_TOL_ATR in
{0.15,0.3} x STOP_ATR in {0.5,1.0} x RR in {1.5,2.5}.

METHODOLOGY: chronological 70% IS / 30% OOS split by signal order (same
convention as head_shoulders_target_test.py's walk-forward section - order
all of a combo's trades by signal bar, first 70% by COUNT = IS, last 30% =
OOS). Search the K=16 grid on IS PF only, freeze the best combo, report OOS
once, untouched. Random-timing null on the frozen OOS trades: matched count,
random entry bar + random direction, SAME stop_pct/target_pct distances as
each real OOS trade (reused verbatim, not recomputed from a different
reference - this sidesteps the exact bug flagged tonight where a null's
stop-distance reference didn't match the real signal's own wick reference),
real spread, draws restricted to the OOS bar-index window only (keeps the
null's price-level/regime comparable to the real OOS trades, not diluted by
the very different price scale earlier in history).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E

DATA_DIR = E.DATA_DIR
H4_TRIM_START = "2013-05-09"
ATR_PERIOD = 14

INCREMENTS = (25.0, 50.0)
TOUCH_TOLS = (0.15, 0.3)
STOP_ATRS = (0.5, 1.0)
RRS = (1.5, 2.5)

HORIZON_BARS = dict(H4=180, D1=60)   # ~30 days H4, ~60 days D1 - generous time-stop
N_RANDOM = 1000
MIN_IS_TRADES = 10


def read_meta_point(path):
    with open(path) as f:
        header = f.readline().strip().split(",")
    idx = header.index("meta_point")
    return float(header[idx + 1])


def derive_d1_spread(h4):
    """engine.py's derive_d1_from_h4() only carries OHLC - this mirrors its
    own groupby convention (grouping real H4 bars by calendar date) to add a
    real per-day spread, the same aggregation (mean) resample_m15_from_m5()
    already uses in engine.py for the M5->M15 case, applied here to H4->D1."""
    d = h4.copy()
    d["date"] = d["time"].dt.date
    sp = d.groupby("date")["spread"].mean().reset_index().rename(columns={"spread": "spread"})
    return sp


def pct_pf(trades):
    if not trades:
        return float("nan")
    arr = np.array([t["pnl"] / t["entry"] for t in trades])
    gw = arr[arr > 0].sum()
    gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def round_level_signals(h, l, c, atr, increment):
    """Returns list of (bar_i, direction[+1 long/-1 short], level) for every
    TOUCH_TOL_ATR combo lazily - actually parameterized by tol since tol only
    changes the band width, not the nearest-level lookup."""
    n = len(c)

    def gen(touch_tol):
        sigs = []
        for i in range(n):
            a = atr[i]
            if np.isnan(a) or a <= 0:
                continue
            tol = touch_tol * a
            lvl_hi = round(h[i] / increment) * increment
            lvl_lo = round(l[i] / increment) * increment
            short_ok = (lvl_hi - tol <= h[i] <= lvl_hi + tol) and (c[i] <= lvl_hi - tol)
            long_ok = (lvl_lo - tol <= l[i] <= lvl_lo + tol) and (c[i] >= lvl_lo + tol)
            if short_ok and long_ok:
                continue  # ambiguous same-bar signal - skip per pre-spec
            if short_ok:
                sigs.append((i, -1, lvl_hi))
            elif long_ok:
                sigs.append((i, 1, lvl_lo))
        return sigs
    return gen


def simulate(signals, o, h, l, c, spread, point, atr, stop_atr, rr, horizon_cap):
    n = len(c)
    trades = []
    last_exit_bar = -1
    for (i, d, lvl) in signals:
        if i <= last_exit_bar:
            continue
        fill_i = i + 1
        if fill_i >= n:
            continue
        a = atr[i]
        if np.isnan(a) or a <= 0:
            continue
        is_long = d == 1
        sc = spread[fill_i] * point
        raw = o[fill_i]
        entry = raw + sc if is_long else raw - sc
        stop = (lvl - stop_atr * a) if is_long else (lvl + stop_atr * a)
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        target = entry + rr * risk if is_long else entry - rr * risk
        horizon_end = min(n - 1, fill_i + horizon_cap)
        exit_px, exit_bar = None, None
        for k in range(fill_i, horizon_end + 1):
            hit_stop = (l[k] <= stop) if is_long else (h[k] >= stop)
            hit_target = (h[k] >= target) if is_long else (l[k] <= target)
            if hit_stop:
                exit_px, exit_bar = stop, k
                break
            if hit_target:
                exit_px, exit_bar = target, k
                break
        if exit_px is None:
            exit_bar = horizon_end
            exit_px = c[exit_bar]
        pnl = (exit_px - entry) if is_long else (entry - exit_px)
        trades.append(dict(signal_bar=i, entry_bar=fill_i, exit_bar=exit_bar,
                            entry=entry, pnl=pnl, is_long=is_long,
                            stop_pct=risk / entry, target_pct=(rr * risk) / entry))
        last_exit_bar = exit_bar
    return trades


def replay_at(o, h, l, c, spread, point, n, q0, is_long, stop_pct, target_pct, horizon_cap):
    fill_i = q0 + 1
    if fill_i >= n:
        return None
    sc = spread[fill_i] * point
    raw = o[fill_i]
    entry = raw + sc if is_long else raw - sc
    stop = entry * (1 - stop_pct) if is_long else entry * (1 + stop_pct)
    target = entry * (1 + target_pct) if is_long else entry * (1 - target_pct)
    horizon_end = min(n - 1, fill_i + horizon_cap)
    exit_px = None
    for k in range(fill_i, horizon_end + 1):
        hit_stop = (l[k] <= stop) if is_long else (h[k] >= stop)
        hit_target = (h[k] >= target) if is_long else (l[k] <= target)
        if hit_stop:
            exit_px = stop
            break
        if hit_target:
            exit_px = target
            break
    if exit_px is None:
        exit_px = c[horizon_end]
    pnl = (exit_px - entry) if is_long else (entry - exit_px)
    return pnl / entry


def random_null(oos_trades, o, h, l, c, spread, point, n, lo, hi, horizon_cap, rng, n_runs=N_RANDOM):
    pfs = []
    for _ in range(n_runs):
        pcts = []
        for t in oos_trades:
            q0 = int(rng.integers(lo, hi))
            is_long = rng.random() < 0.5
            r = replay_at(o, h, l, c, spread, point, n, q0, is_long,
                          t["stop_pct"], t["target_pct"], horizon_cap)
            if r is not None:
                pcts.append(r)
        if not pcts:
            pfs.append(np.nan)
            continue
        arr = np.array(pcts)
        gw = arr[arr > 0].sum()
        gl = -arr[arr <= 0].sum()
        pfs.append(gw / gl if gl > 0 else np.nan)
    return np.array(pfs)


def run(label, df, point, horizon_cap, seed):
    o = df["open"].values; h = df["high"].values; l = df["low"].values; c = df["close"].values
    spread = df["spread"].values.astype(float)
    atr = E.wilder_atr(h, l, c, ATR_PERIOD)
    n = len(c)
    years = (df["time"].max() - df["time"].min()).days / 365.25
    print("\n" + "=" * 100)
    print(f"{label}: n={n} bars, {df['time'].min().date()} -> {df['time'].max().date()} ({years:.2f} yrs), "
          f"price range ${c.min():.0f}-${c.max():.0f}")
    print("=" * 100)

    # signal gens are keyed by (increment, touch_tol) - reuse the same
    # nearest-level lookup across the inner stop_atr/RR grid
    sig_gens = {}
    for inc in INCREMENTS:
        gen = round_level_signals(h, l, c, atr, inc)
        for tol in TOUCH_TOLS:
            sig_gens[(inc, tol)] = gen(tol)
            print(f"  increment=${inc:.0f} tol={tol}xATR: {len(sig_gens[(inc, tol)])} raw touch+reject signals "
                  f"({len(sig_gens[(inc, tol)]) / years:.1f}/yr, before 1-at-a-time filtering)")

    grid_results = []
    for inc in INCREMENTS:
        for tol in TOUCH_TOLS:
            sigs = sig_gens[(inc, tol)]
            for sa in STOP_ATRS:
                for rr in RRS:
                    trades = simulate(sigs, o, h, l, c, spread, point, atr, sa, rr, horizon_cap)
                    cut = int(len(trades) * 0.7)
                    is_tr, oos_tr = trades[:cut], trades[cut:]
                    pf_is = pct_pf(is_tr)
                    grid_results.append(dict(inc=inc, tol=tol, sa=sa, rr=rr,
                                              trades=trades, is_tr=is_tr, oos_tr=oos_tr, pf_is=pf_is))

    print(f"\n  K={len(grid_results)} combos searched on IS only:")
    for g in sorted(grid_results, key=lambda g: (g["pf_is"] if not np.isnan(g["pf_is"]) else -1), reverse=True):
        print(f"    INC=${g['inc']:.0f} tol={g['tol']} stop={g['sa']}xATR RR={g['rr']}: "
              f"n_total={len(g['trades'])} n_IS={len(g['is_tr'])} PF_IS={g['pf_is']:.3f}")

    eligible = [g for g in grid_results if len(g["is_tr"]) >= MIN_IS_TRADES and not np.isnan(g["pf_is"])]
    if not eligible:
        print(f"\n  No grid combo reached {MIN_IS_TRADES}+ IS trades - construction too rare on {label}, nothing to freeze.")
        return
    best = max(eligible, key=lambda g: g["pf_is"])
    print(f"\n  FROZEN (best IS PF among {len(eligible)} eligible combos): "
          f"INC=${best['inc']:.0f} tol={best['tol']}xATR stop={best['sa']}xATR RR={best['rr']}  "
          f"PF_IS={best['pf_is']:.3f} (n_IS={len(best['is_tr'])})")

    oos = best["oos_tr"]
    if len(oos) < 8:
        print(f"  OOS n={len(oos)} - too few to conclude anything. STOP HERE (hypothesis, not a verdict).")
        return

    oos_arr = np.array([t["pnl"] / t["entry"] for t in oos])
    wins = (oos_arr > 0).sum()
    pf_oos = pct_pf(oos)
    net_oos = 100 * oos_arr.sum()
    print(f"\n  OOS (untouched, reported once): n={len(oos)}  win%={100*wins/len(oos):.1f}  "
          f"PF={pf_oos:.3f}  net%={net_oos:.2f}")

    oos_bars = [t["signal_bar"] for t in oos]
    lo, hi = min(oos_bars), max(n - horizon_cap - 1, min(oos_bars) + 1)
    if hi <= lo:
        lo, hi = 0, n - horizon_cap - 1
    rng = np.random.default_rng(seed)
    null_pfs = random_null(oos, o, h, l, c, spread, point, n, lo, hi, horizon_cap, rng)
    null_pfs = null_pfs[~np.isnan(null_pfs)]
    p_value = (null_pfs >= pf_oos).mean()
    pct_rank = 100 * (null_pfs < pf_oos).mean()
    print(f"  Random-timing null (matched n={len(oos)}, random dir, same stop/target %, real spread, "
          f"{len(null_pfs)} runs, draws confined to the OOS bar window [{lo},{hi}]):")
    print(f"    null median PF={np.median(null_pfs):.3f}  p10={np.percentile(null_pfs,10):.3f}  "
          f"p90={np.percentile(null_pfs,90):.3f}")
    print(f"    REAL OOS PF={pf_oos:.3f} sits at the {pct_rank:.1f}th percentile of the null "
          f"(one-sided p={p_value:.3f})")
    if p_value <= 0.05:
        print("    -> OOS result is ABOVE the random-timing band - survives this one check.")
    else:
        print("    -> OOS result is INSIDE/BELOW the random-timing band - FAILS. No evidence the round-number "
              "entry timing beats random at matched risk. Reporting this plainly, per project standard.")

    # scale-drift sanity: split OOS by sub-period (price level) and show PF in each half
    mid_bar = oos_bars[len(oos_bars) // 2]
    half1 = [t for t in oos if t["signal_bar"] <= mid_bar]
    half2 = [t for t in oos if t["signal_bar"] > mid_bar]
    if len(half1) >= 5 and len(half2) >= 5:
        p1 = c[[t["signal_bar"] for t in half1]].mean()
        p2 = c[[t["signal_bar"] for t in half2]].mean()
        print(f"\n  Scale-drift check (OOS only, split in half chronologically):")
        print(f"    earlier OOS half: n={len(half1)} avg price=${p1:.0f} PF={pct_pf(half1):.3f}")
        print(f"    later   OOS half: n={len(half2)} avg price=${p2:.0f} PF={pct_pf(half2):.3f}")
    else:
        print(f"\n  Scale-drift check: not enough OOS trades per half (n1={len(half1)}, n2={len(half2)}) to split further.")

    # tol-vs-increment sanity: is TOUCH_TOL_ATR actually tight relative to the
    # increment, or is the tolerance band so wide every bar is "near" a level?
    tol_px = best["tol"] * atr[~np.isnan(atr)]
    half_inc = best["inc"] / 2.0
    frac_wide = (tol_px >= half_inc).mean()
    print(f"\n  Tolerance-vs-increment sanity: TOUCH_TOL_ATR*ATR >= increment/2 on {100*frac_wide:.1f}% of bars "
          f"(increment=${best['inc']:.0f}, half={half_inc:.1f}). "
          + ("WARNING: tolerance frequently exceeds half the increment - 'near a round number' is close to "
             "always true on this timeframe/increment, weakening what a 'touch' means."
             if frac_wide > 0.05 else "Tolerance stays tight relative to the increment - 'touch' is a meaningful filter."))


if __name__ == "__main__":
    point = read_meta_point(f"{DATA_DIR}/GOLD_H4.csv")
    print(f"meta_point read from GOLD_H4.csv header: {point}")

    h4_full = E.load_h4()
    h4 = h4_full[h4_full["time"] >= H4_TRIM_START].reset_index(drop=True)
    print(f"H4 trimmed to time >= {H4_TRIM_START}: {len(h4_full)} -> {len(h4)} bars")

    run("H4 (real GOLD H4 export, trimmed)", h4, point, HORIZON_BARS["H4"], seed=101)

    d1 = E.derive_d1_from_h4(h4)
    d1["time"] = pd.to_datetime(d1["date"])
    d1_spread = derive_d1_spread(h4)
    d1 = d1.merge(d1_spread, on="date", how="left")
    d1 = d1.sort_values("time").reset_index(drop=True)
    print(f"\nD1 derived from trimmed H4: {len(d1)} daily bars, spread = mean of that day's real H4 spread column")

    run("D1 (derived from real GOLD H4, trimmed)", d1, point, HORIZON_BARS["D1"], seed=202)
