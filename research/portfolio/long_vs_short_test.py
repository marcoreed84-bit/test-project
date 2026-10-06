"""
Real long (buy) vs short (sell) performance, broken down per EA, on each
EA's own currently-shipped real construction (Meridian/Ratchet include
the now-shipped early-exit-on-break rule since that's their real live
behavior as of tonight; Aurelius/Vanguard/H&S use their unmodified real
construction - no early-exit was shipped there, it was tested and
rejected/neutral). User's question: does Aurelius specifically do better
in uptrends (buys) than downtrends (sells) - real GOLD has been falling
since they started running it live, which would explain some live pain
if so, independent of any bug.

Loads each same-named module (sim.py exists in BOTH research/ratchet/
and research/aurelius/; early_exit_break_test.py exists in BOTH
research/meridian/ and research/ratchet/) via importlib with an explicit
file path and a unique internal name - a plain `import sim as X` a
second time would silently return the FIRST cached module instead of
loading the other one, a real bug caught before running, not after.
"""
import sys
import importlib.util

import numpy as np
import pandas as pd


def load_module(unique_name, path):
    spec = importlib.util.spec_from_file_location(unique_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = mod
    spec.loader.exec_module(mod)
    return mod


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report_split(label, dirs, pnl):
    dirs = np.asarray(dirs)
    pnl = np.asarray(pnl)
    print(f"\n{label}")
    for name, mask in (("BUY (long)", dirs > 0), ("SELL (short)", dirs < 0)):
        p = pnl[mask]
        if len(p) == 0:
            print(f"    {name:14s}: n=0")
            continue
        print(f"    {name:14s}: n={len(p):4d}  win%={100*(p>0).mean():5.1f}  PF={pf(p):6.3f}  "
              f"net={p.sum():9.2f}  avg={p.mean():7.3f}")


sys.path.insert(0, "/home/user/test-project/research/ratchet")   # bars.py needed by msim/ratchet sim
sys.path.insert(0, "/home/user/test-project/research/meridian")  # for msim's own internal import
sys.path.insert(0, "/home/user/test-project/research/aurelius")  # for engine.py needed by aurelius sim

print("=" * 92)
print("MERIDIAN (shipped V102 + early-exit-on-break, current real live config)")
print("=" * 92)
M = load_module("msim_mod", "/home/user/test-project/research/meridian/msim.py")
MEE = load_module("meridian_ee", "/home/user/test-project/research/meridian/early_exit_break_test.py")
from dataclasses import replace  # noqa: E402
ctx_m = M.build_ctx()
p_m = replace(M.V102, exit_fn=MEE.make_early_exit_fn(ctx_m))
trades_m, _ = M.simulate(ctx_m, p_m)
report_split("Meridian", [t["dir"] for t in trades_m], [t["pnl"] for t in trades_m])

print("\n" + "=" * 92)
print("RATCHET (shipped + early-exit-on-break, current real live config)")
print("=" * 92)
RS = load_module("ratchet_sim", "/home/user/test-project/research/ratchet/sim.py")
REE = load_module("ratchet_ee", "/home/user/test-project/research/ratchet/early_exit_break_test.py")
ctx_r = RS.build_ctx()
p_r = replace(RS.SHIPPED, exit_fn=REE.make_early_exit_fn(ctx_r))
trades_r, _ = RS.simulate(ctx_r, p_r)
report_split("Ratchet", [t["dir"] for t in trades_r], [t["pnl"] for t in trades_r])

print("\n" + "=" * 92)
print("AURELIUS M5 (shipped v1.46, unmodified - early-exit tested, not shipped here)")
print("=" * 92)
E = load_module("aurelius_engine", "/home/user/test-project/research/aurelius/engine.py")
S = load_module("aurelius_sim", "/home/user/test-project/research/aurelius/sim.py")
df5 = E.load_m5(); h4 = E.load_h4()
ctx_a5 = E.build_context(df5, h4, E.P)
trades_a5 = S.simulate(ctx_a5, params=E.P)
pnl_a5 = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades_a5]
report_split("Aurelius M5", [t["dir"] for t in trades_a5], pnl_a5)

print("\n" + "=" * 92)
print("AURELIUS M15 (shipped, unmodified)")
print("=" * 92)
df15 = E.load_m15_native()
ctx_a15 = E.build_context(df15, h4, E.P15)
trades_a15 = S.simulate(ctx_a15, params=E.P15)
pnl_a15 = [(t["exit_px"] - t["entry_px"]) * t["dir"] for t in trades_a15]
report_split("Aurelius M15", [t["dir"] for t in trades_a15], pnl_a15)

print("\n" + "=" * 92)
print("VANGUARD (shipped, unmodified - early-exit tested, rejected)")
print("=" * 92)
V = load_module("vanguard_ee", "/home/user/test-project/research/aurelius/vanguard_early_exit_break_test.py")
trades_v = V.run(ctx_a5, df5["close"].values, df5["high"].values, df5["low"].values,
                  df5["spread"].values, len(df5), early_exit=False)
report_split("Vanguard", [t["dir"] for t in trades_v], [t["pnl"] for t in trades_v])

print("\n" + "=" * 92)
print("HEAD & SHOULDERS (shipped, unmodified - early-exit tested, rejected)")
print("=" * 92)
HS = load_module("hs_sim_mod", "/home/user/test-project/research/trendbreaker/hs_sim.py")
DATA_DIR = "/tmp/claude-0/-home-user-test-project/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/scratchpad/data"


def load_gold_m15():
    d = pd.read_csv(f"{DATA_DIR}/GOLD_M15_native.csv", skiprows=1)
    d["time"] = pd.to_datetime(d["time"], format="%Y.%m.%d %H:%M:%S")
    d = d.sort_values("time").reset_index(drop=True)
    d = d[d["time"] >= pd.Timestamp("2014-06-13")].reset_index(drop=True)
    return d[["time", "open", "high", "low", "close", "spread"]]


df_hs = load_gold_m15()
p_hs = dict(HS.DEFAULTS, point=0.01)
trades_hs = HS.simulate(df_hs, p_hs)
report_split("H&S", [t["dir"] for t in trades_hs], [t["pnl_pct"] for t in trades_hs])
print("    (H&S's pnl is pnl_pct, not price units - % terms, same convention as its own reporting)")
