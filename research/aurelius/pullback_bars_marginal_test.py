import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S

df = E.load_m5()
h4 = E.load_h4()

base_ctx = E.build_context(df, h4, params=E.P)
n = base_ctx["n"]
base_trades = S.simulate(base_ctx, params=E.P)

params20 = dict(E.P, pullback_bars=20)
ctx20 = E.build_context(df, h4, params=params20)
trades20 = S.simulate(ctx20, params=params20)

base_keys = set((t["entry_i"], t["dir"]) for t in base_trades)
new_trades = [t for t in trades20 if (t["entry_i"], t["dir"]) not in base_keys]

print("baseline trades:", len(base_trades))
print("pb=20 trades:", len(trades20))
print("newly recovered trades (in pb=20, not in baseline):", len(new_trades))

pnl = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in new_trades]
wins = [p for p in pnl if p > 0]
losses = [p for p in pnl if p <= 0]
print("marginal trades: net=", round(sum(pnl), 2), "win_rate=", round(len(wins)/len(pnl), 3) if pnl else None,
      "avg_win=", round(np.mean(wins), 2) if wins else None, "avg_loss=", round(np.mean(losses), 2) if losses else None)

# chronological split of the marginal trades to check it's not one lucky cluster
new_trades_sorted = sorted(new_trades, key=lambda t: t["entry_i"])
half = len(new_trades_sorted)//2
first_half = new_trades_sorted[:half]; second_half = new_trades_sorted[half:]
def netsum(ts): return round(sum((t["exit_px"]-t["entry_px"])*t["dir"] for t in ts), 2)
print("marginal trades net, first half chronologically:", netsum(first_half), "n=",len(first_half))
print("marginal trades net, second half chronologically:", netsum(second_half), "n=",len(second_half))

# permutation: are these 54 marginal trades better than 54 random bars where
# alignment/slope/cross/volume/sr all passed but pullback specifically was the
# only thing failing (the real comparable population - not just "any bar")
rng = np.random.default_rng(0)
real_net = sum(pnl)
# candidate pool: use baseline's own trades as the null population (same logic
# as elsewhere) sampling WITH replacement since new_trades can exceed base n only if k>n; here it's fine
pnl_all = np.array([(t["exit_px"] - t["entry_px"]) * t["dir"] for t in base_trades])
k = len(new_trades)
draws = np.array([pnl_all[rng.choice(len(pnl_all), size=k, replace=True)].sum() for _ in range(2000)])
pct = 100*(draws < real_net).mean()
print("permutation (marginal trades' net vs random same-size WITH-replacement draws from baseline pop):",
      "percentile=", round(pct,1), "null_mean=", round(draws.mean(),2))
