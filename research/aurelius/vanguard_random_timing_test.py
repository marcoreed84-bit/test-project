"""
Same random-timing baseline discipline applied across this session
(Wolfe Wave -> RoundingBottom/Rectangle -> H&S -> Aurelius, 2026-09-26)
now applied to Vanguard_EA.mq5's real shipped v1.06 construction: a
diagonal-trendline breakout (2 confirmed fractal swings, FRACTAL_K=100,
descending line = lower highs / ascending line = higher lows, buy on a
close back above the descending line, sell on a close back below the
ascending line), gated by VWAP direction + S/R distance (MIN_SR=0.50xATR),
exited by the NEXT OPPOSITE breakout, a 4.0xATR safety stop, or a 225-bar
stale-exit - reusing the ALREADY-BUILT real simulator (trendline_break_
test.py's build_trendline_values/build_breakout_events,
vanguard_m5_joint_sweep_test.py's sim_full/FRACTAL_K/MIN_SR - these are
the files that actually produced the shipped v1.06 defaults, not a fresh
port).

ADAPTATION (same reasoning as Aurelius): no fixed bracket to replay, so
this tests whether Vanguard's real entry TIMING (the specific trendline-
breakout + VWAP + S/R conditions) beats the SAME exit machinery (4.0xATR
stop, 225-bar stale exit, exit on the next REAL opposite-direction
breakout event - kept real and data-driven, not synthetic) fired at
RANDOM entry times with a coin-flip direction, calibrated to the same
average trade count.

%PF (not raw points) throughout - M5 spans ~2022-2026, GOLD ~$1700->~$4000
over that window, the same drift-bias risk flagged for every other pattern
this session.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events

POINT = E.POINT
FRACTAL_K = 100
MIN_SR = 0.50
SAFETY_SL_ATR = 4.0
STALE_BARS = 225
STALE_MIN_PROFIT_ATR = 0.0
N_RANDOM = 300


def sim_full(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr,
             stale_bars=None, stale_min_profit_atr=0.0):
    """Verbatim from vanguard_m5_joint_sweep_test.py (the file that produced
    the real shipped defaults) - unmodified, just imported by copy since
    that file has no importable module-level function separate from its
    __main__ block reliance on module-level constants."""
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
        sc = spread[fill_i] * POINT
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


def pct_pf(trades):
    if not trades:
        return float("nan")
    arr = np.array([t[2] / t[4] for t in trades])
    gw = arr[arr > 0].sum(); gl = -arr[arr <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def sim_random_entry(real_events, close, high, low, spread, atr, n, rng, p_fire,
                      safety_sl_atr, stale_bars, stale_min_profit_atr):
    """Same exit machinery as sim_full (opposite REAL breakout event, ATR
    stop, stale exit) but entries fire at random bars with a coin-flip
    direction instead of a real trendline-breakout signal. `real_events`
    (the actual breakout event list) is reused ONLY to find each random
    trade's own "next opposite-direction real event" exit cap, matching
    the real system's own "hold until the trend genuinely reverses" logic
    rather than inventing a synthetic reversal rule."""
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
        sc = spread[fill_i] * POINT
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


def calibrate_p_fire(real_events, close, high, low, spread, atr, n, rng, target_n, trials=3):
    p_fire = 0.001
    for _ in range(trials):
        trades = sim_random_entry(real_events, close, high, low, spread, atr, n, rng, p_fire,
                                   SAFETY_SL_ATR, STALE_BARS, STALE_MIN_PROFIT_ATR)
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
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    entry_ok = vwap_ok & sr_ok

    real_trades = sim_full(events, entry_ok, close, high, low, spread, atr, n,
                            SAFETY_SL_ATR, stale_bars=STALE_BARS, stale_min_profit_atr=STALE_MIN_PROFIT_ATR)
    real_pct_pf = pct_pf(real_trades)
    pnls = np.array([t[2] for t in real_trades])
    print(f"REAL Vanguard v1.06 shipped defaults: n={len(real_trades)}  win%={100*(pnls>0).mean():.1f}  "
          f"net={pnls.sum():.2f}  %PF={real_pct_pf:.3f}")

    rng = np.random.default_rng(1)
    p_fire = calibrate_p_fire(events, close, high, low, spread, atr, n, rng, len(real_trades))
    print(f"\nCalibrated p_fire={p_fire:.6f} to target ~{len(real_trades)} trades")

    print(f"Running {N_RANDOM} random-entry/coin-flip-direction baselines (same exit machinery)...")
    rng = np.random.default_rng(42)
    rand_pfs, rand_ns = [], []
    for _ in range(N_RANDOM):
        tr = sim_random_entry(events, close, high, low, spread, atr, n, rng, p_fire,
                               SAFETY_SL_ATR, STALE_BARS, STALE_MIN_PROFIT_ATR)
        rand_ns.append(len(tr))
        rand_pfs.append(pct_pf(tr))
    rand_pfs = np.array(rand_pfs)
    rand_pfs = rand_pfs[~np.isnan(rand_pfs) & ~np.isinf(rand_pfs)]
    print(f"  random-entry trade counts: mean={np.mean(rand_ns):.0f} (target {len(real_trades)})")
    print(f"  random-entry %PF distribution: median={np.median(rand_pfs):.3f}  "
          f"p95={np.percentile(rand_pfs,95):.3f}")
    pctile = 100 * (rand_pfs < real_pct_pf).mean()
    p_val = (rand_pfs >= real_pct_pf).mean()
    print(f"\n  REAL %PF={real_pct_pf:.3f} sits at the {pctile:.1f}th percentile (one-sided p={p_val:.3f})")

    print("\nMultiple-testing correction (best-of-K, K estimated from this session's own Vanguard tuning history):")
    rng2 = np.random.default_rng(7)
    for K in (1, 24, 50, 100):
        best = rand_pfs[rng2.integers(0, len(rand_pfs), size=(5000, K))].max(axis=1)
        pctile_k = 100 * (best < real_pct_pf).mean()
        p_k = (best >= real_pct_pf).mean()
        verdict = "SURVIVES" if p_k < 0.05 else ("borderline" if p_k < 0.15 else "DOES NOT SURVIVE")
        print(f"  K={K:>4}: best-of-K median={np.median(best):.3f}  p95={np.percentile(best,95):.3f}  "
              f"real pctile={pctile_k:5.1f}  p={p_k:.3f}  [{verdict}]")
