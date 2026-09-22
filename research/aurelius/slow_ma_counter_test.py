"""
User's hypothesis: even when Aligned()/PullbackOK()/etc. all pass, if the
SLOWER MAs (150/600/2400) are already converging toward each other AND
sloping against the trade direction, that's a real early-warning the
broader trend is losing steam - Aligned() only checks ORDERING (21>50>150
>600), never the slope or spacing of the slow MAs themselves, so this is
a genuinely different signal than anything already filtered.

Tests two candidate slow-MA pairs (150/600 and 600/2400) x M5/M15, each
as: block when (a) the slower MA's own slope is against the trade AND
(b) the gap between the pair has narrowed below some ATR threshold,
simultaneously - mirroring the exact "pulled together AND pointing
opposite" description.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S


def tail_concentration(trades):
    if not trades:
        return None
    pnl = sorted([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades], reverse=True)
    net = sum(pnl)
    top20 = sum(pnl[:20])
    return dict(net=round(net, 2), top20_pct=round(100 * top20 / net, 1) if net else float("nan"))


def permutation_test(base_trades, candidate_trades, n_draws=2000, seed=0):
    rng = np.random.default_rng(seed)
    k = len(candidate_trades)
    pnl_all = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
    real_net = sum((t["exit_px"] - t["entry_px"]) * t["dir"] for t in candidate_trades)
    if k == 0 or k > len(pnl_all):
        return None
    draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=False)].sum()
                       for _ in range(n_draws)])
    pct = 100 * (draws < real_net).mean()
    return dict(percentile=round(pct, 1), real_net=round(real_net, 2))


def split_stats(trades, n_total, is_frac=0.7):
    cutoff = int(n_total * is_frac)
    is_t = [t for t in trades if t["entry_i"] < cutoff]
    oos_t = [t for t in trades if t["entry_i"] >= cutoff]
    return S.stats(is_t), S.stats(oos_t)


def make_filter(ctx, slow_ma_name, fast_ma_name, slope_bars, min_slope_atr, max_gap_atr):
    slow = ctx[slow_ma_name]; fast = ctx[fast_ma_name]; atr = ctx["atr"]
    n = ctx["n"]
    slope = np.full(n, np.nan)
    slope[slope_bars:] = (slow[slope_bars:] - slow[:-slope_bars]) / atr[slope_bars:]
    gap = np.abs(fast - slow) / atr

    def f(ctx_unused, i, is_buy):
        if np.isnan(slope[i]) or np.isnan(gap[i]) or atr[i] <= 0:
            return True
        counter_slope = (slope[i] < -min_slope_atr) if is_buy else (slope[i] > min_slope_atr)
        narrow = gap[i] < max_gap_atr
        return not (counter_slope and narrow)
    return f


for label, df_fn, params, slope_bars in [("M5", E.load_m5, E.P, 20), ("M15", lambda: E.resample_m15_from_m5(E.load_m5()), E.P15, 20)]:
    df = df_fn(); h4 = E.load_h4()
    ctx = E.build_context(df, h4, params=params)
    n = ctx["n"]
    base_trades = S.simulate(ctx, params=params)
    print(f"=== {label} baseline: {S.stats(base_trades)}")
    print("   tail:", tail_concentration(base_trades))

    for slow_name, fast_name in [("m600", "m150"), ("m2400", "m600")]:
        for min_slope, max_gap in [(0.1, 1.0), (0.2, 1.5), (0.3, 2.0)]:
            filt = make_filter(ctx, slow_name, fast_name, slope_bars, min_slope, max_gap)
            trades = S.simulate(ctx, params=params, extra_filter=filt)
            blocked = len(base_trades) - len(trades)
            st = S.stats(trades)
            print(f"  [{slow_name} vs {fast_name}] slope>={min_slope} gap<{max_gap}: "
                  f"blocked={blocked} n={st['n']} net={st['net']:.2f} pf={st['pf']:.3f} win={st['win_rate']:.3f}")
    print()
