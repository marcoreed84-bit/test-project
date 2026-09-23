"""
v1.15 candidate, evaluated exactly as implemented in MSG_Trader_EA.mq5:
  risk% = |px - SL| / px * 100 at order time (px = the requested Ask/Bid);
  if risk% < InpSmallRiskPct (0.26) -> lots = LotStep(InpLots * InpSmallRiskLotFactor)
                                      = LotStep(0.03 / 3) = 0.01
  otherwise InpLots (0.03) as before.  Nothing else changes: the setup is
  still taken, the range is still retired, the slot is held exactly as long.

1. Full sequential re-simulation (both symbols, all periods), confirming the
   entry sequence is IDENTICAL to v1.14 (sizing cannot cascade).
2. Re-derivation on the real v1.12 MT5 trade list (Backtest_1), in USD and in
   the report's own ZAR, as the concrete prediction for the next real run.
"""
import sys
import numpy as np
sys.path.insert(0, "/home/user/test-project/research/msg")
from search import load_bars, simulate, stats, base_params, PERIODS  # noqa
from real_resize import load, LISTS  # noqa

TH, FACTOR = 0.26, 1.0 / 3.0


def v115_size(ctx):
    risk_pct = abs(ctx["fill"] - ctx["sl"]) / ctx["fill"] * 100.0
    return 0.03 * FACTOR if risk_pct < TH else 0.03


if __name__ == "__main__":
    bars = load_bars()
    print("1) sequential sim, v1.14 -> v1.15")
    for sym in ("GOLD", "GOLD#"):
        for per, (a, b) in PERIODS.items():
            t14, _ = simulate(bars, base_params(sym, start=a, end=b))
            t15, _ = simulate(bars, base_params(sym, start=a, end=b, size_fn=v115_size))
            same = [x["t"] for x in t14] == [x["t"] for x in t15]
            s14, s15 = stats(t14), stats(t15)
            small = sum(1 for x in t15 if x["units0"] == 1)
            print(f"  {sym:5s} {per:7s} n {s14['n']:3d}->{s15['n']:3d} (same entries: {same}, {small} at 0.01)  "
                  f"net {s14['net']:8.2f} -> {s15['net']:8.2f} ({s15['net']-s14['net']:+7.2f})  "
                  f"PF {s14['pf']:.2f} -> {s15['pf']:.2f}   maxDD {s14['maxdd']:.0f} -> {s15['maxdd']:.0f}   "
                  f"net/DD {s14['ret_dd']:.2f} -> {s15['ret_dd']:.2f}")
    print("2) real Backtest_1 (v1.12, GOLD, account 382043238) re-derived at v1.15 sizing")
    trips = load(LISTS[2][1])
    usd0 = zar0 = usd1 = zar1 = 0.0
    eq0, eq1 = [], []
    for t in trips:
        usd0 += t["pnl_usd"]; zar0 += t["profit_ccy"]
        if t["risk_pct"] < TH:
            fl = t["legs"][-1]
            units = round(fl["vol"] / 0.01)
            u = (fl["price"] - t["entry"]) * t["side"]
            z = fl["profit"] / units
        else:
            u, z = t["pnl_usd"], t["profit_ccy"]
        usd1 += u; zar1 += z
        eq0.append(t["profit_ccy"]); eq1.append(z)

    def dd(x):
        e = np.cumsum(x); return (np.maximum.accumulate(np.concatenate([[0], e]))[1:] - e).max()

    def pf(x):
        x = np.array(x); return x[x > 0].sum() / -x[x < 0].sum()
    print(f"  USD net {usd0:.2f} -> {usd1:.2f} ({usd1-usd0:+.2f})")
    print(f"  ZAR net {zar0:.2f} -> {zar1:.2f} ({zar1-zar0:+.2f}, {100*(zar1-zar0)/zar0:+.1f}%)  "
          f"PF {pf(eq0):.3f} -> {pf(eq1):.3f}  closed-trade maxDD ZAR {dd(eq0):.2f} -> {dd(eq1):.2f}")
