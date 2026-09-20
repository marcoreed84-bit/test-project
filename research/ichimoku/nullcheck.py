"""Does the header's 97.6th percentile survive? It depends entirely on WHICH
null. Build both and compare."""
import numpy as np, engine as E, sim as S
d = E.load_h4("2013-01-01")
BASE_P = E.params(entry_mode="PLAIN", use_adx=False, min_hold_bars=8, safety_stop_atr=2.5)
BEST_P = E.P_BEST_PLAIN_ADX
ctx = E.build_context(d, BEST_P)
base = S.simulate(ctx, BASE_P); best = S.simulate(ctx, BEST_P)

def bar_level_null(ctx, real_trades, pool_mask, n_draws=2000, seed=0):
    """Header's described null: 'matched-count/direction/holding-time null drawn
    from real TK-cross bars'. Pick random bars from the TK-cross pool, keep the
    real trades' direction + holding-time multiset, price entry/exit off open[]."""
    rng = np.random.default_rng(seed)
    o = ctx["open"]; n = ctx["n"]
    pool = np.flatnonzero(pool_mask)
    dirs = np.array([t["dir"] for t in real_trades])
    holds = np.array([t["exit_i"]-t["entry_i"] for t in real_trades])
    real_net = sum(t["pnl"] for t in real_trades)
    draws = np.empty(n_draws)
    for k in range(n_draws):
        idx = rng.choice(pool, len(dirs), replace=True)
        ex = np.minimum(idx + holds, n-1)
        draws[k] = ((o[ex]-o[idx])*dirs).sum()
    return dict(percentile=round(100*(draws<real_net).mean(),1), real_net=round(real_net,2),
                null_mean=round(draws.mean(),2), null_std=round(draws.std(),2))

tk, kj = ctx["tenkan"], ctx["kijun"]
import pandas as pd
tkp, kjp = pd.Series(tk).shift(1).values, pd.Series(kj).shift(1).values
cross = np.nan_to_num(((tk>kj)&(tkp<=kjp))|((tk<kj)&(tkp>=kjp)), nan=0).astype(bool)
cross[:200] = False
print("TK-cross bars in pool:", int(cross.sum()))
print("\nPLAIN+ADX vs BAR-LEVEL null (header's description):")
print("  ", bar_level_null(ctx, best, cross))
print("PLAIN(no ADX) vs same BAR-LEVEL null (is the BASE already 'significant' here?):")
print("  ", bar_level_null(ctx, base, cross))
print("\nPLAIN+ADX vs TRADE-SUBSET null (project's later, stricter 'beats the base signal' null):")
print("  ", S.permutation_test(base, best, n_draws=4000))
