"""
CORRECTED random-timing null, replacing stoch_table_claims_null_test.py.

That file's null test had a real confound, found by investigating why
every one of its five configs landed on the exact same minimum
possible p-value (0.0033 with 300 draws) - a huge red flag per this
project's "investigate alarming results before reporting" rule.

The bug: both the real and random trades compute their stop distance
(swing = 10-bar low/high) from their OWN entry bar's preceding window.
But a real stochastic zone-extreme signal bar is, by construction, near
a local price extreme - so its 10-bar swing stop is naturally TIGHT. A
random bar, picked from anywhere, is usually mid-range with a much
WIDER stop. Confirmed directly on GOLD M5 (8,3,3/85-15): real signal
bars average 0.052% risk, random bars average 0.147% risk - nearly 3x
wider. Since the 1:2 R:R target also scales off that same risk
distance, real losing trades were mechanically smaller than random
losing trades for a reason that has NOTHING to do with entry timing
skill - fully explaining the suspicious uniform minimum p-value across
five very different instruments/timeframes/parameter sets.

Fix: each random draw's stop/target distance is now drawn from the
REAL trades' own risk_pct distribution (shuffled, with replacement)
instead of recomputed from the random bar's own 10-bar window. This
keeps the risk-per-trade distribution IDENTICAL between real and
random by construction, isolating the one thing actually being tested
- whether WHEN you enter matters, with risk-sizing held constant.

Honest K=1 per config (first CORRECT random-timing check of each - the
previous file's result is retracted, not counted as a separate line).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from stoch_table_claims_verify_test import load, build_trades, SWING_BARS, RR, TIME_CAP_BARS

N_DRAWS = 300


def real_risk_pcts(df, real_trades):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    risks = []
    for t in real_trades:
        i = t["entry_i"]
        dir_ = t["dir"]
        swing = low_a[i - SWING_BARS:i].min() if dir_ > 0 else high_a[i - SWING_BARS:i].max()
        risks.append(abs(close_a[i] - swing) / close_a[i])
    return np.array(risks)


def random_timing_null_risk_matched(df, point, k_period, slowing, d_period, real_trades, n_draws=N_DRAWS, seed=0):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, k_period, slowing, d_period)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    start = k_period + slowing + d_period + SWING_BARS + 5
    valid_idx_arr = np.array([i for i in range(start, n - TIME_CAP_BARS - 2) if valid[i]])

    n_long = sum(1 for r in real_trades if r["dir"] > 0)
    n_short = sum(1 for r in real_trades if r["dir"] < 0)
    target_trades = n_long + n_short
    risk_pcts = real_risk_pcts(df, real_trades)
    rng = np.random.default_rng(seed)

    net_pcts = []
    for draw in range(n_draws):
        dirs_pool = [1] * n_long + [-1] * n_short
        rng.shuffle(dirs_pool)
        risk_pool = risk_pcts.copy()
        rng.shuffle(risk_pool)
        total = 0.0
        next_free = start
        taken = 0
        dir_pool_i = 0
        pool = []
        pool_pos = 0
        while taken < target_trades:
            if pool_pos >= len(pool):
                batch = rng.choice(valid_idx_arr, size=max(target_trades * 3, 200), replace=True)
                pool = sorted(int(x) for x in batch if x >= next_free)
                pool_pos = 0
                if not pool:
                    break
            i = pool[pool_pos]
            pool_pos += 1
            if i < next_free:
                continue
            dir_ = dirs_pool[dir_pool_i % len(dirs_pool)]
            risk_pct = risk_pool[dir_pool_i % len(risk_pool)]
            dir_pool_i += 1
            fill_i = i + 1
            if fill_i >= n:
                continue
            sc = spread[fill_i] * point
            entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
            risk_abs = risk_pct * entry_px
            stop_px = entry_px - dir_ * risk_abs
            target_px = entry_px + dir_ * RR * risk_abs
            hard_limit = min(fill_i + TIME_CAP_BARS, n - 1)

            exit_i, exit_px = None, None
            for j in range(fill_i + 1, hard_limit + 1):
                stop_hit = (low[j] <= stop_px) if dir_ > 0 else (high[j] >= stop_px)
                target_hit = (high[j] >= target_px) if dir_ > 0 else (low[j] <= target_px)
                if stop_hit:
                    exit_i, exit_px = j, stop_px
                    break
                if target_hit:
                    exit_i, exit_px = j, target_px
                    break
                if valid[j] and valid[j - 1]:
                    opposite = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                    if opposite:
                        scj = spread[j] * point
                        exit_i = j
                        exit_px = close[j] - (scj if dir_ > 0 else -scj)
                        break
            if exit_i is None:
                exit_i, exit_px = hard_limit, close[hard_limit]
            total += ((exit_px - entry_px) / entry_px) * dir_
            next_free = exit_i + 1
            taken += 1
        net_pcts.append(total)

    net_pcts = np.array(net_pcts)
    real_net = sum(r["pnl_pct"] for r in real_trades)
    p_value = (np.sum(net_pcts >= real_net) + 1) / (n_draws + 1)
    return real_net, net_pcts, p_value


def run_one(label, symbol_file, trim_gold, k_period, slowing, d_period, zone_low, zone_high):
    df, point = load(symbol_file, trim_gold=trim_gold)
    real_trades = build_trades(df, point, k_period, slowing, d_period, zone_low, zone_high)
    real_net = sum(r["pnl_pct"] for r in real_trades)
    print(f"\n{'#'*100}\n{label}\n{'#'*100}")
    print(f"  Real: n={len(real_trades)}  net%={100*real_net:.2f}")
    real_net2, null_dist, p = random_timing_null_risk_matched(df, point, k_period, slowing, d_period, real_trades)
    print(f"  null mean net%  = {100*null_dist.mean():8.2f}")
    print(f"  null std%       = {100*null_dist.std():8.2f}")
    print(f"  null 5th pct    = {100*np.percentile(null_dist, 5):8.2f}")
    print(f"  null 95th pct   = {100*np.percentile(null_dist, 95):8.2f}")
    print(f"  p-value         = {p:.4f}")
    if real_net2 < null_dist.mean():
        verdict = "WORSE than random-timing - entry is picking worse-than-chance timing"
    elif p > 0.05:
        verdict = "NOT distinguishable from random timing (p>0.05) - no demonstrated timing skill"
    else:
        verdict = "BEATS random-timing at p<0.05 - real signal (still check absolute %PF separately)"
    print(f"  -> {verdict}")
    return p, verdict


if __name__ == "__main__":
    results = []
    results.append(("GOLD M5  (8,3,3, 85/15)",   run_one("GOLD M5  (8,3,3 / 85-15) vs RISK-MATCHED random timing",
                     "GOLD_M5.csv", True, 8, 3, 3, 15.0, 85.0)))
    results.append(("GOLD M15 (14,3,3, 80/20)",  run_one("GOLD M15 (14,3,3 / 80-20) vs RISK-MATCHED random timing",
                     "GOLD_M15_native.csv", True, 14, 3, 3, 20.0, 80.0)))
    results.append(("SILVER M5  (14,3,3, 90/10)", run_one("SILVER M5  (14,3,3 / 90-10) vs RISK-MATCHED random timing",
                     "SILVER_M5.csv", False, 14, 3, 3, 10.0, 90.0)))
    results.append(("SILVER M15 (21,3,3, 85/15)", run_one("SILVER M15 (21,3,3 / 85-15) vs RISK-MATCHED random timing",
                     "SILVER_M15_native.csv", False, 21, 3, 3, 15.0, 85.0)))
    results.append(("BTC M5  (14,3,3, 80/20)",    run_one("BTC M5  (14,3,3 / 80-20) vs RISK-MATCHED random timing",
                     "BTCUSD_M5.csv", False, 14, 3, 3, 20.0, 80.0)))

    print(f"\n\n{'='*100}\nSUMMARY (risk-matched null)\n{'='*100}")
    for label, (p, verdict) in results:
        print(f"  {label:<32} p={p:.4f}  {verdict}")
    print(f"\n  Honest K=1 per config for this corrected null test (supersedes the")
    print(f"  retracted stoch_table_claims_null_test.py result, not an additional line).")
