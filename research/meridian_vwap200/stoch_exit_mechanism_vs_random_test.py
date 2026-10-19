"""
Direct request: "test the exit mechanism itself against random timing."
Different question from every prior null test tonight - those fixed the
EXIT machinery and randomized WHEN you enter. This one does the
opposite: keeps the REAL entries (actual stochastic signal bars, same
direction, same count) and asks whether the ENGINEERED exit (swing
stop + fixed 1:2 R:R target + opposite-cross exit, stop/target
enforced every bar) is adding value over just holding for a random
duration and closing out - or whether the exit logic itself is what's
destroying the edge (stops too tight for noise, target cut short by
the opposite-cross exit before it's reached, etc).

Method: for each REAL entry (same bar, same direction as the real
trade), draw a random hold_bars value from the REAL trades' own
hold_bars distribution (shuffled, same real spread cost both legs) and
exit flat after that many bars - no stop, no target, no opposite-cross
rule. Same number of trades, same entries, same average holding time
as the real construction - the ONLY thing varied is whether the exit
is the engineered rule or a random-duration flat close.

If the real engineered exit does BETTER than this random-duration
exit, the exit logic is adding value (even if the overall system is
still a net loser - entries alone might just be worse). If real does
NO BETTER or WORSE, the exit mechanism itself is actively hurting
performance, not helping, which is itself an actionable finding
independent of the entry-timing question already tested tonight.

Tested on BTCUSD M15 (21,5,5, 20/80 - this project's most-cited,
already-established construction) and GOLD M15 (14,3,3, 20/80 - one of
the configs from the 9-combo table). Honest K=2 for
this new exit-mechanism check (does not add to the entry-timing null
tests already run on these same configs - genuinely different
question).
"""
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "vwap_open"))
from classic_stoch_14_3_3_test import stochastic_lowhigh_sma
from stoch_table_claims_verify_test import load, build_trades, SWING_BARS, RR, TIME_CAP_BARS

N_DRAWS = 1000


def build_trades_random_exit(df, point, k_period, slowing, d_period, zone_low, zone_high,
                              hold_bars_pool, rng):
    """Same entries as build_trades(), but exit flat after a random
    hold_bars (drawn from hold_bars_pool, shuffled) - no stop/target/
    opposite-cross rule at all."""
    close_a, high_a, low_a = df["close"].values, df["high"].values, df["low"].values
    spread_a = df["spread"].values
    n = len(df)
    k_a, d_a = stochastic_lowhigh_sma(high_a, low_a, close_a, k_period, slowing, d_period)

    close, spread = close_a.tolist(), spread_a.tolist()
    k, d = k_a.tolist(), d_a.tolist()
    valid = (~(np.isnan(k_a) | np.isnan(d_a))).tolist()
    crossUp = [False] * n
    crossDown = [False] * n
    for i in range(1, n):
        if valid[i] and valid[i - 1]:
            crossUp[i] = k[i - 1] <= d[i - 1] and k[i] > d[i]
            crossDown[i] = k[i - 1] >= d[i - 1] and k[i] < d[i]

    hold_pool = list(hold_bars_pool)
    rng.shuffle(hold_pool)
    pool_i = 0

    total = 0.0
    taken = 0
    start = k_period + slowing + d_period + SWING_BARS + 5
    i = start
    while i < n - 1:
        if not valid[i]:
            i += 1
            continue
        dir_ = 0
        if crossUp[i] and k[i] < zone_low:
            dir_ = 1
        elif crossDown[i] and k[i] > zone_high:
            dir_ = -1
        if dir_ == 0:
            i += 1
            continue

        swing = min(low_a.tolist()[i - SWING_BARS:i]) if dir_ > 0 else max(high_a.tolist()[i - SWING_BARS:i])
        risk = dir_ * (close[i] - swing)
        if risk <= 0.0:
            i += 1
            continue
        fill_i = i + 1
        if fill_i >= n:
            i += 1
            continue
        sc = spread[fill_i] * point
        entry_px = close[fill_i] + (sc if dir_ > 0 else -sc)

        hb = hold_pool[pool_i % len(hold_pool)]
        pool_i += 1
        exit_i = min(fill_i + max(hb, 1), n - 1)
        scj = spread[exit_i] * point
        exit_px = close[exit_i] - (scj if dir_ > 0 else -scj)

        total += ((exit_px - entry_px) / entry_px) * dir_
        taken += 1
        i = exit_i + 1

    return total, taken


def run_config(label, symbol_file, trim_gold, k_period, slowing, d_period, zone_low, zone_high):
    df, point = load(symbol_file, trim_gold=trim_gold)
    real_trades = build_trades(df, point, k_period, slowing, d_period, zone_low, zone_high)
    real_net = sum(t["pnl_pct"] for t in real_trades)
    hold_bars_real = np.array([t["hold_bars"] for t in real_trades])

    print(f"\n{'#'*100}\n{label}\n{'#'*100}")
    print(f"  REAL (engineered exit): n={len(real_trades)}  net%={100*real_net:.2f}  "
          f"mean hold={hold_bars_real.mean():.1f} bars")

    rng = np.random.default_rng(0)
    draw_nets = []
    draw_ns = []
    for _ in range(N_DRAWS):
        net, taken = build_trades_random_exit(df, point, k_period, slowing, d_period,
                                               zone_low, zone_high, hold_bars_real, rng)
        draw_nets.append(net)
        draw_ns.append(taken)
    draw_nets = np.array(draw_nets)

    print(f"  RANDOM-DURATION exit (same entries, same avg hold, {N_DRAWS} draws):")
    print(f"    mean net%  = {100*draw_nets.mean():8.2f}")
    print(f"    std%       = {100*draw_nets.std():8.2f}")
    print(f"    5th pct    = {100*np.percentile(draw_nets, 5):8.2f}")
    print(f"    95th pct   = {100*np.percentile(draw_nets, 95):8.2f}")
    p = (np.sum(draw_nets >= real_net) + 1) / (N_DRAWS + 1)
    print(f"    p-value (real >= random-exit) = {p:.4f}")

    if real_net > draw_nets.mean() and p < 0.05:
        verdict = "Engineered exit BEATS random-duration exit - the exit logic is adding real value"
    elif real_net < draw_nets.mean():
        verdict = "Engineered exit is WORSE than just holding for a random matched duration - the exit mechanism is actively hurting performance, not helping"
    else:
        verdict = "No meaningful difference - the exit mechanism isn't adding or subtracting much vs a naive random-duration close"
    print(f"  -> {verdict}")
    return real_net, draw_nets, p, verdict


if __name__ == "__main__":
    run_config("BTCUSD M15 (21,5,5, 20/80) - engineered exit vs random-duration exit",
               "BTCUSD_M15_native.csv", False, 21, 5, 5, 20.0, 80.0)
    run_config("GOLD M15 (14,3,3, 20/80) - engineered exit vs random-duration exit",
               "GOLD_M15_native.csv", True, 14, 3, 3, 20.0, 80.0)
    print(f"\n\n  Honest K=2 (new exit-mechanism question, not counted against the")
    print(f"  entry-timing null lines already run on these configs).")
