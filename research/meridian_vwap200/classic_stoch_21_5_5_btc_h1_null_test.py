"""
Random-timing null for the best BTC construction found tonight: H1,
Stoch(21,5,5) zone-cross entry, swing stop + 1:2 R:R target, STOCH
exit with 10-bar grace+trail (classic_stoch_21_5_5_btc_h1_stop_trail_
test.py at grace_bars=10 - full-history %PF=0.614, OOS %PF=0.819).

This checks the standing project question those numbers alone can't
answer: does the STOCHASTIC actually pick better entry TIMING than
chance, or would a random entry put through the exact same exit
machinery (swing stop, 1:2 R:R target, grace+trail, real spread) do
just as well? Same real spread cost, same exit rules, entry count and
direction mix matched to the real result - the only thing randomized
is WHEN the trade opens.

Tested on the FULL-HISTORY real result (n=2052, 827 longs / 1225
shorts) and n_draws=1000 random draws.
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from classic_stoch_21_5_5_btc_test import K_PERIOD, SLOWING, D_PERIOD, SWING_BARS, RR
from classic_stoch_21_5_5_btc_h1_test import load_btc_h1
from classic_stoch_21_5_5_btc_h1_stop_trail_test import build_trades

TIME_CAP_BARS = 300
GRACE_BARS = 10


def random_timing_null(df, point, real_trades, n_draws=1000, seed=0):
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, K_PERIOD, SLOWING, D_PERIOD)

    close, high, low, spread = close_a.tolist(), high_a.tolist(), low_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    start = K_PERIOD + SLOWING + D_PERIOD + SWING_BARS + 5
    valid_idx = [i for i in range(start, n - TIME_CAP_BARS - 2) if valid[i]]

    n_long = sum(1 for r in real_trades if r["dir"] > 0)
    n_short = sum(1 for r in real_trades if r["dir"] < 0)
    rng = np.random.default_rng(seed)

    net_pcts = []
    for draw in range(n_draws):
        picks = rng.choice(valid_idx, size=n_long + n_short, replace=False)
        dirs = [1] * n_long + [-1] * n_short
        rng.shuffle(dirs)
        total = 0.0
        # sort picks chronologically and skip overlaps the same way the
        # real construction does (entries consume bars until their own exit)
        order = sorted(range(len(picks)), key=lambda idx: picks[idx])
        next_free = start
        for oi in order:
            i = picks[oi]
            dir_ = dirs[oi]
            if i < next_free:
                continue   # would overlap a still-open random trade - skip, same spirit as the real loop
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

            pending_exit_bar = None
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
                    favorable = (dir_ > 0 and crossUp[j]) or (dir_ < 0 and crossDown[j])
                    opposite  = (dir_ > 0 and crossDown[j]) or (dir_ < 0 and crossUp[j])
                    if pending_exit_bar is not None and favorable:
                        new_swing = min(low[j - SWING_BARS:j]) if dir_ > 0 else max(high[j - SWING_BARS:j])
                        if dir_ > 0 and new_swing > stop_px:
                            stop_px = new_swing
                        elif dir_ < 0 and new_swing < stop_px:
                            stop_px = new_swing
                        pending_exit_bar = None
                    if pending_exit_bar is None and opposite:
                        pending_exit_bar = j if GRACE_BARS <= 0 else j + GRACE_BARS
                    if pending_exit_bar is not None and j >= pending_exit_bar:
                        scj = spread[j] * point
                        exit_i = j
                        exit_px = close[j] - (scj if dir_ > 0 else -scj)
                        break
            if exit_i is None:
                exit_i, exit_px = hard_limit, close[hard_limit]
            total += ((exit_px - entry_px) / entry_px) * dir_
            next_free = exit_i + 1
        net_pcts.append(total)

    net_pcts = np.array(net_pcts)
    real_net = sum(r["pnl_pct"] for r in real_trades)
    p_value = (np.sum(net_pcts >= real_net) + 1) / (n_draws + 1)
    return real_net, net_pcts, p_value


def run():
    df, point = load_btc_h1()
    real_trades = build_trades(df, point, GRACE_BARS)
    real_net = sum(r["pnl_pct"] for r in real_trades)
    n_long = sum(1 for r in real_trades if r["dir"] > 0)
    n_short = sum(1 for r in real_trades if r["dir"] < 0)
    print(f"Real H1 grace={GRACE_BARS} construction: n={len(real_trades)} ({n_long} long / {n_short} short), "
          f"net%={100*real_net:.2f}")
    print(f"Running random-timing null (n_draws=1000, same exit machinery, same real spread, "
          f"matched trade count/direction)...")
    real_net2, null_dist, p = random_timing_null(df, point, real_trades, n_draws=1000)
    print(f"\n  real net%        = {100*real_net2:7.2f}")
    print(f"  null mean net%    = {100*null_dist.mean():7.2f}")
    print(f"  null std%         = {100*null_dist.std():7.2f}")
    print(f"  null 5th pct      = {100*np.percentile(null_dist, 5):7.2f}")
    print(f"  null 95th pct     = {100*np.percentile(null_dist, 95):7.2f}")
    print(f"  p-value           = {p:.4f}")
    print()
    if real_net2 < null_dist.mean():
        print("  Real result is WORSE than the average random-timing entry with the same")
        print("  exit machinery - the stochastic entry is not adding timing skill here,")
        print("  it is actively picking worse entries than chance would.")
    elif p > 0.05:
        print("  Real result is not statistically distinguishable from random entry timing")
        print("  at the conventional 0.05 threshold - no demonstrated timing skill.")
    else:
        print("  Real result beats random-timing entries at p<0.05 - a real signal, though")
        print("  still net-negative in absolute terms per the construction's own numbers.")


if __name__ == "__main__":
    run()
