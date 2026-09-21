"""Why doesn't the replica hit the header's n=835 / PF=1.29 / net=$1959?

Scans the axes that explained the gap on the sibling EAs this session:
  1. data window (the CSV was re-exported this session and now runs to
     2026-08-19; a claim made on an older/shorter export is a stale number)
  2. modelling convention (fill at signal-bar close vs next open, spread on/off)
  3. individual filters (session filter, indecision, entry-distance, shadow)
"""
import importlib.util
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


E = _load("engine_tailwind", "engine.py")
M = _load("sim_tailwind", "sim.py")

TARGET = "header claim: full n=835 PF=1.29 net=$1959 | train PF=1.14 net=$473 | holdout PF=1.42 net=$1486"


def line(tag, tr, i0, n):
    f = M.stats(tr)
    a, b, _ = M.split_stats(tr, i0, n)
    return (f"{tag:<34s} full n={f['n']:4d} PF={f['pf']:.3f} net=${f['net']:8.2f} "
            f"dd=${f['maxdd']:7.2f} | train n={a['n']:4d} PF={a['pf']:.3f} net=${a['net']:8.2f}"
            f" | hold n={b['n']:4d} PF={b['pf']:.3f} net=${b['net']:8.2f}")


def window_scan():
    print("--- 1. data-window scan (shipped defaults, InpAvoidOpposing ON) ---")
    print(TARGET)
    d_full, _ = E.load_h4(start=None)
    p = E.params()
    for start in ["2001-06-04", "2005-01-01", "2008-01-01", "2010-01-01",
                  "2011-01-01", "2012-01-01", "2013-01-01", "2015-01-01"]:
        d, i0 = E.load_h4(start=start)
        ctx = E.build_context(d, p)
        sig = E.base_signals(ctx, p)
        tr = M.simulate(ctx, p, sig=sig)
        tr = [t for t in tr if t["entry_i"] >= i0]
        print(line(f"start={start}", tr, i0, ctx["n"]))

    print("\n--- 1b. end-date scan (start=2013-01-01, truncating the export) ---")
    for end in ["2024-01-01", "2025-01-01", "2026-01-01", "2026-04-01", None]:
        d, i0 = E.load_h4(start="2013-01-01")
        if end is not None:
            keep = d["time"] < end
            d = d[keep].reset_index(drop=True)
        ctx = E.build_context(d, p)
        sig = E.base_signals(ctx, p)
        tr = [t for t in M.simulate(ctx, p, sig=sig) if t["entry_i"] >= i0]
        print(line(f"end={end or 'full 2026-08'}", tr, i0, ctx["n"]))


def convention_scan():
    print("\n--- 2. modelling-convention grid (start=2013-01-01) ---")
    p = E.params()
    d, i0 = E.load_h4(start="2013-01-01")
    ctx = E.build_context(d, p)
    sig = E.base_signals(ctx, p)
    for fill in ("open", "close"):
        for sp in (True, False):
            for dnb in (True, False):
                tr = [t for t in M.simulate(ctx, p, sig=sig, fill=fill,
                                            charge_spread=sp, double_isnewbar=dnb)
                      if t["entry_i"] >= i0]
                print(line(f"fill={fill} spread={int(sp)} dblNewBar={int(dnb)}",
                           tr, i0, ctx["n"]))


def filter_scan():
    print("\n--- 3. filter ablation (start=2013-01-01) ---")
    d, i0 = E.load_h4(start="2013-01-01")
    variants = [
        ("shipped", {}),
        ("no session filter", dict(use_session_filter=False)),
        ("no friday block", dict(block_friday_close=False)),
        ("no indecision block", dict(block_indecision=False)),
        ("EntryDistATR=0", dict(entry_dist_atr=0.0)),
        ("SLBuffer=1.0", dict(sl_buffer_atr=1.0)),
        ("SLBuffer=2.0", dict(sl_buffer_atr=2.0)),
        ("cooldown=0", dict(cooldown=0)),
        ("MinRun=2", dict(min_run=2)),
        ("MinRun=4", dict(min_run=4)),
        ("no filters at all", dict(use_session_filter=False, block_friday_close=False,
                                   block_indecision=False, entry_dist_atr=0.0,
                                   avoid_opposing=False)),
    ]
    for tag, over in variants:
        p = E.params(**over)
        ctx = E.build_context(d, p)
        sig = E.base_signals(ctx, p)
        tr = [t for t in M.simulate(ctx, p, sig=sig) if t["entry_i"] >= i0]
        print(line(tag, tr, i0, ctx["n"]))


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    if which in ("all", "1"):
        window_scan()
    if which in ("all", "2"):
        convention_scan()
    if which in ("all", "3"):
        filter_scan()
