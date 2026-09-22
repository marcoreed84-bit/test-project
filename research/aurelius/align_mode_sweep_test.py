"""
InpAlignMode sweep on Aurelius's real gate (PRICE/FAST/MID/FULL), M5 and
M15 separately - prompted by the user's own observation from a real live
chart ("the alignment was not correct, hence I think we are missing other
trades that would have actually made overall more profit"). MID is the
real shipped default on both files; PRICE/FAST are progressively looser,
FULL is stricter.
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


def marginal_vs_base(base_trades, cand_trades, label):
    base_keys = set((t["entry_i"], t["dir"]) for t in base_trades)
    new_trades = [t for t in cand_trades if (t["entry_i"], t["dir"]) not in base_keys]
    lost_trades = [t for t in base_trades if (t["entry_i"], t["dir"]) not in
                   set((t2["entry_i"], t2["dir"]) for t2 in cand_trades)]
    pnl = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in new_trades]
    wins = [p for p in pnl if p > 0]
    print(f"  [{label}] new={len(new_trades)} lost={len(lost_trades)}", end="")
    if pnl:
        print(f"  marginal_net={sum(pnl):.2f} marginal_winrate={len(wins)/len(pnl):.3f}", end="")
        rng = np.random.default_rng(0)
        pnl_all = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
        k = len(new_trades)
        draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=True)].sum() for _ in range(2000)])
        pct = 100 * (draws < sum(pnl)).mean()
        print(f"  perm_pct={pct:.1f}")
    else:
        print()


df = E.load_m5()
h4 = E.load_h4()
df15 = E.resample_m15_from_m5(df)

for label, dfx, base_params in [("M5", df, E.P), ("M15", df15, E.P15)]:
    print(f"=== {label} ===")
    base_ctx = E.build_context(dfx, h4, params=base_params)
    base_trades = S.simulate(base_ctx, params=base_params)
    print("MID (shipped default):", S.stats(base_trades), tail_concentration(base_trades))
    for mode in ["FULL", "FAST", "PRICE"]:
        params = dict(base_params, align_mode=mode)
        ctx = E.build_context(dfx, h4, params=params)
        trades = S.simulate(ctx, params=params)
        print(f"{mode}:", S.stats(trades), tail_concentration(trades))
        marginal_vs_base(base_trades, trades, mode)
    print()
