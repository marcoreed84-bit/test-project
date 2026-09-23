"""
Step 2b: WHY the Python research over-counted - attribute the gap to the
specific EA-vs-model differences msim.py models, and check msim against the
header's two older full-history real runs.

  * Same 2026 window as python_vs_real.py (2026-01-01..2026-08-14): msim
    under the Python model's rules (stop-and-reverse, no Friday flatten, no
    spread filter, no stale-ticket bar, no session-open gate) should land on
    the research code's own trade counts (412 / 504); under the EA's rules on
    the real ones (362 / 409). Then each EA rule switched on alone, on top of
    the Python rules, shows which one moves net.
  * Full history 2023.01.01-2026.09.19 vs the header's REAL results:
      v1.00 (150 EMA, no S/R, stop 3.0): 2512 trades, PF 1.2437, win 26.75%
      v1.01 (150 EMA + S/R 0.5, stop 2.5): 2641 trades, PF 1.2824
Deterministic (no execution noise) - these are trade-count / structure
checks, not P/L forecasts.
"""
import sys
from dataclasses import replace

import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/meridian")
import msim as M  # noqa: E402

PY_RULES = dict(stop_and_reverse=True, no_friday=True, max_spread=0, stale_ticket_bar=False, entry_from_min=0)
EA_NAMES = dict(stop_and_reverse="not stop-and-reverse", no_friday="Friday 22:00 flatten",
                max_spread="spread filter", stale_ticket_bar="stale-ticket bar", entry_from_min="01:05 session gate")

if __name__ == "__main__":
    ctx = M.build_ctx()
    W0, CUT = pd.Timestamp("2026-01-01"), pd.Timestamp("2026-08-15")
    for lbl, p, py_n, real_n in [("v1.02", M.V102, 412, 362), ("BT1 binary", M.BT1_BINARY, 504, 409)]:
        ea = M.stats_of(M.simulate(ctx, p, W0, CUT)[0])
        py = M.stats_of(M.simulate(ctx, replace(p, **PY_RULES), W0, CUT)[0])
        print(f"== {lbl}: research code n={py_n}, real n={real_n}")
        print(f"   msim, Python rules : {py}")
        print(f"   msim, EA rules     : {ea}")
        for k, name in EA_NAMES.items():
            q = replace(p, **{kk: vv for kk, vv in PY_RULES.items() if kk != k})
            s = M.stats_of(M.simulate(ctx, q, W0, CUT)[0])
            print(f"   Python rules + EA's {name:<22}: n={s['n']:4d} net={s['net']:8.2f} "
                  f"({100*(s['net']/py['net']-1):+5.1f}%) PF={s['pf']:.3f}")
    A, B = pd.Timestamp("2023-01-01"), pd.Timestamp("2026-09-19")
    print("\nFull history 2023.01.01-2026.09.19 vs the header's REAL runs:")
    for lbl, p, real in [("v1.00 150EMA noSR stop3.0", replace(M.BT1_BINARY, stop_atr=3.0), "REAL 2512 trades PF 1.2437 win 26.75%"),
                         ("v1.01 150EMA SR0.5 stop2.5", replace(M.BT1_BINARY, use_sr=True), "REAL 2641 trades PF 1.2824"),
                         ("v1.02 250SMA SR0.5 stop2.5", M.V102, "(no real full-history run)")]:
        print(f"   {lbl:<27} {M.stats_of(M.simulate(ctx, p, A, B)[0])} | {real}")
