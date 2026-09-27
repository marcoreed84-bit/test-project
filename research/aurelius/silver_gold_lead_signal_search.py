"""
Cross-asset variant of silver_native_ma_cross_search.py, prompted directly
by the user's own observation: gold and silver M15 returns correlate at
0.75 over the full 2014-2026 history (checked just before this file was
written, stable in a 0.63-0.85 band across every rolling 1-year window -
this isn't a fluke of one era). Every Silver test this session so far has
asked "does a system built on SILVER's OWN price action work" - this asks
the genuinely different question: does GOLD's own trend state, used as the
SIGNAL, produce profitable trades when the position is actually taken in
SILVER? If gold leads (or at least co-moves cleanly) and gold's own trend
is less noisy than silver's (silver is the higher-beta, noisier metal),
gold's cross event could be a cleaner timing signal than silver's own MAs
managed to be.

CONSTRUCTION: bare fast/slow EMA cross on GOLD's own close (same minimal,
honest, 3-parameter family as silver_native_ma_cross_search.py - FAST x
SLOW x STOP_ATR, 64 combos, K=64 for the correction), but the trade itself
is opened, held, stopped and closed entirely in SILVER's own price/ATR/
spread - gold only supplies entry/exit TIMING (the cross event and its
reversal). Both instruments' real M15 history is merged on their common
timestamps (native M15: gold from 2014-06-13, silver from 2014-06-12 - see
engine.py / aurelius_m15_silver_test.py's own contamination notes) so every
signal bar has a real, simultaneous silver bar to trade.

SPLIT: identical IS/OOS boundary as every other Silver search this session
- IS = merged-start -> 2021-01-01 (search only happens here), OOS =
2021-01-01 -> end (genuinely untouched).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import itertools
import numpy as np
import pandas as pd
import engine as E

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
POINT_SILVER = 0.001
IS_CUTOFF = pd.Timestamp("2021-01-01")
FASTS = [10, 20, 30, 50]
SLOWS = [100, 150, 200, 300]
STOP_ATRS = [2.0, 3.0, 4.0, 5.0]
N_RANDOM = 600


def load_native(symbol, cutoff):
    df = pd.read_csv(f"{DATA_DIR}/{symbol}_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    df = df[df["time"] >= cutoff].sort_values("time").reset_index(drop=True)
    return df


def build_cross_events(close, fast, slow):
    mf = E.ma(close, fast, "ema")
    ms = E.ma(close, slow, "ema")
    above = mf > ms
    valid = ~np.isnan(mf) & ~np.isnan(ms)
    above_prev = np.concatenate(([False], above[:-1]))
    valid_prev = np.concatenate(([False], valid[:-1]))
    cross_up = above & ~above_prev & valid & valid_prev
    cross_dn = (~above) & above_prev & valid & valid_prev
    return sorted([(i, 1.0) for i in np.where(cross_up)[0]] +
                  [(i, -1.0) for i in np.where(cross_dn)[0]], key=lambda e: e[0])


def sim_hold_to_reverse(events, close_s, high_s, low_s, spread_s, atr_s, n, stop_atr, point):
    """Signal (events) computed off GOLD; every price used to open/manage/
    close the trade (entry, stop distance, spread cost, exit fill) is
    SILVER's own - this is what makes it a cross-asset LEAD-SIGNAL test
    rather than just re-deriving silver's own cross (that's the other
    file)."""
    trades = []
    for k in range(len(events) - 1):
        i, d = events[k]
        i_next, _ = events[k + 1]
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr_s[i]) or atr_s[i] <= 0:
            continue
        is_buy = d > 0
        raw = close_s[i]
        sc = spread_s[fill_i] * point
        entry = raw + sc if is_buy else raw - sc
        sl = entry - stop_atr * atr_s[i] if is_buy else entry + stop_atr * atr_s[i]
        exit_bar, exit_px = None, None
        cap = min(i_next + 1, n)
        for kk in range(fill_i, cap):
            if is_buy and low_s[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high_s[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close_s[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy, entry))
    return trades


def sim_random_entry(events, close_s, high_s, low_s, spread_s, atr_s, n, rng, p_fire, stop_atr, point, lo, hi):
    """Random entry TIMING (not tied to gold at all) but the SAME reversal-
    exit-cap logic (next opposite GOLD event) and same silver-priced stop/
    spread - isolates whether gold's specific cross TIMING beats random
    timing paying the identical silver costs and using the identical
    reversal-based hold horizon."""
    trades = []
    last_exit = max(lo, -1)
    event_bars = np.array([e[0] for e in events])
    event_dirs = np.array([e[1] for e in events])
    for i in range(lo, min(hi, n - 1)):
        if i < last_exit:
            continue
        if atr_s[i] <= 0 or np.isnan(atr_s[i]):
            continue
        if rng.random() >= p_fire:
            continue
        d = 1.0 if rng.random() < 0.5 else -1.0
        fill_i = i + 1
        if fill_i >= n:
            continue
        is_buy = d > 0
        raw = close_s[i]
        sc = spread_s[fill_i] * point
        entry = raw + sc if is_buy else raw - sc
        sl = entry - stop_atr * atr_s[i] if is_buy else entry + stop_atr * atr_s[i]
        later = event_bars > i
        opp = later & (event_dirs != d)
        cap = int(event_bars[opp].min()) + 1 if opp.any() else n
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy and low_s[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high_s[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close_s[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy, entry))
        last_exit = exit_bar
    return trades


def pct_pf(trades):
    if not trades:
        return float("nan")
    arr = np.array([t[2] / t[4] for t in trades])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


if __name__ == "__main__":
    g = load_native("GOLD", "2014-06-13")
    s = load_native("SILVER", "2014-06-13")
    merged_time = np.intersect1d(g["time"].values, s["time"].values)
    g = g[g["time"].isin(merged_time)].sort_values("time").reset_index(drop=True)
    s = s[s["time"].isin(merged_time)].sort_values("time").reset_index(drop=True)
    assert (g["time"].values == s["time"].values).all()
    n = len(g)
    time = g["time"].values
    is_mask = time < np.datetime64(IS_CUTOFF)
    print(f"Merged GOLD/SILVER M15 on common timestamps: n={n} bars, {g['time'].min()} -> {g['time'].max()}")
    print(f"IS: -> {IS_CUTOFF.date()} ({is_mask.sum()} bars)  OOS: {IS_CUTOFF.date()} -> "
          f"({(~is_mask).sum()} bars, genuinely untouched)\n")

    close_g = g["close"].values.astype(float)
    high_s = s["high"].values.astype(float)
    low_s = s["low"].values.astype(float)
    close_s = s["close"].values.astype(float)
    spread_s = s["spread"].values.astype(float)
    atr_s = E.wilder_atr(high_s, low_s, close_s, 14)

    grid = list(itertools.product(FASTS, SLOWS, STOP_ATRS))
    print(f"Grid: {len(FASTS)}x{len(SLOWS)}x{len(STOP_ATRS)} = {len(grid)} combos "
          f"(GOLD EMA cross signal -> SILVER trade, IS n>=100 required)\n")

    results = []
    cross_cache = {}
    for fast, slow in itertools.product(FASTS, SLOWS):
        events = build_cross_events(close_g, fast, slow)
        cross_cache[(fast, slow)] = events
        for stop_atr in STOP_ATRS:
            trades = sim_hold_to_reverse(events, close_s, high_s, low_s, spread_s, atr_s, n, stop_atr, POINT_SILVER)
            if not trades:
                continue
            entry_bars = np.array([t[0] for t in trades])
            is_trades = [t for t, ib in zip(trades, entry_bars) if is_mask[ib]]
            if len(is_trades) < 100:
                continue
            is_pf = pct_pf(is_trades)
            results.append(dict(fast=fast, slow=slow, stop_atr=stop_atr, is_n=len(is_trades), is_pf=is_pf))

    results.sort(key=lambda r: r["is_pf"], reverse=True)
    print(f"{len(results)} combos had IS n>=100. Top 10 by IS %PF:")
    for r in results[:10]:
        print(f"  FAST={r['fast']:>3} SLOW={r['slow']:>3} STOP={r['stop_atr']:.1f}xATR: "
              f"IS n={r['is_n']:>5} IS %PF={r['is_pf']:.3f}")

    if not results:
        print("\nNo combo cleared IS n>=100.")
        sys.exit(0)

    best = results[0]
    print(f"\n{'='*78}\nFROZEN WINNER (chosen on IS ALONE): GOLD-signal FAST={best['fast']} SLOW={best['slow']} "
          f"STOP={best['stop_atr']}xATR (silver-priced)\nIS: n={best['is_n']} %PF={best['is_pf']:.3f}\n{'='*78}")

    events = cross_cache[(best["fast"], best["slow"])]
    all_trades = sim_hold_to_reverse(events, close_s, high_s, low_s, spread_s, atr_s, n, best["stop_atr"], POINT_SILVER)
    entry_bars = np.array([t[0] for t in all_trades])
    oos_trades = [t for t, ib in zip(all_trades, entry_bars) if not is_mask[ib]]
    oos_pf = pct_pf(oos_trades)
    pnls = np.array([t[2] for t in oos_trades])
    print(f"\nOOS (genuinely untouched, {IS_CUTOFF.date()} onward): n={len(oos_trades)}  "
          f"win%={100*(pnls>0).mean():.1f}  %PF={oos_pf:.3f}")

    if len(oos_trades) < 20:
        print("Too few OOS trades to run a meaningful random-timing test.")
        sys.exit(0)

    oos_lo = int(np.searchsorted(time, np.datetime64(IS_CUTOFF)))
    oos_hi = n

    def calibrate(rng, target_n, trials=4):
        p_fire = 0.001
        for _ in range(trials):
            tr = sim_random_entry(events, close_s, high_s, low_s, spread_s, atr_s, n, rng, p_fire,
                                   best["stop_atr"], POINT_SILVER, oos_lo, oos_hi)
            if len(tr) == 0:
                p_fire *= 3
                continue
            p_fire *= target_n / len(tr)
            p_fire = min(max(p_fire, 1e-6), 0.5)
        return p_fire

    rng = np.random.default_rng(1)
    p_fire = calibrate(rng, len(oos_trades))
    print(f"Calibrated p_fire={p_fire:.6f} on the OOS slice only")

    rng = np.random.default_rng(42)
    pool = []
    for _ in range(N_RANDOM):
        tr = sim_random_entry(events, close_s, high_s, low_s, spread_s, atr_s, n, rng, p_fire,
                               best["stop_atr"], POINT_SILVER, oos_lo, oos_hi)
        pool.append(pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    pctile = 100 * (pool < oos_pf).mean()
    p_val = (pool >= oos_pf).mean()
    print(f"random-timing on OOS slice ({len(pool)} draws): median={np.median(pool):.3f}  "
          f"p95={np.percentile(pool,95):.3f}")
    print(f"REAL OOS %PF={oos_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.4f})")

    print(f"\nMultiple-testing correction (K={len(grid)} is the EXACT grid size searched):")
    rng2 = np.random.default_rng(7)
    for K in (1, len(grid)):
        b = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (b >= oos_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(b):.3f}  p={p_k:.4f}  [{verdict}]")
