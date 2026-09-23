"""
Step 3: separate the two things Backtest_1 -> Backtest_2 changed at once.

The real pair toggles BOTH InpUseMomentumEntry and InpUseWickReject, so it is
NOT the isolated momentum test the v3.28 header's Python prediction describes
(2,703 -> 3,146 trades, maxDD 84 -> 131, momentum added to a pullback-only,
wick-OFF baseline). This runs the validated sequential simulator (sim.py +
noise.py's measured execution noise, 24 seeds each) on all four corners:

      mom OFF / wick OFF   = Backtest_1's config
      mom ON  / wick OFF   = the header's own modeled comparison
      mom OFF / wick ON
      mom ON  / wick ON    = Backtest_2's config (shipped v3.28)

and reports, besides net/PF/closed DD, a mark-to-market equity drawdown on
M5 bars in USD and as % of the running equity peak on a 10,000 ZAR deposit
(= $607 at the window's realized 16.48 ZAR/USD) - the same kind of number the
report's "Equity Drawdown Maximal" is.

Also: of Backtest_2's real trades, how many were momentum-triggered at all.
"""
import sys
from dataclasses import replace

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import noise as N   # noqa: E402
import report as R  # noqa: E402
import sim as S     # noqa: E402

DEP_USD = 10000.0 / 16.48


def equity_dd(ctx, trades, dep=DEP_USD):
    """M5 mark-to-market equity DD (USD, and % of running peak)."""
    h, l, sp = ctx["h"], ctx["l"], ctx["spread"] * S.POINT
    peak, bal, best, bestp = dep, dep, 0.0, 0.0
    for x in trades:
        a, b = x["entry_i"], x["exit_i"]
        d = x["dir"]
        if d > 0:
            fh = h[a:b + 1] - x["entry"]
            fl = l[a:b + 1] - x["entry"]
        else:
            fh = x["entry"] - (l[a:b + 1] + sp[a:b + 1])
            fl = x["entry"] - (h[a:b + 1] + sp[a:b + 1])
        fl[-1] = max(fl[-1], x["pnl"]) if len(fl) else 0.0
        fh[-1] = min(fh[-1], max(x["pnl"], fh[-1])) if len(fh) else 0.0
        for k in range(len(fh)):
            dd = peak - (bal + fl[k])
            if dd > best:
                best, bestp = dd, dd / peak
            peak = max(peak, bal + fh[k])
        bal += x["pnl"]
        peak = max(peak, bal)
    return best, bestp


def run(label, p, seeds=range(24)):
    df, trs = N.mc(p, seeds=seeds, keep_trades=True)
    ctx, _ = N.get_ctx()
    eq = [equity_dd(ctx, tr) for tr in trs]
    df["eq_dd"] = [e[0] for e in eq]
    df["eq_ddp"] = [100 * e[1] for e in eq]
    print(f"{label:<28} n={df.n.mean():6.1f} (momentum {df.mom_n.mean():5.1f})  net=${df.net.mean():6.1f} "
          f"sd {df.net.std():5.1f}  PF={df.pf.mean():.3f}  closedDD=${df.closed_dd.mean():5.1f}  "
          f"equityDD=${df.eq_dd.mean():5.1f} ({df.eq_ddp.mean():4.1f}% of peak)")
    return df


if __name__ == "__main__":
    ctx, _ = N.get_ctx()
    base = S.BASELINE
    res = {}
    res["off/off"] = run("mom OFF / wick OFF (BT1)", base)
    res["on/off"] = run("mom ON  / wick OFF", replace(base, momentum=True))
    res["off/on"] = run("mom OFF / wick ON", replace(base, wick=True))
    res["on/on"] = run("mom ON  / wick ON (BT2)", S.SHIPPED)

    print("\nisolated momentum effect (header's modeled comparison is the wick-OFF row):")
    for w in ("off", "on"):
        a, b = res[f"off/{w}"], res[f"on/{w}"]
        print(f"  wick {w.upper():3}: trades {a.n.mean():.0f}->{b.n.mean():.0f} ({100*(b.n.mean()/a.n.mean()-1):+.0f}%)  "
              f"net {a.net.mean():.0f}->{b.net.mean():.0f} ({100*(b.net.mean()/a.net.mean()-1):+.0f}%)  "
              f"PF {a.pf.mean():.3f}->{b.pf.mean():.3f}  closedDD {a.closed_dd.mean():.0f}->{b.closed_dd.mean():.0f} "
              f"({100*(b.closed_dd.mean()/a.closed_dd.mean()-1):+.0f}%)  equityDD {a.eq_dd.mean():.0f}->{b.eq_dd.mean():.0f} "
              f"({100*(b.eq_dd.mean()/a.eq_dd.mean()-1):+.0f}%)")

    # real Backtest_2: which trades were momentum-triggered? (deterministic sim kinds, bar-matched)
    simt, _ = S.simulate(ctx, S.SHIPPED)
    kinds = {N.key(t["entry_time"]): t["kind"] for t in simt}
    real = R.load(R.RATCHET_BT2)
    km = [kinds.get(N.key(t["entry_time"])) for t in real]
    mom = [t for t, k in zip(real, km) if k == "momentum"]
    pb = [t for t, k in zip(real, km) if k == "pullback"]
    print(f"\nreal Backtest_2: {len(mom)} momentum-triggered trades, {len(pb)} pullback, "
          f"{sum(k is None for k in km)} unmatched")
    for lbl, grp in (("momentum", mom), ("pullback", pb)):
        s = R.summary([t["profit_ccy"] for t in grp])
        print(f"  {lbl:<9} n={s['n']:4d}  net {s['net']:9.2f} ZAR  PF {s['pf']}  win {s['win']}%")
