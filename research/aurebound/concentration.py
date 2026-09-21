"""How concentrated is the baseline's positive net?

The 2013+ baseline nets +$460 over 13.6 years, but the by-year table shows
2026 (a PARTIAL year, 973 bars to 2026-08-19) contributing +$928 on its own.
This quantifies that, because a net that lives in one recent partial year is
not a result you can size up on.

Also runs ONE narrowly-scoped diagnostic: Slipstream_EA.mq5's header states,
with real numbers, that adding a breakeven-snap stage made it unprofitable.
AuRebound HAS such a stage (mq5 1240-1248: first bar whose close clears the
BB midline in the trade's favour -> SL := entryPx).  This asks the same
question of AuRebound.  It is a single-variable probe, NOT a validated
improvement, and nothing is shipped from it.
"""
import importlib.util
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


aeng = _load("aurebound_engine", "engine.py")
asim = _load("aurebound_sim", "sim.py")

p = aeng.params()
d, _ = aeng.load_h4(start=None)
ctx = aeng.build_context(d, p)
ft = aeng.first_tradable(ctx, p)
n = len(d)
i13 = max(ft, int(np.searchsorted(d["time"].values, np.datetime64(pd.Timestamp("2013-01-01")))))
i18 = max(ft, int(np.searchsorted(d["time"].values, np.datetime64(pd.Timestamp("2018-01-01")))))

for lbl, i0 in (("2013+", i13), ("2018+", i18)):
    tr = asim.simulate(ctx, p, i0=i0, intrabar="stop_first")
    pnl = np.array([t["pnl"] for t in tr])
    net = pnl.sum()
    ex26 = [t for t in tr if t["year"] < 2026]
    top5 = np.sort(pnl)[-5:].sum()
    print(f"{lbl}: net=${net:.2f} | excluding 2026: {asim.fmt(asim.stats(ex26))}")
    print(f"       top-5 trades alone = ${top5:.2f} "
          f"({100*top5/net:.0f}% of net) | 2026 = ${net - sum(t['pnl'] for t in ex26):.2f}")

print("\n--- single-variable probe: disable the stage2 breakeven snap --------")
print("    (TESTED, NOT CONFIRMED - one variable, no sweep, nothing shipped)")

# monkeypatch-free variant: re-run with MFELockFrac unchanged but stage2 never
# arming.  Implemented by copying simulate()'s loop with the stage2 branch off.
src = open(os.path.join(HERE, "sim.py")).read()
src_nobe = src.replace("            if not stage2 and not np.isnan(mid[i]):",
                       "            if False and not stage2 and not np.isnan(mid[i]):")
assert src_nobe != src
ns = {"__name__": "aurebound_sim_nobe", "__file__": os.path.join(HERE, "sim.py")}
exec(compile(src_nobe, os.path.join(HERE, "sim.py"), "exec"), ns)

for lbl, i0 in (("2013+", i13), ("2018+", i18)):
    tr = ns["simulate"](ctx, p, i0=i0, intrabar="stop_first")
    tri, tro, _ = ns["split_stats"](tr, i0, n, 0.7)
    print(f"  no-breakeven {lbl} full    {asim.fmt(asim.stats(tr))}")
    print(f"               {lbl} train   {asim.fmt(tri)}")
    print(f"               {lbl} holdout {asim.fmt(tro)}")
    print(f"               {lbl} exits   {asim.reason_breakdown(tr)}")
