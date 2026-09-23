"""
Step 1 of the Meridian 2026-09-23 work: prove sim.py reproduces both real
reports, and pin down what Backtest_1's stale binary actually ran.

  Backtest_2: recompiled v1.02 (InpPConfirm=250 SMA, InpSRDays=3,
              InpMinSRDistATR=0.5, stop 2.5) - 414 trades.
  Backtest_1: a stale pre-v1.02 binary. Its Inputs block has v1.00's layout
              (InpP150=150, InpMAMethod=EMA) with InpSafetyStopATR=2.5 and NO
              InpSRDays/InpMinSRDistATR - a combination no committed version
              has (v1.00 = 3.0 stop, no S/R; v1.01 = 2.5 stop WITH S/R
              inputs). Candidates are simulated and bar-matched to decide.

Real trades matched to sim trades by entry bar (5-min floor of the real fill).
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/meridian")
sys.path.insert(0, "/home/user/test-project/research/ratchet")
import report as R  # noqa: E402
import msim as M    # noqa: E402


def key(ts):
    return pd.Timestamp(ts).floor("5min")


def compare(real, simt, label, verbose=False):
    rk = {key(t["entry_time"]): t for t in real}
    sk = {key(t["entry_time"]): t for t in simt}
    both = sorted(set(rk) & set(sk))
    only_r, only_s = sorted(set(rk) - set(sk)), sorted(set(sk) - set(rk))
    same_dir = sum(rk[x]["side"] == sk[x]["dir"] for x in both)
    same_exit = sum(key(rk[x]["exit_time"]) == key(sk[x]["exit_time"]) for x in both)
    rs, ss = R.summary([t["pnl_usd"] for t in real]), M.stats_of(simt)
    print(f"== {label}")
    print(f"   REAL n={rs['n']} net=${rs['net']:.2f} PF={rs['pf']} win={rs['win']}%   "
          f"SIM n={ss['n']} net=${ss['net']:.2f} PF={ss['pf']} win={ss['win']}%")
    print(f"   entry-bar matches {len(both)} ({100*len(both)/max(1,len(real)):.1f}% of real), real-only "
          f"{len(only_r)}, sim-only {len(only_s)}; same dir {same_dir}; same exit bar {same_exit}; matched P/L "
          f"real ${sum(rk[x]['pnl_usd'] for x in both):.2f} vs sim ${sum(sk[x]['pnl'] for x in both):.2f}")
    if verbose:
        for x in only_r[:15]:
            print("   real-only", x, rk[x]["side"], round(rk[x]["pnl_usd"], 2), rk[x]["reason"])
        for x in only_s[:15]:
            print("   sim-only ", x, sk[x]["dir"], round(sk[x]["pnl"], 2), sk[x]["reason"])
    return len(both)


if __name__ == "__main__":
    ctx = M.build_ctx()
    v = "-v" in sys.argv
    r1, r2 = R.load(R.MERIDIAN_BT1), R.load(R.MERIDIAN_BT2)
    s2, st2 = M.simulate(ctx, M.V102)
    compare(r2, s2, "Backtest_2 vs sim v1.02 (250 SMA + S/R 0.5, stop 2.5)", v)
    print("   ", st2)
    print("\nWhich logic did Backtest_1's stale binary run?")
    for lbl, p in [("150 EMA, NO S/R, stop 2.5", M.BT1_BINARY),
                   ("150 EMA, S/R 0.5 (v1.01), stop 2.5", replace(M.BT1_BINARY, use_sr=True)),
                   ("150 EMA, NO S/R, stop 3.0 (v1.00)", replace(M.BT1_BINARY, stop_atr=3.0))]:
        s1, _ = M.simulate(ctx, p)
        compare(r1, s1, "Backtest_1 vs sim " + lbl, v and lbl.startswith("150 EMA, NO S/R, stop 2.5"))
    # stop-2.5 evidence straight from the report: initial SL distance / Wilder ATR
    ks = []
    atr, t64 = ctx["atr"], ctx["t64"]
    for t in r1:
        i = int(np.searchsorted(t64, np.datetime64(key(t["entry_time"]))))
        if t["sl0"] > 0:
            ks.append(abs(t["entry"] - t["sl0"]) / atr[i - 1])
    print(f"\nBacktest_1 initial SL distance / Wilder ATR: median {np.median(ks):.3f} (IQR "
          f"{np.percentile(ks,25):.3f}-{np.percentile(ks,75):.3f})")
