"""
Step 3: does v1.02 actually validate, and which of its two changes is doing
what? v1.02 = v1.01 (150 EMA confirm + VWAP + S/R 0.5, stop 2.5) with the
confirm line swapped to a 250 SMA. The real same-window pair is Backtest_1
(150 EMA, NO S/R) vs Backtest_2 (250 SMA + S/R) - two changes at once - so
this runs all four corners through the validated simulator (msim.py matches
414/414 of Backtest_2's and 471/473 of Backtest_1's real entries to the bar,
and 2,511 vs the real 2,512 trades on the header's full-history v1.00 run),
24 execution-noise seeds each, in every calendar year the M5 export covers.

2023/2024/2025 are out-of-sample for the simulator's validation, and the
Python research that picked 250 SMA used 2023-01..2026-08 (it is in-sample
for THAT, but it ran under the Python model's stop-and-reverse / no-Friday
rules, not the EA's).
"""
import sys
from dataclasses import replace

import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/meridian")
import mc as MC     # noqa: E402
import msim as M    # noqa: E402

PERIODS = [("2023", "2023-01-02", "2024-01-01"), ("2024", "2024-01-01", "2025-01-01"),
           ("2025", "2025-01-01", "2026-01-01"), ("2026", "2026-01-01", "2026-09-21")]
CORNERS = [("150 EMA, no S/R (BT1 binary)", M.BT1_BINARY),
           ("150 EMA + S/R (v1.01)", replace(M.BT1_BINARY, use_sr=True)),
           ("250 SMA, no S/R", replace(M.V102, use_sr=False)),
           ("250 SMA + S/R (v1.02, BT2)", M.V102)]

if __name__ == "__main__":
    tot = {}
    for per, a, b in PERIODS:
        print(f"--- {per}")
        for lbl, p in CORNERS:
            df = MC.mc(p, start=pd.Timestamp(a), end=pd.Timestamp(b))
            tot.setdefault(lbl, []).append(df)
            print(f"  {lbl:<30} n={df.n.mean():6.1f} net=${df.net.mean():7.1f} (sd {df.net.std():5.1f}) "
                  f"PF={df.pf.mean():.3f} closedDD=${df.closed_dd.mean():5.1f} eqDD=${df.eq_dd.mean():5.1f}",
                  flush=True)
    print("--- 4-period totals (sum of per-period means)")
    for lbl, _ in CORNERS:
        dfs = tot[lbl]
        print(f"  {lbl:<30} net=${sum(d.net.mean() for d in dfs):7.1f}  worst-period eqDD="
              f"${max(d.eq_dd.mean() for d in dfs):5.1f}  periods net>0 {sum(d.net.mean() > 0 for d in dfs)}/4")
