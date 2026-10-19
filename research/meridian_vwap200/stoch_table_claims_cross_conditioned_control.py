"""
Second-level control for stoch_table_claims_9tf_risk_matched_null_test.py,
written because that file returned ALL NINE configs at the p floor
(0.001-0.003) - the same uniform-result red flag as the first two nulls.

Hypothesis tested: the exit rule (opposite K/D cross) is mechanically
tied to the entry rule (a fresh K/D cross). A real entry starts a full
stoch half-cycle before its exit can fire; a random bar sits at an
arbitrary stoch phase. That is construction, not "zone timing skill".

Control: same borrowed (dir, stop, target) geometry and identical exit
machinery, but random entries drawn only from same-direction K/D crosses
ANYWHERE (zone condition dropped), compared per trade with the trade
count matched (a first draft without matched counts ran out of history
and gave a spurious result; fixed here, n_null == n_real is printed).

Result (100 draws each, p resolution ~0.01), run on 4 of the 9 rows:
  GOLD M15  any-bar p=0.010  any-cross p=0.020
  GOLD H1   any-bar p=0.010  any-cross p=0.119
  SILVER H1 any-bar p=0.010  any-cross p=0.010
  BTC H1    any-bar p=0.010  any-cross p=1.000 (zone entries WORSE than random crosses)
=> most of the any-bar "edge" is the fresh-cross/exit coupling. The zone
condition adds at most a small, inconsistent increment, and none of these
reaches the K=9 Sidak bar (0.0057) at this resolution. Every row is still
a net loser on %PF regardless. Honest K: 4 additional null variants.
Usage: python3 stoch_table_claims_cross_conditioned_control.py GOLDH1 SILVERH1 ...
"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vwap_open"))
import stoch_table_claims_9tf_risk_matched_null_test as M
from stoch_table_claims_verify_test import load, build_trades

which = sys.argv[1:]
for row in M.CONFIGS:
    inst, tf, f, trim, h1, kp, sl, dp, zl, zh = row
    if f"{inst}{tf}" not in which:
        continue
    df, point = M.load_h1(f, trim) if h1 else load(f, trim_gold=trim)
    tr = build_trades(df, point, kp, sl, dp, zl, zh)
    m = M.Machine(df, point, kp, sl, dp)
    geo = M.effective_geometry(df, point, tr)
    real_net = sum(t["pnl_pct"] for t in tr) / len(tr)
    real_hold = np.mean([t["exit_i"] - t["entry_i"] for t in tr])
    up = np.flatnonzero(np.array(m.up)); dn = np.flatnonzero(np.array(m.dn))
    lim = m.n - M.TIME_CAP_BARS - 2
    up = up[(up >= m.start) & (up < lim)]; dn = dn[(dn >= m.start) & (dn < lim)]
    rng = np.random.default_rng(1)
    for mode in ("any-bar", "any-cross"):
        nets, holds, cnts = [], [], []
        for _ in range(100):
            order = rng.permutation(len(tr)); cnt = 0; total = 0.0; nxt = m.start
            # sample sorted candidate times, assign direction from geometry
            cand = np.sort(rng.choice(m.valid_idx, size=len(tr) * 6))
            ci = 0
            for k in range(len(tr)):
                d, s, t = geo[order[k]]
                if mode == "any-bar":
                    while ci < len(cand) and cand[ci] < nxt: ci += 1
                    if ci >= len(cand): break
                    i = int(cand[ci])
                else:
                    pool = up if d > 0 else dn
                    j0 = np.searchsorted(pool, nxt)
                    if j0 >= len(pool): break
                    # random cross among the next few eligible, keeps pace through history
                    i = int(pool[min(j0 + rng.integers(0, 3), len(pool) - 1)])
                ex, p = m.trade(i, d, s, t)
                total += p; holds.append(ex - i); nxt = ex + 1; cnt += 1
            nets.append(total / max(cnt,1)); cnts.append(cnt)
        nets = np.array(nets)
        print(f"{inst} {tf} {mode:9s} n_real={len(tr)} n_null={np.mean(cnts):.0f} real/trade={100*real_net:.4f}% null/trade={100*nets.mean():.4f}% "
              f"p={(np.sum(nets>=real_net)+1)/101:.4f} real_hold={real_hold:.1f} null_hold={np.mean(holds):.1f}", flush=True)
