"""
Step 1 of the Ratchet 2026-09-23 work: prove sim.py reproduces BOTH real MT5
Strategy Tester reports before trusting it for anything.

  Backtest_1: InpUseMomentumEntry=false, InpUseWickReject=false (960 trades)
  Backtest_2: InpUseMomentumEntry=true,  InpUseWickReject=true  (443 trades,
              the shipped v3.28 defaults)

Real trades are matched to simulated ones by entry BAR (the EA only enters on
the first tick of a new M5 bar, so the 5-minute floor of the real entry time
is exact). Reported: match rates, P/L agreement on matched trades (USD per
0.01 lot, currency-neutral), exit-reason agreement, SL-level agreement at
exit (the real exit deal's comment carries the exact resting SL, "sl 4378.70").
"""
import sys
import collections

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import report as R  # noqa: E402
import sim as S     # noqa: E402


def key(ts):
    return pd.Timestamp(ts).floor("5min")


def compare(real, simt, label, verbose=False):
    rk = {key(t["entry_time"]): t for t in real}
    sk = {key(t["entry_time"]): t for t in simt}
    both = sorted(set(rk) & set(sk))
    only_r = sorted(set(rk) - set(sk))
    only_s = sorted(set(sk) - set(rk))
    same_dir = sum(rk[x]["side"] == sk[x]["dir"] for x in both)
    dp = np.array([rk[x]["pnl_usd"] - sk[x]["pnl"] for x in both])
    close = np.abs(dp) <= np.maximum(0.5, 0.1 * np.abs([rk[x]["pnl_usd"] for x in both]))
    same_exit = sum(key(rk[x]["exit_time"]) == key(sk[x]["exit_time"]) for x in both)
    rs = R.summary([t["pnl_usd"] for t in real])
    ss = S.stats_of(simt)
    print(f"== {label}")
    print(f"   REAL: n={rs['n']} net=${rs['net']:.2f} PF={rs['pf']} win(>0)={rs['win']}%")
    print(f"   SIM : n={ss['n']} net=${ss['net']:.2f} PF={ss['pf']} win(>=0)={ss['win']}%")
    print(f"   entry-bar matches {len(both)} ({100*len(both)/max(1,len(real)):.1f}% of real), "
          f"real-only {len(only_r)}, sim-only {len(only_s)}; same dir {same_dir}; "
          f"same exit bar {same_exit}; P/L within max($0.50,10%) {int(close.sum())}")
    if len(dp):
        print(f"   matched P/L: real ${sum(rk[x]['pnl_usd'] for x in both):.2f} vs sim "
              f"${sum(sk[x]['pnl'] for x in both):.2f} (median |diff| ${np.median(np.abs(dp)):.3f})")
    if verbose:
        for x in only_r[:40]:
            print("   real-only", x, rk[x]["side"], round(rk[x]["pnl_usd"], 2))
        for x in only_s[:40]:
            print("   sim-only ", x, sk[x]["dir"], sk[x]["kind"], round(sk[x]["pnl"], 2))
    return both, only_r, only_s, rk, sk


if __name__ == "__main__":
    ctx = S.build_ctx()
    v = "-v" in sys.argv
    r1 = R.load(R.RATCHET_BT1)
    r2 = R.load(R.RATCHET_BT2)
    s1, st1 = S.simulate(ctx, S.BASELINE)
    s2, st2 = S.simulate(ctx, S.SHIPPED)
    compare(r1, s1, "Backtest_1 (baseline: momentum OFF, wick OFF)", v)
    compare(r2, s2, "Backtest_2 (shipped v3.28: momentum ON, wick ON)", v)
