"""
Does Vanguard_EA.mq5's frozen v1.06 M5 defaults (FractalK=100 diagonal-
trendline breakout, VWAP direction filter, MIN_SR=0.50xATR distance filter,
4.0xATR safety stop, 225-bar stale exit) transfer to SILVER and BTCUSD with
the SAME parameters, unchanged? Same question already asked and answered for
H&S (hs_silver_test.py / BTC's own real MT5 confirmation - transfers cleanly)
and Aurelius (aurelius_m15_silver_test.py / aurelius_*_tailored_test.py -
fails on both, even after a full tailored retune).

Data: user's real SILVER_M5.csv / BTCUSD_M5.csv exports (both capped at
300000 rows by the same MT5 export limit GOLD_M5.csv hit - SILVER from
2022-07, BTCUSD from 2023-11 - i.e. genuinely native M5 history from each
instrument's own export start, NOT the daily/hourly-mislabeled-as-M15
contamination found on the M15/H4 native exports; nothing to trim here).
No native H4 export exists for either instrument, so H4 is resampled from
each instrument's own M5 (lossless OHLC aggregation, same convention as
engine.py's resample_m15_from_m5) purely to derive D1 H/L for Vanguard's
S/R-distance filter via derive_d1_from_h4() - identical approach already
used for Silver M15 Aurelius (aurelius_m15_silver_test.py resampled H4 from
M15 there; here it's resampled from M5, one level down, same reasoning).

BUG AVOIDED (same class as the Aurelius/Silver point-size bug found in
aurelius_m15_silver_test.py): vanguard_random_timing_test.py's sim_full/
sim_random_entry hardcode `POINT = E.POINT` (GOLD's 0.01) at module level
when pricing the spread-cost-on-fill. SILVER's real point is 0.001 (a 10x
overcharge if left as-is); BTCUSD's real point is numerically 0.01 same as
gold (coincidence of this broker's BTCUSD quote convention, confirmed in
BTCUSD_M5.csv's own header: meta_digits=2, meta_point=0.01) but is kept
explicit below rather than assumed. sim_full_p/sim_random_entry_p here are
copies of vanguard_random_timing_test.py's functions with `point` promoted
to an explicit parameter - everything else byte-identical.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
FRACTAL_K = 100
MIN_SR = 0.50
SAFETY_SL_ATR = 4.0
STALE_BARS = 225
STALE_MIN_PROFIT_ATR = 0.0
N_RANDOM = 600


def load_m5(symbol):
    df = pd.read_csv(f"{DATA_DIR}/{symbol}_M5.csv", skiprows=1)
    df["time"] = pd.to_datetime(df["time"], format="%Y.%m.%d %H:%M:%S")
    return df.sort_values("time").reset_index(drop=True)


def resample_h4_from_m5(df5):
    d = df5.set_index("time")
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
    """vanguard_random_timing_test.sim_full with `point` promoted to a
    parameter instead of a hardcoded module-level GOLD constant."""
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
                        safety_sl_atr, point, stale_bars, stale_min_profit_atr):
    trades = []
    last_exit = -1
    real_event_bars = np.array([e[0] for e in real_events])
    real_event_dirs = np.array([e[1] for e in real_events])
    for i in range(n - 1):
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


def calibrate_p_fire(real_events, close, high, low, spread, atr, n, rng, target_n, point, trials=3):
    p_fire = 0.001
    for _ in range(trials):
        trades = sim_random_entry_p(real_events, close, high, low, spread, atr, n, rng, p_fire,
                                     SAFETY_SL_ATR, point, STALE_BARS, STALE_MIN_PROFIT_ATR)
        if len(trades) == 0:
            p_fire *= 3
            continue
        p_fire *= target_n / len(trades)
        p_fire = min(max(p_fire, 1e-6), 0.5)
    return p_fire


def run_instrument(symbol, point):
    print("=" * 78)
    print(f"{symbol} M5 -- Vanguard v1.06 frozen defaults (point={point})")
    print("=" * 78)
    df5 = load_m5(symbol)
    h4 = resample_h4_from_m5(df5)
    print(f"data: n={len(df5)} M5 bars, {df5['time'].min()} -> {df5['time'].max()} "
          f"({(df5['time'].max()-df5['time'].min()).days/365.25:.2f} yrs) - "
          f"native export start (300000-row cap), never touched by any parameter search")

    ctx = E.build_context(df5, h4, E.P)
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    n = ctx["n"]

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    print(f"{len(events)} raw trendline-breakout events -> {entry_ok[[i for i,_ in events]].sum()} pass VWAP+S/R gate")

    real_trades = sim_full_p(events, entry_ok, close, high, low, spread, atr, n,
                              SAFETY_SL_ATR, point, stale_bars=STALE_BARS,
                              stale_min_profit_atr=STALE_MIN_PROFIT_ATR)
    real_pct_pf = pct_pf(real_trades)
    if not real_trades:
        print("\n  NO TRADES generated on this instrument's data - cannot evaluate.\n")
        return
    pnls = np.array([t[2] for t in real_trades])
    print(f"\nREAL Vanguard M5 (frozen v1.06, unchanged) on {symbol}:")
    print(f"  n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = calibrate_p_fire(events, close, high, low, spread, atr, n, rng, len(real_trades), point)
    print(f"Calibrated p_fire={p_fire:.6f}")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines on {symbol}...")
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(N_RANDOM):
        tr = sim_random_entry_p(events, close, high, low, spread, atr, n, rng, p_fire,
                                 SAFETY_SL_ATR, point, STALE_BARS, STALE_MIN_PROFIT_ATR)
        pool.append(pct_pf(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.4f})")

    print("\nMultiple-testing correction (best-of-K; K=24 is Vanguard's own gold tuning-history estimate):")
    rng2 = np.random.default_rng(7)
    for K in (1, 24, 50, 100):
        best = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (best >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p={p_k:.4f}  [{verdict}]")
    print()


if __name__ == "__main__":
    run_instrument("SILVER", point=0.001)
    run_instrument("BTCUSD", point=0.01)
