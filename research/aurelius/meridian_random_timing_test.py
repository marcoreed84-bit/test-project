"""
Same random-timing baseline + multiple-testing correction applied to
Meridian_EA.mq5's real shipped construction: 21/50 EMA cross, confirmed by
close vs the 250-period SMA ("m150" in this repo's own ctx/variable naming,
per meridian_dd_confluence_test.py's own correction note - it genuinely IS
Aurelius's real p150=250/m150=sma via engine.build_context(df5,h4,E.P), not
a mismatch) + VWAP direction agreement + S/R distance filter
(MIN_SR=0.50xATR), safety stop 2.5xATR, hold-to-next-reversal exit.
Reuses m5_stack_variants_fixed_test.py's own sim_filtered_entries()
unmodified.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from m5_stack_variants_fixed_test import sim_filtered_entries

POINT = E.POINT
SAFETY_SL = 2.5
MIN_SR = 0.50
N_RANDOM = 300


def build_real(df5, h4):
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

    trades = sim_filtered_entries(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL)
    return trades, raw_events, close, high, low, spread, atr, n


def make_pct_pf(close, spread):
    def pf(trades):
        if not trades:
            return float("nan")
        pcts = []
        for (i, exit_bar, pnl, is_buy) in trades:
            sc = spread[i + 1] * POINT
            entry = close[i] + sc if is_buy else close[i] - sc
            pcts.append(pnl / entry)
        arr = np.array(pcts)
        gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
        return gw / gl if gl > 0 else float("inf")
    return pf


def sim_random_entry(raw_events, close, high, low, spread, atr, n, rng, p_fire, safety_sl_atr):
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
        sc = spread[fill_i] * POINT
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


def calibrate_p_fire(raw_events, close, high, low, spread, atr, n, rng, target_n, trials=3):
    p_fire = 0.001
    for _ in range(trials):
        trades = sim_random_entry(raw_events, close, high, low, spread, atr, n, rng, p_fire, SAFETY_SL)
        if len(trades) == 0:
            p_fire *= 3
            continue
        p_fire *= target_n / len(trades)
        p_fire = min(max(p_fire, 1e-6), 0.5)
    return p_fire


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    print(f"M5 data: n={len(df5)} bars, {df5['time'].min()} -> {df5['time'].max()}\n")

    real_trades, raw_events, close, high, low, spread, atr, n = build_real(df5, h4)
    pf_fn = make_pct_pf(close, spread)
    real_pct_pf = pf_fn(real_trades)
    pnls = np.array([t[2] for t in real_trades])
    print(f"REAL Meridian v1.07 shipped defaults: n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  "
          f"net={pnls.sum():.2f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = calibrate_p_fire(raw_events, close, high, low, spread, atr, n, rng, len(real_trades))
    print(f"\nCalibrated p_fire={p_fire:.6f}")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines (same exit machinery)...")
    rng = np.random.default_rng(42)
    pool = []
    for _ in range(N_RANDOM):
        tr = sim_random_entry(raw_events, close, high, low, spread, atr, n, rng, p_fire, SAFETY_SL)
        pool.append(pf_fn(tr))
    pool = np.array(pool)
    pool = pool[~np.isnan(pool) & ~np.isinf(pool)]
    print(f"  random-entry %PF distribution: median={np.median(pool):.3f}  p95={np.percentile(pool,95):.3f}")
    pctile = 100 * (pool < real_pct_pf).mean()
    p_val = (pool >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.3f})")

    print("\nMultiple-testing correction (best-of-K; K estimated from this dir's own 15 dedicated")
    print("meridian_*.py research files):")
    rng2 = np.random.default_rng(7)
    for K in (1, 15, 30, 50):
        best = pool[rng2.integers(0, len(pool), size=(5000, K))].max(axis=1)
        p_k = (best >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p95={np.percentile(best,95):.3f}  "
              f"p={p_k:.3f}  [{verdict}]")
