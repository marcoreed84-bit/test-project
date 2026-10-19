"""
Random-timing null for the six stochastic configs just tested in
stoch_table_claims_verify_test.py, per direct request - "I want to know
the best settings." Real %PF alone doesn't say whether the stochastic's
ENTRY TIMING beats chance; a random-timing null (same exit machinery,
same real spread cost, entry count/direction mix matched to the real
result) answers that specific question, same discipline as this
project's established BTC H1 null test
(classic_stoch_21_5_5_btc_h1_null_test.py) - reusing its corrected
oversampling-pool draw method (the original draw method had two
sequential bugs, both found and fixed earlier this project - see that
file's own comments for the full history).

BTC M15 (21,5,5, 80/20) already has this null test's result from
earlier research (different file, different timeframe construction
history) - not reproduced here; this file covers the five NEWLY tested
configs from the table-verification file.

Honest K=1 per config for this null test (first random-timing check of
each of these five specific configs).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from stoch_table_claims_verify_test import load, build_trades, SWING_BARS, RR, TIME_CAP_BARS

N_DRAWS = 300


def random_timing_null(df, point, k_period, slowing, d_period, real_trades, n_draws=N_DRAWS, seed=0):
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
    valid_idx = [i for i in range(start, n - TIME_CAP_BARS - 2) if valid[i]]
    valid_idx_arr = np.array(valid_idx)

    n_long = sum(1 for r in real_trades if r["dir"] > 0)
    n_short = sum(1 for r in real_trades if r["dir"] < 0)
    target_trades = n_long + n_short
    rng = np.random.default_rng(seed)

    net_pcts = []
    for draw in range(n_draws):
        dirs_pool = [1] * n_long + [-1] * n_short
        rng.shuffle(dirs_pool)
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
            dir_pool_i += 1
            swing = min(low[i - SWING_BARS:i]) if dir_ > 0 else max(high[i - SWING_BARS:i])
            risk = dir_ * (close[i] - swing)
            if risk <= 0.0:
                continue
            fill_i = i + 1
            if fill_i >= n:
                continue
            sc = spread[fill_i] * point
            entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)
            stop_px = swing
            target_px = entry_px + dir_ * RR * risk
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
    real_net2, null_dist, p = random_timing_null(df, point, k_period, slowing, d_period, real_trades)
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
        verdict = f"BEATS random-timing at p<0.05 - real signal (still check absolute %PF separately)"
    print(f"  -> {verdict}")
    return p, verdict


if __name__ == "__main__":
    results = []
    results.append(("GOLD M5  (8,3,3, 85/15)",   run_one("GOLD M5  (8,3,3 / 85-15)  vs random timing",
                     "GOLD_M5.csv", True, 8, 3, 3, 15.0, 85.0)))
    results.append(("GOLD M15 (14,3,3, 80/20)",  run_one("GOLD M15 (14,3,3 / 80-20) vs random timing",
                     "GOLD_M15_native.csv", True, 14, 3, 3, 20.0, 80.0)))
    results.append(("SILVER M5  (14,3,3, 90/10)", run_one("SILVER M5  (14,3,3 / 90-10) vs random timing",
                     "SILVER_M5.csv", False, 14, 3, 3, 10.0, 90.0)))
    results.append(("SILVER M15 (21,3,3, 85/15)", run_one("SILVER M15 (21,3,3 / 85-15) vs random timing",
                     "SILVER_M15_native.csv", False, 21, 3, 3, 15.0, 85.0)))
    results.append(("BTC M5  (14,3,3, 80/20)",    run_one("BTC M5  (14,3,3 / 80-20) vs random timing",
                     "BTCUSD_M5.csv", False, 14, 3, 3, 20.0, 80.0)))

    print(f"\n\n{'='*100}\nSUMMARY\n{'='*100}")
    for label, (p, verdict) in results:
        print(f"  {label:<32} p={p:.4f}  {verdict}")
    print(f"\n  BTC M15 (21,5,5, 80/20): already tested earlier this project -")
    print(f"  p=0.13, NOT distinguishable from random timing (classic_stoch_21_5_5_btc_h1_null_test.py,")
    print(f"  H1 timeframe/grace-trail exit variant, not the raw M15 construction used elsewhere here).")
    print(f"\n  Honest K=1 per config for this null test (5 new).")
