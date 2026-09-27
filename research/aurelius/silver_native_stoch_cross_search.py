"""
Genuine ground-up, walk-forward-disciplined search for a Silver-NATIVE
Stochastic-cross system - the user's own suggestion ("BOS, liquidity,
stochastic cross - something has to work on Silver"). Genuinely different
MECHANISM family from everything else tried this session: every other
Silver test has been either a moving-average trend/alignment system
(Aurelius, Meridian, the bare EMA-cross search) or a swing-structure
breakout (H&S, Vanguard's trendline breakout, the native trendbreak
search) - this is the first OSCILLATOR-based construction tried on Silver
at all.

CONSTRUCTION (classic stochastic reversal-from-extreme, the textbook
version, not a novel invention): MT5's standard Stochastic(5,3,3) (ported
in research/ratchet/bars.py's mt5_stoch_signal - generic, no GOLD-specific
assumption, reused directly). Buy when %K crosses above %D while %K was
below the oversold THRESHOLD on the prior bar (a reversal-from-oversold
trigger, not just any cross); mirror for sells from overbought
(100-THRESHOLD). Hold to the next opposite-direction stochastic cross
event (same hold-to-reversal exit style used throughout this session) or
an ATR safety stop.

GRID kept deliberately small (same reasoning as the MA-cross search): only
THRESHOLD and STOP_ATR are searched (K/slowing/D fixed at MT5's own
standard 5/3/3 - not tuned, since searching those too would blow up the
honest K for no strong reason to think this instrument needs a different
oscillator period than the textbook default). THRESHOLD in
{10, 15, 20, 25, 30} x STOP_ATR in {2, 3, 4, 5} = 20 combos - a small,
honestly-counted K, giving any real edge the best realistic chance to
survive the correction.

SPLIT: identical to every other Silver search this session - SILVER_M15_
native.csv, IS = 2014-06-12 -> 2021-01-01 (search only happens here),
OOS = 2021-01-01 -> 2026-09-25 (genuinely untouched).
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import itertools
import numpy as np
import pandas as pd
import engine as E
import bars as B

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
POINT = 0.001  # SILVER
IS_CUTOFF = pd.Timestamp("2021-01-01")
THRESHOLDS = [10, 15, 20, 25, 30]
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


def build_stoch_events(main, sig, threshold):
    above = main > sig
    valid = ~np.isnan(main) & ~np.isnan(sig)
    above_prev = np.concatenate(([False], above[:-1]))
    valid_prev = np.concatenate(([False], valid[:-1]))
    main_prev = np.concatenate(([np.nan], main[:-1]))
    cross_up = above & ~above_prev & valid & valid_prev & (main_prev < threshold)
    cross_dn = (~above) & above_prev & valid & valid_prev & (main_prev > (100 - threshold))
    return sorted([(i, 1.0) for i in np.where(cross_up)[0]] +
                  [(i, -1.0) for i in np.where(cross_dn)[0]], key=lambda e: e[0])


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
    main, sig = B.mt5_stoch_signal(high, low, close, 5, 3, 3)

    grid = list(itertools.product(THRESHOLDS, STOP_ATRS))
    print(f"Grid: {len(THRESHOLDS)}x{len(STOP_ATRS)} = {len(grid)} combos "
          f"(Stochastic(5,3,3) cross-from-extreme, hold-to-reversal + ATR stop; IS n>=100 required)\n")

    results = []
    event_cache = {}
    for threshold in THRESHOLDS:
        events = build_stoch_events(main, sig, threshold)
        event_cache[threshold] = events
        for stop_atr in STOP_ATRS:
            trades = sim_hold_to_reverse(events, close, high, low, spread, atr, n, stop_atr, POINT)
            if not trades:
                continue
            entry_bars = np.array([t[0] for t in trades])
            is_trades = [t for t, ib in zip(trades, entry_bars) if is_mask[ib]]
            if len(is_trades) < 100:
                continue
            is_pf = pct_pf(is_trades)
            results.append(dict(threshold=threshold, stop_atr=stop_atr, is_n=len(is_trades), is_pf=is_pf))

    results.sort(key=lambda r: r["is_pf"], reverse=True)
    print(f"{len(results)} combos had IS n>=100. All results by IS %PF:")
    for r in results:
        print(f"  THRESHOLD={r['threshold']:>3} STOP={r['stop_atr']:.1f}xATR: "
              f"IS n={r['is_n']:>5} IS %PF={r['is_pf']:.3f}")

    if not results:
        print("\nNo combo cleared IS n>=100.")
        sys.exit(0)

    best = results[0]
    print(f"\n{'='*78}\nFROZEN WINNER (chosen on IS ALONE): THRESHOLD={best['threshold']} "
          f"STOP={best['stop_atr']}xATR\nIS: n={best['is_n']} %PF={best['is_pf']:.3f}\n{'='*78}")

    events = event_cache[best["threshold"]]
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
