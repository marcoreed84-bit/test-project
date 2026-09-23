"""
Step 7: is candidates.py's one PASS real, or one lucky cell?

"keep_prog 5ATR->0.60" (the give-back trail keeps 0.30 of the peak until the
peak reaches 5 ATR, then 0.60) cleared the pre-set bar, but its neighbour
"3ATR->0.50" failed badly (1/4 years), and its 2023/2024 deltas (-5.5 /
+4.6) are noise-sized - the pass rests on 2025/2026 runners, and this file's
own v3.20 meta-finding is that profit here is concentrated in a handful of
trades (top-5 = 107-120% of net in both real 2026 reports). A lever that
only touches trades which ran >= X ATR is exactly the kind a single-sample
sweep can fool. So: a grid around it, same seeds for every cell (so each
cell's delta vs base is paired on the same noise stream), 24 seeds x 4
periods, closed AND M5 mark-to-market equity drawdown.

A cell is only "robust" if its neighbours agree - one good cell in a grid of
mixed signs is not a finding.
"""
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
from functools import partial

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import candidates as C  # noqa: E402
import decompose as D   # noqa: E402
import noise as N       # noqa: E402
import sim as S         # noqa: E402

SEEDS = range(24)
GRID = [(x, k) for x in (4.0, 5.0, 6.0, 8.0) for k in (0.5, 0.6, 0.7)]


def job(args):
    name, x, k, per, a, b, seed = args
    ctx, noise = N.get_ctx()
    ent, slp = noise["atr"]
    p = C.BASE if name == "base" else replace(C.BASE, keep_fn=partial(C.keep_prog, x_atr=x, keep_hi=k))
    q = replace(p, entry_noise=ent, sl_slip=slp, noise_in_atr=True, seed=seed)
    tr, _ = S.simulate(ctx, q, start=pd.Timestamp(a), end=pd.Timestamp(b))
    s = S.stats_of(tr)
    s["eq_dd"] = D.equity_dd(ctx, tr)[0]
    s["n_hit"] = sum(1 for t in tr if (t["peak"] - t["entry"]) * t["dir"] >= x * t["atr"]) if name != "base" else 0
    return (name, x, k, per, seed, s)


if __name__ == "__main__":
    jobs = []
    for per, a, b in C.PERIODS:
        for s in SEEDS:
            jobs.append(("base", 0, 0, per, a, b, s))
            for x, k in GRID:
                jobs.append(("keep", x, k, per, a, b, s))
    with ProcessPoolExecutor(4, initializer=N.get_ctx) as ex:
        out = list(ex.map(job, jobs, chunksize=8))
    rows = [dict(name=n, x=x, k=k, per=per, seed=sd, **s) for n, x, k, per, sd, s in out]
    df = pd.DataFrame(rows)
    base = df[df.name == "base"].set_index(["per", "seed"])
    print("base:", {per: round(base.loc[per].net.mean(), 1) for per, _, _ in C.PERIODS})
    print(f"\n{'cell':<14}" + "".join(f"{per:>22}" for per, _, _ in C.PERIODS) + "   total   eqDD(sum)  n_hit/yr")
    for x, k in GRID:
        g = df[(df.name == "keep") & (df.x == x) & (df.k == k)].set_index(["per", "seed"])
        cells, tot, eqd = [], 0.0, 0.0
        for per, _, _ in C.PERIODS:
            d = (g.loc[per].net - base.loc[per].net)
            se = d.std() / np.sqrt(len(d))
            cells.append(f"{d.mean():+7.1f} (se {se:4.1f})")
            tot += d.mean()
            eqd += (g.loc[per].eq_dd - base.loc[per].eq_dd).mean()
        print(f"{x:>3.0f}ATR->{k:.2f}  " + "".join(f"{c:>22}" for c in cells)
              + f"  {tot:+7.1f}   {eqd:+7.1f}   {g.n_hit.mean():5.1f}")
