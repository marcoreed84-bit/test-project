"""
Same InpPullbackBars sweep as pullback_bars_sweep_test.py, but on
Aurelius_M15_EA.mq5's own real shipped defaults (engine.P15) - NOT
assumed to share M5's answer. M15 also uses a different pullback MA
(21, not 50) per its own real config.
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


df = E.load_m5()
h4 = E.load_h4()
df15 = E.resample_m15_from_m5(df)

base_ctx = E.build_context(df15, h4, params=E.P15)
n = base_ctx["n"]
base_trades = S.simulate(base_ctx, params=E.P15)
base_stats = S.stats(base_trades)
print("M15 BASELINE pullback_bars=10 (shipped default, pullback_ma=21):", base_stats)
print("  tail:", tail_concentration(base_trades))
print()

results = {}
for pb in [10, 15, 20, 25, 30, 40, 50]:
    params = dict(E.P15, pullback_bars=pb)
    ctx = E.build_context(df15, h4, params=params)
    trades = S.simulate(ctx, params=params)
    st = S.stats(trades)
    results[pb] = (trades, st)
    print(f"pullback_bars={pb}: {st}  tail={tail_concentration(trades)}")

print()
print("--- marginal trades: best plateau candidate vs baseline ---")
best_pb = None
for pb in sorted(results):
    if pb == 10:
        continue
    if results[pb][1]["net"] != results.get(best_pb, (None, {"net": None}))[1]["net"] if best_pb else True:
        pass
best_pb = max([pb for pb in results if pb != 10], key=lambda pb: results[pb][1]["net"])
print(f"best/plateau candidate: pullback_bars={best_pb}")

trades_best = results[best_pb][0]
base_keys = set((t["entry_i"], t["dir"]) for t in base_trades)
new_trades = [t for t in trades_best if (t["entry_i"], t["dir"]) not in base_keys]
pnl = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in new_trades]
wins = [p for p in pnl if p > 0]
losses = [p for p in pnl if p <= 0]
print("newly recovered trades:", len(new_trades))
if pnl:
    print("marginal: net=", round(sum(pnl), 2), "win_rate=", round(len(wins) / len(pnl), 3),
          "avg_win=", round(np.mean(wins), 2) if wins else None,
          "avg_loss=", round(np.mean(losses), 2) if losses else None)

    new_sorted = sorted(new_trades, key=lambda t: t["entry_i"])
    half = len(new_sorted) // 2
    def netsum(ts): return round(sum((t["exit_px"] - t["entry_px"]) * t["dir"] for t in ts), 2)
    print("marginal net, first half chronologically:", netsum(new_sorted[:half]), "n=", half)
    print("marginal net, second half chronologically:", netsum(new_sorted[half:]), "n=", len(new_sorted) - half)

    rng = np.random.default_rng(0)
    real_net = sum(pnl)
    pnl_all = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
    k = len(new_trades)
    draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=True)].sum() for _ in range(2000)])
    pct = 100 * (draws < real_net).mean()
    print("permutation percentile:", round(pct, 1), "null_mean=", round(draws.mean(), 2))
else:
    print("no marginal trades - pullback_bars had no effect on M15")
