"""
Risk-matched random-timing null for the engulfing-at-extreme
construction (candlestick_engulfing_reversal_test.py) - the best raw
%PF result found all session (Gold 0.916, Silver 0.418, BTC 0.445,
all well above every stochastic variant tested tonight). Before this
gets treated as a real finding, it needs the same scrutiny everything
else got.

Same risk-matching methodology validated earlier tonight
(stoch_table_claims_9tf_risk_matched_null_test.py, after an Opus audit
fixed a geometry bug in the first attempt): each random draw borrows a
REAL trade's own (direction, stop distance, target distance) directly
- shuffled - rather than recomputing risk from the random bar's own
context, which was confirmed earlier to be a required fix (a random
bar's own swing distance differs systematically from a real signal
bar's, which otherwise fakes an "edge" purely from risk-size
differences, not timing skill).

No stochastic-cross coupling artifact risk here (that artifact,
found earlier tonight, came from the exit being tied to a fresh
entry-stochastic cross - this construction's exit is pure stop/target/
time-cap, no cross of any kind), so a uniform floor p-value here would
mean something different and still needs investigating rather than
assumed-explained by that same prior cause.

Tested on GOLD, SILVER, BTCUSD M15. Honest K=1 per instrument for this
null check.
"""
import sys
import os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from candlestick_engulfing_reversal_test import load_m15, build_trades, SWING_BARS, RR, TIME_CAP_BARS

N_DRAWS = 1000


def real_risk_pcts_and_dirs(df, real_trades):
    close_a = df["close"].values
    risks, dirs = [], []
    for t in real_trades:
        i = t["entry_i"]
        dir_ = t["dir"]
        low_i = df["low"].values[i]
        high_i = df["high"].values[i]
        swing = low_i if dir_ > 0 else high_i
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


def run_instrument(label, symbol_file, trim_gold):
    df, point = load_m15(symbol_file, trim_gold=trim_gold)
    real_trades = build_trades(df, point)
    real_net = sum(t["pnl_pct"] for t in real_trades)
    print(f"\n{'#'*100}\n{label} M15 - engulfing-at-extreme vs RISK-MATCHED random timing\n{'#'*100}")
    print(f"  Real: n={len(real_trades)}  net%={100*real_net:.2f}")
    real_net2, null_dist, p = random_timing_null(df, point, real_trades)
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
        verdict = "BEATS random-timing at p<0.05 - real signal"
    print(f"  -> {verdict}")
    return p, verdict


if __name__ == "__main__":
    results = []
    results.append(("GOLD",   run_instrument("GOLD", "GOLD_M15_native.csv", True)))
    results.append(("SILVER", run_instrument("SILVER", "SILVER_M15_native.csv", False)))
    results.append(("BTCUSD", run_instrument("BTCUSD", "BTCUSD_M15_native.csv", False)))

    print(f"\n\n{'='*100}\nSUMMARY\n{'='*100}")
    for label, (p, verdict) in results:
        print(f"  {label:<10} p={p:.4f}  {verdict}")
    print(f"\n  Honest K=1 per instrument for this null test.")
