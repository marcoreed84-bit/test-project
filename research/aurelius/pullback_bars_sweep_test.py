"""
Real test of widening InpPullbackBars (Aurelius_EA.mq5 default=10, M5) -
prompted directly by the user pointing at a real live chart where price
touched/closed above the 50-EMA and rolled back down into a clean
continuation, but the EA's own panel showed pullback=no because the touch
had already scrolled outside the 10-bar (50-minute) lookback window by the
time the continuation was confirmed.

Rigor matches this project's standing rule for testing a changed parameter:
chronological 70/30 IS/OOS split, tail-concentration check, and a
permutation-null control drawn from the BASE model's own entered trades.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S


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
    top20 = sum(pnl[:20])
    return dict(net=round(net, 2), top20_pct=round(100 * top20 / net, 1) if net else float("nan"))


def permutation_test(base_trades, candidate_trades, n_draws=800, seed=0):
    rng = np.random.default_rng(seed)
    k = len(candidate_trades)
    pnl_all = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
    real_net = sum((t["exit_px"] - t["entry_px"]) * t["dir"] for t in candidate_trades)
    if k == 0 or k > len(pnl_all):
        return None
    draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=False)].sum()
                       for _ in range(n_draws)])
    pct = 100 * (draws < real_net).mean()
    return dict(percentile=round(pct, 1), real_net=round(real_net, 2),
                null_mean=round(draws.mean(), 2))


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()

    base_ctx = E.build_context(df, h4, params=E.P)
    n = base_ctx["n"]
    base_trades = S.simulate(base_ctx, params=E.P)
    base_stats = S.stats(base_trades)
    base_risk = S.risk_stats(base_trades, base_ctx)
    print("BASELINE pullback_bars=10 (shipped default):", base_stats)
    print("  risk:", base_risk)
    print("  tail:", tail_concentration(base_trades))
    print()

    results = {}
    for pb in [10, 15, 20, 25, 30, 40, 50, 75, 100]:
        params = dict(E.P, pullback_bars=pb)
        ctx = E.build_context(df, h4, params=params)
        trades = S.simulate(ctx, params=params)
        st = S.stats(trades)
        risk = S.risk_stats(trades, ctx)
        results[pb] = (trades, st, risk)
        print(f"pullback_bars={pb}: {st}  |  closedDD={risk.get('closed_dd_pct')}  floatDD={risk.get('float_dd_pct')}")

    print()
    print("--- IS/OOS (70/30 chronological) for each ---")
    for pb, (trades, st, risk) in results.items():
        is_s, oos_s = split_stats(trades, n)
        print(f"pb={pb}: IS={is_s}  OOS={oos_s}")

    print()
    print("--- tail concentration ---")
    for pb, (trades, st, risk) in results.items():
        print(f"pb={pb}:", tail_concentration(trades))

    print()
    print("--- permutation test vs baseline's own trade population ---")
    for pb, (trades, st, risk) in results.items():
        if pb == 10:
            continue
        perm = permutation_test(base_trades, trades, n_draws=800)
        print(f"pb={pb} vs baseline:", perm)
