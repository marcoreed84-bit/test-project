"""
Risk-matched random-timing null for GOLD INSIDE_BREAKOUT - the one
configuration, out of 15 tried in candlestick_patterns_batch_test.py
(5 patterns x 3 instruments), that cleared %PF=1.0 net
(%PF=1.017, net+16.71%). Everything else in that batch failed. Before
this is reported as anything real, it needs the same risk-matched
random-timing null used all night, AND an honest K=15 multiple-testing
correction (this is the best of 15 configurations searched this round,
not a single pre-registered test).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from candlestick_patterns_batch_test import load_m15, signals_inside_breakout, build_trades, SWING_BARS, RR, TIME_CAP_BARS

N_DRAWS = 2000


def real_risk_pcts_and_dirs(df, real_trades):
    low_a, high_a, close_a = df["low"].values, df["high"].values, df["close"].values
    risks, dirs = [], []
    for t in real_trades:
        i = t["entry_i"]
        dir_ = t["dir"]
        swing = min(low_a[i - SWING_BARS:i]) if dir_ > 0 else max(high_a[i - SWING_BARS:i])
        risks.append(abs(close_a[i] - swing) / close_a[i])
        dirs.append(dir_)
    return np.array(risks), np.array(dirs)


def random_timing_null(df, point, real_trades, n_draws=N_DRAWS, seed=0):
    close = df["close"].values.tolist()
    spread = df["spread"].values.tolist()
    high_l = df["high"].values.tolist()
    low_l = df["low"].values.tolist()
    n = len(close)

    risk_pcts, real_dirs = real_risk_pcts_and_dirs(df, real_trades)
    n_long = int((real_dirs > 0).sum())
    n_short = int((real_dirs < 0).sum())
    target_trades = n_long + n_short

    start = SWING_BARS + 5
    valid_idx_arr = np.array(range(start, n - TIME_CAP_BARS - 2))
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
        pool_i = 0
        pool, pool_pos = [], 0
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
            dir_ = dirs_pool[pool_i % len(dirs_pool)]
            risk_pct = risk_pool[pool_i % len(risk_pool)]
            pool_i += 1
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
                stop_hit = (low_l[j] <= stop_px) if dir_ > 0 else (high_l[j] >= stop_px)
                target_hit = (high_l[j] >= target_px) if dir_ > 0 else (low_l[j] <= target_px)
                if stop_hit:
                    exit_i, exit_px = j, stop_px
                    break
                if target_hit:
                    exit_i, exit_px = j, target_px
                    break
            if exit_i is None:
                exit_i, exit_px = hard_limit, close[hard_limit]
            total += ((exit_px - entry_px) / entry_px) * dir_
            next_free = exit_i + 1
            taken += 1
        net_pcts.append(total)

    net_pcts = np.array(net_pcts)
    real_net = sum(t["pnl_pct"] for t in real_trades)
    p_value = (np.sum(net_pcts >= real_net) + 1) / (n_draws + 1)
    return real_net, net_pcts, p_value


if __name__ == "__main__":
    df, point = load_m15("GOLD_M15_native.csv", trim_gold=True)
    n = len(df)
    o, h, l, c = df["open"].tolist(), df["high"].tolist(), df["low"].tolist(), df["close"].tolist()
    dirs = signals_inside_breakout(o, h, l, c, n)
    real_trades = build_trades(df, point, dirs)
    real_net = sum(t["pnl_pct"] for t in real_trades)

    print(f"\n{'#'*100}\nGOLD M15 - INSIDE_BREAKOUT vs RISK-MATCHED random timing\n{'#'*100}")
    print(f"  Real: n={len(real_trades)}  net%={100*real_net:.2f}")
    real_net2, null_dist, p = random_timing_null(df, point, real_trades)
    print(f"  null mean net%  = {100*null_dist.mean():8.2f}")
    print(f"  null std%       = {100*null_dist.std():8.2f}")
    print(f"  null 5th pct    = {100*np.percentile(null_dist, 5):8.2f}")
    print(f"  null 95th pct   = {100*np.percentile(null_dist, 95):8.2f}")
    print(f"  raw p-value     = {p:.4f}")

    K = 15   # 5 patterns x 3 instruments searched this round
    sidak_p = 1 - (1 - p) ** K
    print(f"\n  Honest K={K} for this batch (5 patterns x 3 instruments) - this result")
    print(f"  is the best of 15, not a single pre-registered test.")
    print(f"  Sidak-corrected p-value = {sidak_p:.4f}")
    if real_net2 < null_dist.mean():
        verdict = "WORSE than random-timing - entry is picking worse-than-chance timing"
    elif sidak_p > 0.05:
        verdict = "Does NOT survive honest K=15 correction - overfitting, not a real signal"
    else:
        verdict = "SURVIVES honest K=15 correction - real signal"
    print(f"  -> {verdict}")
