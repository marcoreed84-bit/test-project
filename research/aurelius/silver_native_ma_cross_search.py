"""
Genuine ground-up, walk-forward-disciplined search for a Silver-NATIVE
moving-average trend-following system - the user's own intuition ("Silver
must have trends too, just like gold - there must be MAs that work on it")
is entirely reasonable and hasn't actually been tested yet: every MA-based
system tried on Silver so far (Aurelius, Meridian) was gold's own rich,
many-filter construction (5 MAs, slope, volume, S/R, VWAP exit, etc.)
either transferred as-is or given a full joint retune across dozens of
levers - and BOTH of those searches racked up a huge honest K (554-573 for
Aurelius's tailored search), which buries any real edge under the
multiple-testing correction even when one exists (Aurelius/Silver M5
actually showed a genuine timing edge at K=1, p=0.021 - it just couldn't
survive being one of ~570 things tried).

This file asks the plainest possible version of the trend question instead:
a bare fast/slow EMA cross, hold until the trend reverses, ATR safety stop -
NOTHING else (no VWAP, no S/R, no volume, no slope filter). Only 3 numbers
are searched (fast period, slow period, stop multiple), so the honest K is
small (<=64) and, if silver genuinely trends the way gold does, this is the
simplest construction that could show it. If EVEN THIS fails to survive,
that's real evidence the earlier systems' failures were not just "too many
filters/parameters diluting a real signal" - the raw trend-following
edge itself isn't there, at least not at the daily-EMA scale this session's
existing infrastructure can probe.

DATA/SPLIT: identical to silver_native_trendbreak_search.py - SILVER_M15_
native.csv (real M15 from 2014-06-12), IS = 2014-06-12 -> 2021-01-01
(~6.6 yrs, all searching happens here), OOS = 2021-01-01 -> 2026-09-25
(~5.75 yrs, genuinely untouched by parameter selection). ATR/spread reused
from engine.build_context (params passed only for its MA/ATR machinery -
none of Aurelius's own filter fields are read by this file).

GRID: FAST in {10, 20, 30, 50} x SLOW in {100, 150, 200, 300} (FAST<SLOW
always true here) x STOP_ATR in {2.0, 3.0, 4.0, 5.0} = 64 combos total,
honestly reported as K=64 (the exact grid size) for the OOS correction.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import itertools
import numpy as np
import pandas as pd
import engine as E

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
POINT = 0.001  # SILVER
IS_CUTOFF = pd.Timestamp("2021-01-01")
FASTS = [10, 20, 30, 50]
SLOWS = [100, 150, 200, 300]
STOP_ATRS = [2.0, 3.0, 4.0, 5.0]
N_RANDOM = 600


def load_m15():
    df = pd.read_csv(f"{DATA_DIR}/SILVER_M15_native.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True)


def resample_h4_from_m15(df15):
    d = df15.set_index("time")
    o = d["open"].resample("4h").first()
    h = d["high"].resample("4h").max()
    l = d["low"].resample("4h").min()
    c = d["close"].resample("4h").last()
    v = d["tick_volume"].resample("4h").sum()
    sp = d["spread"].resample("4h").mean()
    out = pd.DataFrame(dict(open=o, high=h, low=l, close=c, tick_volume=v, spread=sp)).dropna()
    return out.reset_index()


def build_cross_events(close, fast, slow):
    mf = E.ma(close, fast, "ema")
    ms = E.ma(close, slow, "ema")
    above = mf > ms
    valid = ~np.isnan(mf) & ~np.isnan(ms)
    above_prev = np.concatenate(([False], above[:-1]))
    valid_prev = np.concatenate(([False], valid[:-1]))
    cross_up = above & ~above_prev & valid & valid_prev
    cross_dn = (~above) & above_prev & valid & valid_prev
    events = sorted([(i, 1.0) for i in np.where(cross_up)[0]] +
                     [(i, -1.0) for i in np.where(cross_dn)[0]], key=lambda e: e[0])
    return events


def sim_hold_to_reverse(events, close, high, low, spread, atr, n, stop_atr, point):
    trades = []
    for k in range(len(events) - 1):
        i, d = events[k]
        i_next, _ = events[k + 1]
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        is_buy = d > 0
        raw = close[i]
        sc = spread[fill_i] * point
        entry = raw + sc if is_buy else raw - sc
        sl = entry - stop_atr * atr[i] if is_buy else entry + stop_atr * atr[i]
        exit_bar, exit_px = None, None
        cap = min(i_next + 1, n)
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy, entry))
    return trades


def sim_random_entry(events, close, high, low, spread, atr, n, rng, p_fire, stop_atr, point, lo, hi):
    trades = []
    last_exit = max(lo, -1)
    event_bars = np.array([e[0] for e in events])
    event_dirs = np.array([e[1] for e in events])
    for i in range(lo, min(hi, n - 1)):
        if i < last_exit:
            continue
        if atr[i] <= 0 or np.isnan(atr[i]):
            continue
        if rng.random() >= p_fire:
            continue
        d = 1.0 if rng.random() < 0.5 else -1.0
        fill_i = i + 1
        if fill_i >= n:
            continue
        is_buy = d > 0
        raw = close[i]
        sc = spread[fill_i] * point
        entry = raw + sc if is_buy else raw - sc
        sl = entry - stop_atr * atr[i] if is_buy else entry + stop_atr * atr[i]
        later = event_bars > i
        opp = later & (event_dirs != d)
        cap = int(event_bars[opp].min()) + 1 if opp.any() else n
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
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
    df15 = load_m15()
    h4 = resample_h4_from_m15(df15)
    time = df15["time"].values
    is_mask = time < np.datetime64(IS_CUTOFF)
    print(f"SILVER M15: n={len(df15)} bars, {df15['time'].min()} -> {df15['time'].max()}")
    print(f"IS: {df15['time'].min()} -> {IS_CUTOFF.date()} ({is_mask.sum()} bars)  "
          f"OOS: {IS_CUTOFF.date()} -> {df15['time'].max()} ({(~is_mask).sum()} bars, genuinely untouched)\n")

    ctx = E.build_context(df15, h4, E.P15)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    n = ctx["n"]

    grid = list(itertools.product(FASTS, SLOWS, STOP_ATRS))
    print(f"Grid: {len(FASTS)}x{len(SLOWS)}x{len(STOP_ATRS)} = {len(grid)} combos "
          f"(bare EMA cross, hold-to-reversal + ATR stop, no other filter; IS n>=100 required)\n")

    results = []
    cross_cache = {}
    for fast, slow in itertools.product(FASTS, SLOWS):
        events = build_cross_events(close, fast, slow)
        cross_cache[(fast, slow)] = events
        for stop_atr in STOP_ATRS:
            trades = sim_hold_to_reverse(events, close, high, low, spread, atr, n, stop_atr, POINT)
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
    print(f"\n{'='*78}\nFROZEN WINNER (chosen on IS ALONE): FAST={best['fast']} SLOW={best['slow']} "
          f"STOP={best['stop_atr']}xATR\nIS: n={best['is_n']} %PF={best['is_pf']:.3f}\n{'='*78}")

    events = cross_cache[(best["fast"], best["slow"])]
    all_trades = sim_hold_to_reverse(events, close, high, low, spread, atr, n, best["stop_atr"], POINT)
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
            tr = sim_random_entry(events, close, high, low, spread, atr, n, rng, p_fire,
                                   best["stop_atr"], POINT, oos_lo, oos_hi)
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
        tr = sim_random_entry(events, close, high, low, spread, atr, n, rng, p_fire,
                               best["stop_atr"], POINT, oos_lo, oos_hi)
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
