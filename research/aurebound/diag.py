"""Diagnostics on the AuRebound replica: signal counts, stop-distance
distribution, how often each exit-ladder stage is actually reached."""
import importlib.util
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


aeng = _load("aurebound_engine", "engine.py")
asim = _load("aurebound_sim", "sim.py")

d, i0 = aeng.load_h4(start="2013-01-01")
p = aeng.params()
ctx = aeng.build_context(d, p)
i0 = max(i0, aeng.first_tradable(ctx, p))
n = len(d)

# ---- raw signal census (NOT a tradeable count - no single-position gate) ---
raw = np.zeros(n, int)
for i in range(i0 - 1, n - 1):
    raw[i] = aeng.raw_signal(ctx, i, p)
print(f"raw signal bars in window : long={int((raw>0).sum())} "
      f"short={int((raw<0).sum())} total={int((raw!=0).sum())} "
      f"of {n-i0} bars ({100*(raw!=0).sum()/(n-i0):.1f}%)")

# what each filter costs
lb, mode = p["Lookback"], p["StochMode"]
tu = aeng.turn_up_vec(ctx, mode)
td = aeng.turn_dn_vec(ctx, mode)
rl = np.zeros(n, bool); ru = np.zeros(n, bool)
for k in range(lb + 1):
    rl[k:] |= ctx["near_lo"][:n - k] if k else ctx["near_lo"]
    ru[k:] |= ctx["near_up"][:n - k] if k else ctx["near_up"]
w = slice(i0, n - 1)
ls, ss = rl[w] & tu[w], ru[w] & td[w]
print(f"  pre-filter            : long={ls.sum()} short={ss.sum()} "
      f"ambiguous(both)={(ls & ss).sum()}")
hr, dw = ctx["hour"][w], ctx["dow"][w]
print(f"  killed by hour==8     : {((ls | ss) & (hr == 8)).sum()}")
print(f"  killed by Fri>=16     : {((ls | ss) & (dw == 4) & (hr >= 16)).sum()}")

# ---- the actual sequential run -------------------------------------------
tr = asim.simulate(ctx, p, i0=i0, intrabar="stop_first")
print(f"\ntrades actually taken     : {len(tr)}  "
      f"({100*len(tr)/max(1,int((raw!=0).sum())):.0f}% of raw signal bars - "
      f"the rest are blocked by the single-position gate + cooldown)")

sl = np.array([abs(t["entry"] - 0) for t in tr])
dist = []
for t in tr:
    i = t["entry_i"] - 1
    a = ctx["atr"][i]
    px = ctx["o"][t["entry_i"]] + (ctx["spread"][t["entry_i"]] if t["dir"] > 0 else 0)
    sd, _ = aeng.compute_sl_dist(ctx, i, t["dir"], px, p)
    dist.append(sd / a)
dist = np.array(dist)
print(f"stopDist / entryATR       : mean={dist.mean():.3f} "
      f"median={np.median(dist):.3f} min={dist.min():.3f} "
      f"| capped at 1.5x on {100*(dist >= 1.4999).mean():.1f}% of entries")

bars = np.array([t["bars"] for t in tr])
print(f"bars held                 : mean={bars.mean():.2f} median={np.median(bars):.0f} "
      f"p90={np.percentile(bars,90):.0f} max={bars.max()}")
print(f"exit reasons              : {asim.reason_breakdown(tr)}")

pnl = np.array([t["pnl"] for t in tr])
atrs = np.array([ctx["atr"][t["entry_i"] - 1] for t in tr])
print(f"pnl in R (R=entryATR)     : mean={np.mean(pnl/atrs):.4f} "
      f"winners_mean={np.mean((pnl/atrs)[pnl>0]):.3f} "
      f"losers_mean={np.mean((pnl/atrs)[pnl<=0]):.3f}")
print(f"  -> winners cluster at the 0.70*bestFav MFE lock, losers at the "
      f"1.5*ATR cap: a ~0.7R : ~1.4R payoff needing >66% wins to break even, "
      f"observed win rate {100*(pnl>0).mean():.1f}%")

# how often each ladder stage is reached at all
st2 = 0
for t in tr:
    e = t["entry_i"]
    hit = False
    for j in range(e, t["exit_i"] + 1):
        i = j - 1
        if i < e:
            continue
        m = ctx["bb_mid"][i]
        if not np.isnan(m) and ((ctx["c"][i] > m) if t["dir"] > 0 else (ctx["c"][i] < m)):
            hit = True
            break
    st2 += hit
print(f"\nstage2 (breakeven snap) reached on {st2}/{len(tr)} trades "
      f"({100*st2/len(tr):.1f}%)")
print("band-reject is gated behind stage2, which is why it fires so rarely.")
