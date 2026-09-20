"""Independent re-derivation of Slipstream_EA.mq5's header-claimed numbers.

Header claim (mq5 26-35):
  H4 Gold 2013-2026, 70/30 chronological split
  full n=554 PF=1.56 net=$1620 | train n=394 PF=1.39 net=$632 |
  holdout n=155 PF=1.86 net=$1024
Header confluence claim (mq5 43-45):
  win 65.6->70.2 train, 73.1->76.1 holdout; PF 1.36->1.48 train,
  1.84->1.81 holdout; n=554->467; maxdd 132.8->121.2
"""
import importlib.util
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name, fn):
    s = importlib.util.spec_from_file_location(name, os.path.join(HERE, fn))
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


E = _load("engine_slipstream", "engine.py")
S = _load("sim_slipstream", "sim.py")

t0 = time.time()
d, i0 = E.load_h4(start="2013-01-01", warmup_from_full=True)
p = E.params()
ctx = E.build_context(d, p)
n = ctx["n"]
print(f"bars total={n}  tradable window starts at {i0} ({d['time'].iloc[i0]}) "
      f"-> {d['time'].iloc[-1]}")
print(f"shipped defaults: BBPeriod={p['bb_period']} TouchTol={p['touch_tol']} "
      f"SLBuffer={p['sl_buffer']} lookback={p['lookback']} "
      f"signal_line_mode={p['signal_line_mode']} confluence={p['require_confluence']} "
      f"trendline={p['use_trendline']} maxhold={p['max_hold_bars']}\n")


def run(label, pp, **kw):
    sig = E.base_signals(ctx, pp, symmetric_touch=kw.pop("symmetric_touch", False))
    # restrict the tradable window to 2013+ by zeroing earlier signals
    sig0 = sig[0].copy()
    sig0[:i0] = 0
    tr = S.simulate(ctx, pp, sig=(sig0, max(sig[1], i0)), **kw)
    full = S.stats(tr)
    a, b, cut = S.split_stats(tr, i0, n)
    print(f"{label}")
    print(f"   full   {S.fmt(full)}")
    print(f"   train  {S.fmt(a)}")
    print(f"   holdout{S.fmt(b)}   (bar-index cut={cut}, {d['time'].iloc[cut]})")
    return tr, full, a, b


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "all"

    if which in ("all", "base"):
        print("=" * 78)
        print("SHIPPED DEFAULTS (confluence ON), intrabar=stop_first")
        run("", p)
        print("\nSHIPPED DEFAULTS, intrabar=lock_first (pessimistic bound)")
        run("", p, intrabar="lock_first")

        print("\n" + "=" * 78)
        print("CONFLUENCE OFF (the 'standalone' number the header compares against)")
        run("", p, require_confluence=False)
        print("\nCONFLUENCE OFF, intrabar=lock_first")
        run("", p, require_confluence=False, intrabar="lock_first")

    if which in ("all", "orig"):
        print("\n" + "=" * 78)
        print("ORIGINAL params 20/1.0/0.5 (header says the shipped 14/1.25/0.75 beat")
        print("these on BOTH halves) - confluence OFF and ON")
        po = E.params(**{k: E.P_ORIGINAL[k] for k in ("bb_period", "touch_tol", "sl_buffer")})
        run("  [orig, confluence OFF]", po, require_confluence=False)
        run("  [orig, confluence ON ]", po)

    if which in ("all", "extra"):
        print("\n" + "=" * 78)
        print("SENSITIVITY / STRUCTURAL CHECKS")
        tr, full, a, b = run("  [confluence loop starts at CLOSED bar k=1, not the forming bar]",
                             p, include_forming_bar=False)
        run("  [short-side pullback measured off HIGH (symmetric) instead of LOW]",
            p, symmetric_touch=True)
        print("\n  exit-reason mix + max-hold check, shipped defaults:")
        _s = E.base_signals(ctx, p)
        _s0 = _s[0].copy()
        _s0[:i0] = 0
        tr = S.simulate(ctx, p, sig=(_s0, max(_s[1], i0)))
        from collections import Counter
        print("   ", Counter(t["reason"] for t in tr))
        print("    longest hold =", max(t["bars"] for t in tr), "bars "
              f"(InpMaxHoldBars={p['max_hold_bars']})")
        print("    longs/shorts =", Counter(t["dir"] for t in tr))
        print("    per-year net:", S.year_breakdown(tr))

    print(f"\n[wall clock {time.time()-t0:.1f}s]")
