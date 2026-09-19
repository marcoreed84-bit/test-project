"""
S&R touch-and-reject filter test on Aurelius's real M5 gate (v1.46 true
shipped defaults, engine.P) - the user's pending "test it on aurelius
aswell" request from the Ichimoku thread, applied here with the same
construction: does the entry get preceded by a real touch-and-reject of
the relevant prior-3-day S&R level, not just occur at some distance from
one (which InpUseSRDist already tests, in the opposite direction - it
requires distance AWAY from a level; this tests for a recent BOUNCE off
one instead).

FIXED (Opus audit caught this): originally used the WRONG side of the
level - sr_lo for buys, sr_hi for sells. SRDistanceATR() (Aurelius_EA.mq5
~2029) does the opposite: a buy's relevant level is the resistance
(prior 3-day HIGH, since a confirmed-uptrend pullback entry sits above a
prior high it broke through - a breakout/retest pattern), a sell's is the
support (prior 3-day LOW). The bug made the "touch" condition nearly
impossible (comparing an uptrend entry's recent lows against the 3-day
LOW instead of the 3-day HIGH it had already broken above), producing a
false "structurally never happens" result - the first run found 0/971
entries ever within 1.0 ATR of the (wrong) level; the corrected level
puts ~26.6% of entries within 1.0 ATR, a real, testable population.

Rigor matches this project's standing rule: chronological 70/30 IS/OOS
split, tail-concentration check (top-5 trades / negative years), and a
permutation-null control drawn from the BASE model's own entered trades
(not raw signal bars) - the stricter null for testing whether an ADDED
filter provides value beyond the already-real base gate.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S

LOOKBACK_BARS = 12      # ~1h on M5 - how far back to look for the touch
TOUCH_TOL_ATR = 0.30    # how close to the level counts as "touched"
REJECT_ATR = 0.30       # how far back away from the level by entry counts as "rejected"


def make_sr_reject_filter(ctx):
    atr = ctx["atr"]
    low, high, close = ctx["low"], ctx["high"], ctx["close"]
    sr_hi_level, sr_lo_level = ctx["sr_hi"], ctx["sr_lo"]

    def touched_and_rejected(ctx_unused, i, is_buy):
        if np.isnan(atr[i]) or atr[i] <= 0:
            return False
        tol = TOUCH_TOL_ATR * atr[i]
        rej = REJECT_ATR * atr[i]
        lvl = sr_hi_level[i] if is_buy else sr_lo_level[i]
        if np.isnan(lvl):
            return False
        touched = False
        for j in range(max(0, i - LOOKBACK_BARS + 1), i + 1):
            if is_buy and low[j] <= lvl + tol:
                touched = True
                break
            if (not is_buy) and high[j] >= lvl - tol:
                touched = True
                break
        if not touched:
            return False
        return (close[i] - lvl >= rej) if is_buy else (lvl - close[i] >= rej)

    return touched_and_rejected


def split_stats(trades, n_total, is_frac=0.7):
    if not trades:
        return None
    cutoff = int(n_total * is_frac)
    is_t = [t for t in trades if t["entry_i"] < cutoff]
    oos_t = [t for t in trades if t["entry_i"] >= cutoff]
    return S.stats(is_t), S.stats(oos_t)


def tail_concentration(trades):
    if not trades:
        return None
    pnl = sorted([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades], reverse=True)
    net = sum(pnl)
    top5 = sum(pnl[:5])
    return dict(net=net, top5_pct=100 * top5 / net if net else float("nan"),
                ex_top5_net=net - top5)


def permutation_test(base_trades, candidate_trades, n_draws=800, seed=0):
    """Null: random same-size subsets of the BASE model's own trades (not
    fresh random entries) - tests whether the filtered subset beats a random
    equal-size subset of the same underlying trade population."""
    rng = np.random.default_rng(seed)
    k = len(candidate_trades)
    pnl_all = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
    real_net = sum((t["exit_px"] - t["entry_px"]) * t["dir"] for t in candidate_trades)
    if k == 0 or k > len(pnl_all):
        return None
    draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=False)].sum()
                       for _ in range(n_draws)])
    pct = 100 * (draws < real_net).mean()
    return dict(percentile=pct, real_net=real_net, null_mean=draws.mean(), null_std=draws.std())


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4)
    n = ctx["n"]

    base_trades = S.simulate(ctx, params=E.P)
    base_stats = S.stats(base_trades)
    print("BASELINE (v1.46 true defaults, full 2023-2026):", base_stats)

    filt = make_sr_reject_filter(ctx)
    cand_trades = S.simulate(ctx, params=E.P, extra_filter=filt)
    cand_stats = S.stats(cand_trades)
    print("CANDIDATE (+ S&R touch-and-reject):", cand_stats)

    print()
    print("--- IS/OOS (70/30 chronological) ---")
    b_is, b_oos = split_stats(base_trades, n)
    c_is, c_oos = split_stats(cand_trades, n)
    print("baseline IS:", b_is, "OOS:", b_oos)
    print("candidate IS:", c_is, "OOS:", c_oos)

    print()
    print("--- tail concentration ---")
    print("baseline:", tail_concentration(base_trades))
    print("candidate:", tail_concentration(cand_trades))

    print()
    print("--- permutation test (candidate's trades vs random same-size draws from baseline's own trades) ---")
    perm = permutation_test(base_trades, cand_trades, n_draws=800)
    print(perm)
