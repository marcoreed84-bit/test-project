"""
Step 2: validate sim.py against REAL MT5 reports of this reconstruction.

  Backtest_1 (v1.12, MSG3-only, M1, filter OFF) - the clean baseline.
  Backtest_2 (v1.13, same config, InpSkipDeadZone ON) - the cascade check:
      the simulator must reproduce the fact that the live filter made net
      WORSE, not just match the baseline.

Real trades are matched to simulated trades by entry minute (the EA only
ever enters on the first tick of a new bar, so the minute is exact).
"""
import sys
import collections

sys.path.insert(0, "/home/user/test-project/research/msg")
from report import load_deals, round_trips, summary  # noqa: E402
from sim import load_bars, simulate, stats, Params   # noqa: E402

UP = "/root/.claude/uploads/0bd2ac72-7526-55cb-84f6-d8ea842f8c5b/"
BT1 = UP + "28855db1-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_1.xlsx"
BT2 = UP + "9d84e911-20260923_-_ReportTester-382043238_-_MSG_-_Backtest_2.xlsx"


def key(t):
    return t["entry_time"].replace(second=0, microsecond=0)


def compare(real, sim, label, verbose=False):
    rk = {key(t): t for t in real}
    sk = {key(t): t for t in sim}
    both = sorted(set(rk) & set(sk))
    only_r = sorted(set(rk) - set(sk))
    only_s = sorted(set(sk) - set(rk))
    same_dir = sum(rk[x]["side"] == sk[x]["dir"] for x in both)
    same_out = sum(abs(rk[x]["pnl_usd"] - sk[x]["pnl"]) < max(2.0, 0.1 * abs(rk[x]["pnl_usd"])) for x in both)
    same_legs = sum(rk[x]["nlegs"] == sk[x]["nlegs"] for x in both)
    rs = summary([t["pnl_usd"] for t in real])
    ss = stats(sim)
    print(f"== {label}")
    print(f"   REAL: n={rs['n']} net=${rs['net']:.2f} PF={rs['pf']} win={rs['win']}%")
    print(f"   SIM : n={ss['n']} net=${ss['net']:.2f} PF={ss['pf']} win={ss['win']}%")
    print(f"   entry-minute matches: {len(both)}  (real-only {len(only_r)}, sim-only {len(only_s)})")
    print(f"   of matched: same dir {same_dir}, same #legs {same_legs}, same P/L (+-10%/$2) {same_out}")
    if verbose:
        for x in both:
            r, s = rk[x], sk[x]
            flag = "" if abs(r["pnl_usd"] - s["pnl"]) < max(2.0, 0.1 * abs(r["pnl_usd"])) else "  <-- P/L differs"
            print(f"   {x}  dir {r['side']:+d}/{s['dir']:+d}  entry {r['entry']:.2f}/{s['px']:.2f}  "
                  f"legs {r['nlegs']}/{s['nlegs']}  pnl {r['pnl_usd']:8.2f}/{s['pnl']:8.2f}{flag}")
        print("   real-only:", [str(x) for x in only_r])
        print("   sim-only :", [str(x) for x in only_s])
    return both, only_r, only_s


if __name__ == "__main__":
    bars = load_bars()
    verbose = "-v" in sys.argv
    r1 = round_trips(load_deals(BT1))
    s1, info = simulate(bars, Params())
    compare(r1, s1, "Backtest_1 (v1.12 baseline, filter OFF)", verbose)
    print("  ", info)
    r2 = round_trips(load_deals(BT2))
    s2, _ = simulate(bars, Params(skip_dead=True))
    compare(r2, s2, "Backtest_2 (v1.13, InpSkipDeadZone ON)", verbose)
    print("   cascade check - real delta (BT2-BT1): $%.2f   sim delta: $%.2f" % (
        sum(t["pnl_usd"] for t in r2) - sum(t["pnl_usd"] for t in r1),
        sum(t["pnl"] for t in s2) - sum(t["pnl"] for t in s1)))
