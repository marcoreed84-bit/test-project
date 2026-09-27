"""
Genuine ground-up, walk-forward-disciplined search for a Silver-NATIVE
trendline-breakout system - not a transfer of Vanguard's gold-tuned
FractalK=100/SafetyStopATR=4.0/StaleBars=225/MinSR=0.50 (already tested
frozen in vanguard_silver_btc_test.py and confirmed a net loser that
doesn't even beat random timing). Same construction family (diagonal
trendline breakout via trendline_break_test.build_trendline_values/
build_breakout_events, gated by VWAP direction + S/R distance, ATR safety
stop, optional stale-bar exit), but every parameter is searched FRESH on
Silver's own in-sample data and never touched by anything OOS.

WHY THIS FAMILY AND NOT SOMETHING ELSE: every pattern/system this session
has tried on Silver/Bitcoin has been a GOLD-tuned system transferred as-is
(H&S - the only one that survived; Aurelius/Vanguard/Ratchet/Meridian - all
failed) or a pattern that never even survived gold's own multiple-testing
bar in the first place (RoundingBottom, Rectangle - re-checked just before
this file was written, both fail their own real K correction on GOLD, so
porting them anywhere is pointless). The one thing never yet tried: taking
a proven-generalizing MECHANISM (swing-structure breakout + ATR-relative
risk) and tuning its actual numbers to Silver's own volatility regime
instead of gold's, with proper IS/OOS discipline - exactly the same
standard Aurelius's tailored search was held to (and failed 4/4 times), so
expectations going in are modest, not optimistic.

DATA / SPLIT: SILVER_M15_native.csv, real M15 from 2014-06-12 (see
aurelius_m15_silver_test.py's own contamination note - already trimmed).
IS_CUTOFF = 2021-01-01: IS = 2014-06-12 -> 2021-01-01 (~6.6 yrs, used for
the ENTIRE grid search below), OOS = 2021-01-01 -> 2026-09-25 (~5.75 yrs,
genuinely never touched by parameter selection). H4 resampled from this
same M15 (lossless OHLC aggregation) purely to derive D1 H/L for the S/R
filter via engine.derive_d1_from_h4() - same approach as every other
Silver H4 need this session.

GRID (asked/answered honestly, not narrowed after peeking at results):
  FRACTAL_K in {20, 40, 60, 100, 150} x MIN_SR in {0.0, 0.25, 0.50, 0.75, 1.00}
  x SAFETY_SL_ATR in {2.0, 3.0, 4.0, 5.0} x STALE_BARS in {None, 100, 225, 400}
  = 500 combos total. Selection rule: highest IS %PF among combos with
  IS n>=100 (guards against a handful of lucky trades driving the pick).
  K=500 for the OOS multiple-testing correction is exact (it's the literal
  grid size), not an after-the-fact estimate like the older gold-era files'
  K=14/15/24/27 - the strongest-possible version of this session's own
  correction discipline.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import itertools
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
POINT = 0.001  # SILVER
IS_CUTOFF = pd.Timestamp("2021-01-01")
FRACTAL_KS = [20, 40, 60, 100, 150]
MIN_SRS = [0.0, 0.25, 0.50, 0.75, 1.00]
SAFETY_SLS = [2.0, 3.0, 4.0, 5.0]
STALE_BARS_OPTS = [None, 100, 225, 400]
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


def sim_full_p(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr, point,
               stale_bars=None, stale_min_profit_atr=0.0):
    trades = []
    last_exit = -1
    for idx, (i, d) in enumerate(events):
        if entry_ok is not None and not entry_ok[i]:
            continue
        if i < last_exit:
            continue
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        is_buy = d > 0
        raw = close[i]
        sc = spread[fill_i] * point
        entry = raw + sc if is_buy else raw - sc
        sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
        cap = n
        for j in range(idx + 1, len(events)):
            if events[j][1] != d:
                cap = min(events[j][0] + 1, n)
                break
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
            if stale_bars and (kk - fill_i) >= stale_bars:
                cur_profit = ((close[kk] - entry) if is_buy else (entry - close[kk])) / atr[i]
                if cur_profit < stale_min_profit_atr:
                    exit_bar, exit_px = kk, close[kk]; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy, entry))
        last_exit = exit_bar
    return trades


def sim_random_entry_p(real_events, close, high, low, spread, atr, n, rng, p_fire,
                        safety_sl_atr, point, stale_bars, stale_min_profit_atr, lo, hi):
    """Same exit machinery, entries restricted to [lo, hi) - used to build a
    random-timing null on ONLY the OOS slice, matching real_events' own
    'next opposite real event' exit cap so the exit rule stays identical."""
    trades = []
    last_exit = max(lo, -1)
    real_event_bars = np.array([e[0] for e in real_events])
    real_event_dirs = np.array([e[1] for e in real_events])
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
        sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
        later = real_event_bars > i
        opp = later & (real_event_dirs != d)
        cap = int(real_event_bars[opp].min()) + 1 if opp.any() else n
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
            if stale_bars and (kk - fill_i) >= stale_bars:
                cur_profit = ((close[kk] - entry) if is_buy else (entry - close[kk])) / atr[i]
                if cur_profit < stale_min_profit_atr:
                    exit_bar, exit_px = kk, close[kk]; break
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
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]
    cond_vwap = close > vwap

    grid = list(itertools.product(FRACTAL_KS, MIN_SRS, SAFETY_SLS, STALE_BARS_OPTS))
    print(f"Grid: {len(FRACTAL_KS)}x{len(MIN_SRS)}x{len(SAFETY_SLS)}x{len(STALE_BARS_OPTS)} = {len(grid)} combos "
          f"(selecting by IS %PF, IS n>=100 required)\n")

    results = []
    for fk in FRACTAL_KS:
        print(f"  building trendlines for FRACTAL_K={fk}...")
        desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=fk)
        events = build_breakout_events(close, desc_line, asc_line, n)
        for min_sr in MIN_SRS:
            entry_ok = np.zeros(n, dtype=bool)
            for i, d in events:
                cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
                if not cv:
                    continue
                sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
                entry_ok[i] = not (sr >= 0.0 and sr < min_sr)
            for sl_atr in SAFETY_SLS:
                for stale in STALE_BARS_OPTS:
                    trades = sim_full_p(events, entry_ok, close, high, low, spread, atr, n,
                                         sl_atr, POINT, stale_bars=stale, stale_min_profit_atr=0.0)
                    if not trades:
                        continue
                    entry_bars = np.array([t[0] for t in trades])
                    is_trades = [t for t, ib in zip(trades, entry_bars) if is_mask[ib]]
                    if len(is_trades) < 100:
                        continue
                    is_pf = pct_pf(is_trades)
                    results.append(dict(fk=fk, min_sr=min_sr, sl_atr=sl_atr, stale=stale,
                                         is_n=len(is_trades), is_pf=is_pf, events=events))

    results.sort(key=lambda r: r["is_pf"], reverse=True)
    print(f"\n{len(results)} combos had IS n>=100. Top 10 by IS %PF:")
    for r in results[:10]:
        print(f"  FRACTAL_K={r['fk']:>4} MIN_SR={r['min_sr']:.2f} SL={r['sl_atr']:.1f}xATR "
              f"stale={r['stale']}: IS n={r['is_n']:>5} IS %PF={r['is_pf']:.3f}")

    if not results:
        print("\nNo combo cleared the IS n>=100 bar - search failed to even produce a candidate.")
        sys.exit(0)

    best = results[0]
    print(f"\n{'='*78}\nFROZEN WINNER (chosen on IS ALONE): FRACTAL_K={best['fk']} MIN_SR={best['min_sr']} "
          f"SL={best['sl_atr']}xATR stale={best['stale']}\nIS: n={best['is_n']} %PF={best['is_pf']:.3f}\n{'='*78}")

    events = best["events"]
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < best["min_sr"])
    all_trades = sim_full_p(events, entry_ok, close, high, low, spread, atr, n,
                             best["sl_atr"], POINT, stale_bars=best["stale"], stale_min_profit_atr=0.0)
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
            tr = sim_random_entry_p(events, close, high, low, spread, atr, n, rng, p_fire,
                                     best["sl_atr"], POINT, best["stale"], 0.0, oos_lo, oos_hi)
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
        tr = sim_random_entry_p(events, close, high, low, spread, atr, n, rng, p_fire,
                                 best["sl_atr"], POINT, best["stale"], 0.0, oos_lo, oos_hi)
        pool.append(pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    pctile = 100 * (pool < oos_pf).mean()
    p_val = (pool >= oos_pf).mean()
    print(f"random-timing on OOS slice ({len(pool)} draws): median={np.median(pool):.3f}  "
          f"p95={np.percentile(pool,95):.3f}")
    print(f"REAL OOS %PF={oos_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.4f})")

    print(f"\nMultiple-testing correction (K={len(grid)} is the EXACT grid size searched, not an estimate):")
    rng2 = np.random.default_rng(7)
    for K in (1, len(grid)):
        b = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (b >= oos_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(b):.3f}  p={p_k:.4f}  [{verdict}]")
