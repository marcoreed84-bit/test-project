"""Baseline run of the AuRebound replica at the TRUE SHIPPED DEFAULTS.

AuRebound_EA.mq5's header carries NO numeric backtest claim (unlike
Slipstream_EA.mq5 / Tailwind_EA.mq5), so there is nothing to validate
against - this establishes what the shipped configuration actually does,
as new information.

DATA CAVEATS found in GOLD_H4.csv itself (bars/year, mean spread/year):
  2001-2012 : ~260 bars/year  -> that is DAILY density, not H4. Not real H4
              data; any result over that span is not an H4 backtest.
  2013      : 1096 bars       -> partial year.
  2014-2026 : ~1540 bars/year -> real H4 density.
  spread column is EXACTLY 0.00 for every bar before 2018 -> the 2013-2017
              stretch is effectively cost-free and flatters any result.
  2018-2026 : mean spread 13-21 points ($0.13-$0.21) -> the only stretch
              where the modelled entry cost is a real cost.
So three windows are reported, with 2013+ as the headline (it is the session
standard used for Slipstream) and 2018+ flagged as the cost-realistic one.
"""
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

p = aeng.params()
d_all, _ = aeng.load_h4(start=None)
ctx = aeng.build_context(d_all, p)
ft = aeng.first_tradable(ctx, p)
n = len(d_all)

print("=" * 82)
print("AuRebound_EA.mq5 replica - SHIPPED DEFAULTS, single-position sequential sim")
print(f"data: {d_all['time'].iloc[0]} .. {d_all['time'].iloc[-1]}  ({n} H4 bars)")
print("intrabar=stop_first is EXACT here (the stop only moves at a bar boundary)")
print("=" * 82)

for label, start in (("2013+  (session standard)", "2013-01-01"),
                     ("2018+  (real spread only)", "2018-01-01"),
                     ("full   (incl. daily-density pre-2013)", None)):
    i0 = ft if start is None else max(
        ft, int(np.searchsorted(d_all["time"].values,
                                np.datetime64(__import__("pandas").Timestamp(start)))))
    tr = asim.simulate(ctx, p, i0=i0, intrabar="stop_first")
    full = asim.stats(tr)
    tri, tro, cut = asim.split_stats(tr, i0, n, 0.7)
    print(f"\n### {label}")
    print(f"    window bar {i0} ({d_all['time'].iloc[i0]}) .. {n-1}; "
          f"70/30 split at {d_all['time'].iloc[cut]}")
    print(f"    full    {asim.fmt(full)}")
    print(f"    train   {asim.fmt(tri)}")
    print(f"    holdout {asim.fmt(tro)}")
    print(f"    exits   {asim.reason_breakdown(tr)}")
    print(f"    L/S {sum(1 for t in tr if t['dir']>0)}/"
          f"{sum(1 for t in tr if t['dir']<0)}  "
          f"avg bars held {np.mean([t['bars'] for t in tr]):.1f}")

# counterfactual only - AuRebound does NOT trail intrabar
i0 = max(ft, int(np.searchsorted(
    d_all["time"].values, np.datetime64(__import__("pandas").Timestamp("2013-01-01")))))
tr2 = asim.simulate(ctx, p, i0=i0, intrabar="lock_first")
print(f"\n[counterfactual, NOT the shipped behaviour - 'what if it trailed "
      f"intrabar like Slipstream': 2013+ {asim.fmt(asim.stats(tr2))}]")

tr = asim.simulate(ctx, p, i0=i0, intrabar="stop_first")
print("\nby year (2013+): " + ", ".join(
    f"{y}:{v[0]}/{v[1]:+.0f}" for y, v in asim.year_breakdown(tr).items()))
