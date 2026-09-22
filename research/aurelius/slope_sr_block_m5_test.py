"""
InpUseSlopeSRBlock on Aurelius M5 - the M15 file (v1.51) shipped this ON
by default after a real, permutation-confirmed Python finding there; NOT
assumed to transfer to M5 (same discipline as every other cross-timeframe
question this session - each file gets its own real test).
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
    return dict(percentile=round(pct, 1), real_net=round(real_net, 2), null_mean=round(draws.mean(), 2))


df = E.load_m5(); h4 = E.load_h4()
ctx = E.build_context(df, h4, params=E.P)
n = ctx["n"]

base_trades = S.simulate(ctx, params=E.P)
base_stats = S.stats(base_trades)
print("BASELINE (M5, no slope+SR block):", base_stats)
print("  tail:", tail_concentration(base_trades))
print()

# same real thresholds M15 shipped with, then a small sweep
for slope_th, sr_th in [(1.00, 6.00), (0.8, 5.0), (1.2, 7.0), (0.6, 4.0), (1.5, 8.0)]:
    params = dict(E.P, use_slope_sr_block=True, slope_sr_block_slope=slope_th, slope_sr_block_sr=sr_th)
    trades = S.simulate(ctx, params=params)
    st = S.stats(trades)
    blocked = len(base_trades) - len(trades)
    print(f"slope>={slope_th} & sr>={sr_th}: {st}  (blocked {blocked} of {len(base_trades)})")
    print("  tail:", tail_concentration(trades))

print()
print("--- deep dive on the real M15 default (1.00 / 6.00) ---")
params = dict(E.P, use_slope_sr_block=True, slope_sr_block_slope=1.00, slope_sr_block_sr=6.00)
cand_trades = S.simulate(ctx, params=params)
b_is, b_oos = split_stats(base_trades, n)
c_is, c_oos = split_stats(cand_trades, n)
print("baseline IS:", b_is)
print("baseline OOS:", b_oos)
print("candidate IS:", c_is)
print("candidate OOS:", c_oos)
perm = permutation_test(base_trades, cand_trades)
print("permutation (removed trades vs random same-size removal):", perm)

# what got blocked - were they actually bad trades?
base_keys = {(t["entry_i"], t["dir"]): t for t in base_trades}
cand_keys = {(t["entry_i"], t["dir"]) for t in cand_trades}
removed = [t for k, t in base_keys.items() if k not in cand_keys]
pnl_removed = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in removed]
wins = [p for p in pnl_removed if p > 0]
print(f"removed trades: n={len(removed)}, net={sum(pnl_removed):.2f}, win_rate={len(wins)/len(removed):.3f}" if removed else "removed: none")
