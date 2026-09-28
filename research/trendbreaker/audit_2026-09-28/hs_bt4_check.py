"""AUDIT: real H&S Gold Backtest_4 (v1.08 shipped config, 2020-01..2026-09, real MT5 fills) split by
period, and bar-matched against (1) hs_sim.py (EA-faithful) and (2) the research-sim 'mode A'
(frictionless neckline fill) and 'mode B' (next-open fill) trade lists."""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius"); sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
sys.path.insert(0, "/home/user/test-project/research/ratchet"); sys.path.insert(0, "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad")
import numpy as np, pandas as pd
import report as REP, engine as E, pattern_rigor_common as R, hs_sim as HS
from hs_next_round_test import find_breakouts_causal
from hs_fill_isolation import eval_fill
UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
real = REP.load(UP + "d2ffdcc0-20260925_-_ReportTester-382043238_-_HS_-_Backtest_4.xlsx")


def pf(a):
    a = np.asarray(a); gw = a[a > 0].sum(); gl = -a[a < 0].sum(); return gw / gl if gl > 0 else np.inf


rp = np.array([t["pnl_usd"] / t["entry"] for t in real]); rt = pd.to_datetime([t["entry_time"] for t in real])
print(f"REAL BT4 n={len(real)} %PF={pf(rp):.3f}")
for a, b in (("2020-01", "2022-07-04"), ("2022-07-04", "2024-07"), ("2024-07", "2027")):
    m = (rt >= a) & (rt < b); print(f"   real {a}..{b}: n={m.sum()} %PF={pf(rp[m]):.3f} net$={sum(real[i]['pnl_usd'] for i in np.where(m)[0]):.1f}")
m15 = E.load_m15_native()
df = m15[(m15.time >= "2019-06-01")].reset_index(drop=True)[["time", "open", "high", "low", "close", "spread"]]
k0 = int(np.searchsorted(df.time.values, np.datetime64("2020-01-01")))
tr = HS.simulate(df, dict(HS.DEFAULTS, point=0.01, start_k=k0))
st = pd.to_datetime(df.time.values[[t["entry_i"] for t in tr]]); sp_ = np.array([t["pnl_pct"] for t in tr])
b, h, l, c, atr = find_breakouts_causal(df, break_tol=0.35)
o = df["open"].values; spr = df["spread"].values * 0.01
lists = {"hs_sim": (st, sp_)}
for mode in ("A", "B"):
    res = [r for r in eval_fill(b, o, h, l, c, spr, mode) if r["brk_q"] >= k0]
    # entry bar: A enters ON the retest bar, B at the bar after
    ei = [min(r["brk_q"] + 1, len(df) - 1) for r in res]   # the EA's real fill bar is the one after the retest bar
    lists["research " + mode] = (pd.to_datetime(df.time.values[ei]), np.array([r["pnl_pct"] for r in res]))
rkey = set(rt.floor("15min"))
for name, (t, p) in lists.items():
    k = set(pd.DatetimeIndex(t).floor("15min"))
    both = rkey & k
    print(f"{name:<12} n={len(p)} %PF={pf(p):.3f} | entry-bar matches with REAL: {len(both)} ({100*len(both)/len(rkey):.0f}% of real, {100*len(both)/max(1,len(k)):.0f}% of sim)")
    for a, bb in (("2020-01", "2022-07-04"), ("2022-07-04", "2027")):
        m = (t >= a) & (t < bb); print(f"      {a}..{bb}: n={m.sum()} %PF={pf(p[m]):.3f}")
