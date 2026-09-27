"""
Does Meridian_EA.mq5's frozen v1.07 shipped construction (21/50 EMA cross,
confirmed by close vs 250-period SMA + VWAP direction agreement + S/R
distance filter MIN_SR=0.50xATR, 2.5xATR safety stop, hold-to-next-reversal
exit) transfer to SILVER and BTCUSD with the SAME parameters, unchanged?
Same cross-asset question already asked of H&S (transfers cleanly), Aurelius
(fails on both) and Vanguard (fails on both, worse than Aurelius).

Data/H4: identical approach to vanguard_silver_btc_test.py - each
instrument's own real M5 export (native from its own export start, no
contamination to trim), H4 resampled from that same M5 purely to derive D1
H/L for the S/R filter via engine.derive_d1_from_h4().

BUG AVOIDED (same class as Aurelius/Silver and Vanguard/Silver):
meridian_random_timing_test.py's build_real()/sim_random_entry() hardcode
`POINT = E.POINT` (GOLD's 0.01) at module level for spread-cost-on-fill.
SILVER's real point is 0.001 (10x overcharge if left as-is); BTCUSD's is
numerically 0.01 same as gold (confirmed in BTCUSD_M5.csv's own header) but
kept explicit rather than assumed. build_real_p/sim_random_entry_p/
make_pct_pf_p here are copies of that file's functions with `point`
promoted to an explicit parameter - everything else byte-identical.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import pandas as pd
import engine as E

DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"
SAFETY_SL = 2.5
MIN_SR = 0.50
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


def sim_filtered_entries_p(raw_events, entry_ok_mask, close, high, low, spread, atr, n, safety_sl_atr, point):
    """m5_stack_variants_fixed_test.sim_filtered_entries with `point` promoted
    to a parameter instead of a hardcoded module-level GOLD constant."""
    trades = []
    for k in range(len(raw_events) - 1):
        i, d = raw_events[k]
        if not entry_ok_mask[i]:
            continue
        i_next, _ = raw_events[k + 1]
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * point
        is_buy = d > 0
        entry = raw + sc if is_buy else raw - sc
        sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
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
        trades.append((i, exit_bar, pnl, is_buy))
    return trades


def build_real(df5, h4, point):
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    m21 = E.ma(close, 21, "ema")
    m50 = E.ma(close, 50, "ema")
    m150 = ctx["m150"]

    above = m21 > m50
    valid = ~np.isnan(m21) & ~np.isnan(m50)
    above_prev = np.concatenate(([False], above[:-1]))
    valid_prev = np.concatenate(([False], valid[:-1]))
    cross_up = above & ~above_prev & valid & valid_prev
    cross_dn = (~above) & above_prev & valid & valid_prev
    raw_events = sorted([(i, 1.0) for i in np.where(cross_up)[0]] +
                         [(i, -1.0) for i in np.where(cross_dn)[0]], key=lambda e: e[0])

    cond_150 = close > m150
    cond_vwap = close > vwap
    ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        c150 = cond_150[i] if d > 0 else (not cond_150[i])
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not (c150 and cv) or np.isnan(m150[i]):
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    trades = sim_filtered_entries_p(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL, point)
    return trades, raw_events, close, high, low, spread, atr, n


def make_pct_pf_p(close, spread, point):
    def pf(trades):
        if not trades:
            return float("nan")
        pcts = []
        for (i, exit_bar, pnl, is_buy) in trades:
            sc = spread[i + 1] * point
            entry = close[i] + sc if is_buy else close[i] - sc
            pcts.append(pnl / entry)
        arr = np.array(pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        return gw / gl if gl > 0 else float("inf")
    return pf


def sim_random_entry_p(raw_events, close, high, low, spread, atr, n, rng, p_fire, safety_sl_atr, point):
    trades = []
    last_exit = -1
    real_event_bars = np.array([e[0] for e in raw_events])
    real_event_dirs = np.array([e[1] for e in raw_events])
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
        sc = spread[fill_i] * point
        entry = close[i] + sc if is_buy else close[i] - sc
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
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades


def calibrate_p_fire(raw_events, close, high, low, spread, atr, n, rng, target_n, point, trials=3):
    p_fire = 0.001
    for _ in range(trials):
        trades = sim_random_entry_p(raw_events, close, high, low, spread, atr, n, rng, p_fire, SAFETY_SL, point)
        if len(trades) == 0:
            p_fire *= 3
            continue
        p_fire *= target_n / len(trades)
        p_fire = min(max(p_fire, 1e-6), 0.5)
    return p_fire


def run_instrument(symbol, point):
    print("=" * 78)
    print(f"{symbol} M5 -- Meridian v1.07 frozen defaults (point={point})")
    print("=" * 78)
    df5 = load_m5(symbol)
    h4 = resample_h4_from_m5(df5)
    print(f"data: n={len(df5)} M5 bars, {df5['time'].min()} -> {df5['time'].max()} "
          f"({(df5['time'].max()-df5['time'].min()).days/365.25:.2f} yrs) - "
          f"native export start (300000-row cap), never touched by any parameter search")

    real_trades, raw_events, close, high, low, spread, atr, n = build_real(df5, h4, point)
    pf_fn = make_pct_pf_p(close, spread, point)
    real_pct_pf = pf_fn(real_trades)
    if not real_trades:
        print("\n  NO TRADES generated on this instrument's data - cannot evaluate.\n")
        return
    pnls = np.array([t[2] for t in real_trades])
    print(f"\nREAL Meridian M5 (frozen v1.07, unchanged) on {symbol}:")
    print(f"  n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = calibrate_p_fire(raw_events, close, high, low, spread, atr, n, rng, len(real_trades), point)
    print(f"Calibrated p_fire={p_fire:.6f}")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines on {symbol}...")
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(N_RANDOM):
        tr = sim_random_entry_p(raw_events, close, high, low, spread, atr, n, rng, p_fire, SAFETY_SL, point)
        pool.append(pf_fn(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.4f})")

    print("\nMultiple-testing correction (best-of-K; K=15 is Meridian's own gold tuning-history estimate):")
    rng2 = np.random.default_rng(7)
    for K in (1, 15, 30, 50):
        best = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (best >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p={p_k:.4f}  [{verdict}]")
    print()


if __name__ == "__main__":
    run_instrument("SILVER", point=0.001)
    run_instrument("BTCUSD", point=0.01)
