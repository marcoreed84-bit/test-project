"""
A genuinely non-circular test of the low-vol-regime pattern noticed in
vanguard_m5_oos_regime_split.py (LOW-vol tercile %PF=1.284, MID=0.795,
HIGH=1.104, on the FULL untouched 2014-06-13->2022-07-04 window). Testing
that pattern on the SAME window it was found in would be circular - not a
real test, just re-describing the same data. Instead: split the untouched
window itself in half chronologically. CHARACTERIZE the low-vol threshold
on the first half only, freeze it, then test it purely on the second half,
which never informed the threshold choice. K=1 - one frozen rule, applied
once to data it never touched.

Regime measure: same trailing-ATR-percentile construction as the original
split (TRAIL_BARS=20000, causal - only past bars). Rule: trade allowed
only if trailing ATR percentile at entry <= the IS-half's own 1/3 quantile
(the boundary that defined "LOW tercile" there).

Random-timing null is REGIME-MATCHED: random entries are also restricted
to low-vol bars (same frozen threshold), not just any bar - otherwise a
difference could just mean "low-vol bars have smaller moves/different
baseline risk", not "the real signal has skill within the low-vol regime".
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
import vanguard_random_timing_test as V

CUTOFF = "2022-07-04"
START = "2014-06-13"
TRAIL_BARS = 20000


def pf(a):
    a = np.asarray(a)
    if len(a) == 0:
        return float("nan")
    gw = a[a > 0].sum(); gl = -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


if __name__ == "__main__":
    m5_full = E.load_m5_extended()
    h4 = E.load_h4()
    m5 = m5_full[(m5_full["time"] >= START) & (m5_full["time"] < CUTOFF)].reset_index(drop=True)
    n_total = len(m5)
    mid = n_total // 2
    mid_time = m5["time"].iloc[mid]
    print(f"Untouched window: {m5['time'].min()} -> {m5['time'].max()} (n={n_total})")
    print(f"Chronological midpoint: {mid_time} (bar {mid})")
    print(f"  IS (characterize): {m5['time'].iloc[0]} -> {mid_time}")
    print(f"  OOS (confirm, frozen rule, never seen): {mid_time} -> {m5['time'].iloc[-1]}")

    ctx = E.build_context(m5, h4, E.P)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=V.FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < V.MIN_SR)

    # trailing ATR percentile, causal - identical construction to the original split
    atr_pctile = pd.Series(atr).rolling(TRAIL_BARS, min_periods=2000).rank(pct=True).values

    # --- STEP 1: characterize the threshold on the IS half ONLY ---
    is_mask_bar = np.arange(n) < mid
    is_trades = V.sim_full(
        [(i, d) for i, d in events if i < mid], entry_ok, close, high, low, spread, atr, n,
        V.SAFETY_SL_ATR, stale_bars=V.STALE_BARS, stale_min_profit_atr=V.STALE_MIN_PROFIT_ATR)
    is_rp = np.array([atr_pctile[t[0]] for t in is_trades])
    is_pnl = np.array([t[2] for t in is_trades])
    valid_is = ~np.isnan(is_rp)
    threshold = np.quantile(is_rp[valid_is], 1 / 3)
    print(f"\nIS half: n={len(is_trades)} trades, frozen LOW-vol threshold = {threshold:.4f} "
          f"(trailing ATR percentile)")
    print(f"  IS LOW-vol subset itself: n={ (is_rp[valid_is] <= threshold).sum() }  "
          f"%PF={pf(is_pnl[valid_is][is_rp[valid_is] <= threshold]):.3f}  (for reference only, not the test)")

    # --- STEP 2: apply the FROZEN threshold to the OOS half only ---
    oos_events = [(i, d) for i, d in events if i >= mid]
    oos_trades_all = V.sim_full(oos_events, entry_ok, close, high, low, spread, atr, n,
                                 V.SAFETY_SL_ATR, stale_bars=V.STALE_BARS,
                                 stale_min_profit_atr=V.STALE_MIN_PROFIT_ATR)
    oos_rp = np.array([atr_pctile[t[0]] for t in oos_trades_all])
    oos_pnl = np.array([t[2] for t in oos_trades_all])
    valid_oos = ~np.isnan(oos_rp)
    lowvol_mask = valid_oos & (oos_rp <= threshold)
    oos_low_pnl = oos_pnl[lowvol_mask]
    oos_low_pf = pf(oos_low_pnl)
    print(f"\nOOS half (frozen rule applied, never used to pick the threshold):")
    print(f"  all trades: n={len(oos_trades_all)}  %PF={V.pct_pf(oos_trades_all):.3f}")
    print(f"  LOW-vol subset: n={lowvol_mask.sum()}  %PF={oos_low_pf:.3f}")

    if lowvol_mask.sum() < 20:
        print("  too few trades for a meaningful random-timing null")
        sys.exit(0)

    # --- STEP 3: regime-matched random-timing null on the OOS half ---
    # restrict the random-entry "opportunity set" to low-vol bars only (per the frozen threshold),
    # so the null answers "is the REAL signal better than random timing WITHIN the low-vol regime",
    # not "do low-vol bars just have smaller moves".
    oos_bar_idx = np.arange(mid, n)
    oos_lowvol_bars = oos_bar_idx[~np.isnan(atr_pctile[oos_bar_idx]) & (atr_pctile[oos_bar_idx] <= threshold)]
    lowvol_bar_set = set(oos_lowvol_bars.tolist())
    lowvol_events = [(i, d) for i, d in oos_events if i in lowvol_bar_set]

    rng = np.random.default_rng(1)
    p_fire = V.calibrate_p_fire(lowvol_events, close, high, low, spread, atr, n, rng, lowvol_mask.sum())
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(600):
        tr = V.sim_random_entry(lowvol_events, close, high, low, spread, atr, n, rng, p_fire,
                                 V.SAFETY_SL_ATR, V.STALE_BARS, V.STALE_MIN_PROFIT_ATR)
        pool.append(V.pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    pctile = 100 * (pool < oos_low_pf).mean()
    p_val = (pool >= oos_low_pf).mean()
    print(f"\n  regime-matched random-timing null (same low-vol bars, same count): "
          f"median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    print(f"  REAL %PF={oos_low_pf:.3f} -> {pctile:.1f}th percentile, p={p_val:.4f} (K=1, frozen threshold)")
