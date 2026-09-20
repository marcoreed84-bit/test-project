"""The header's InpRequireConfluence claim (mq5 43-45), re-derived:
  win 65.6->70.2 train, 73.1->76.1 holdout
  PF  1.36 ->1.48 train, 1.84 ->1.81 holdout
  n   554  ->467          maxdd 132.8 -> 121.2

Reported on (a) the full current CSV (2013-01-02 .. 2026-08-19) and (b) the
same run truncated at 2026-05-15, which is the end date at which the header's
own n (554 / 467) reproduces exactly - i.e. the export the claim was made on.
"""
import importlib.util
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


E = _load("engine_slipstream", "engine.py")
S = _load("sim_slipstream", "sim.py")

d, i0 = E.load_h4(start="2013-01-01", warmup_from_full=True)
p = E.params()
ctx = E.build_context(d, p)
n = ctx["n"]
sig = E.base_signals(ctx, p)
s0 = sig[0].copy()
s0[:i0] = 0
sg = (s0, max(sig[1], i0))

CLAIM = {
    ("train", "win"): (65.6, 70.2), ("holdout", "win"): (73.1, 76.1),
    ("train", "pf"): (1.36, 1.48), ("holdout", "pf"): (1.84, 1.81),
}

for intrabar in ("stop_first", "lock_first"):
    for end in (None, "2026-05-15"):
        nb = n if end is None else int(np.searchsorted(ctx["time"], np.datetime64(pd.Timestamp(end))))
        print("=" * 78)
        print(f"intrabar={intrabar}   data end = {end or d['time'].iloc[-1]}")
        rows = {}
        for conf in (False, True):
            tr = [t for t in S.simulate(ctx, p, sig=sg, require_confluence=conf,
                                        intrabar=intrabar) if t["entry_i"] < nb]
            a, b, cut = S.split_stats(tr, i0, nb)
            rows[conf] = (S.stats(tr), a, b)
            tag = "confluence ON " if conf else "confluence OFF"
            print(f"  {tag} full   {S.fmt(rows[conf][0])}")
            print(f"  {tag} train  {S.fmt(a)}")
            print(f"  {tag} hold   {S.fmt(b)}")
        off, on = rows[False], rows[True]
        print(f"  --> DELTA  n {off[0]['n']}->{on[0]['n']} (claim 554->467)   "
              f"maxdd {off[0]['maxdd']}->{on[0]['maxdd']} (claim 132.8->121.2)")
        for idx, name in ((1, "train"), (2, "holdout")):
            print(f"  --> {name:8s} win {off[idx]['win']}->{on[idx]['win']} "
                  f"(claim {CLAIM[(name,'win')][0]}->{CLAIM[(name,'win')][1]})   "
                  f"PF {off[idx]['pf']:.3f}->{on[idx]['pf']:.3f} "
                  f"(claim {CLAIM[(name,'pf')][0]}->{CLAIM[(name,'pf')][1]})")
