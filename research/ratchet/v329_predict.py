"""
Step 8: what the next real MT5 runs should show, written down BEFORE they
exist (so they can confirm or refute it - same discipline as v3.20's
InpBBMaxPos criteria).

Same GOLD# M5 2026.01.01-2026.09.21 window, 10,000 ZAR, 0.01 lots as the two
2026-09-23 reports. Three configs through the validated simulator, 48 seeds
under each noisy execution model plus the deterministic one:

  v3.28 shipped    momentum ON,  wick ON                   (= real Backtest_2)
  v3.29 default    momentum OFF, wick ON
  v3.29 + runner   v3.29 with InpTrailRunnerATR=6.0 / InpTrailRunnerKeep=0.60

Net is shown in USD per 0.01 lot and in ZAR at the window's realized 16.48
ZAR/USD (11,590.72 ZAR / $703.19 on Backtest_1); equity DD is M5
mark-to-market (decompose.equity_dd) as % of the running peak on the
10,000 ZAR deposit.
"""
import sys
from dataclasses import replace
from functools import partial

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import candidates as C  # noqa: E402
import decompose as D   # noqa: E402
import noise as N       # noqa: E402
import report as R      # noqa: E402
import sim as S         # noqa: E402

ZAR = 16.48
CFG = [("v3.28 shipped (mom ON)", S.SHIPPED),
       ("v3.29 default (mom OFF)", C.BASE),
       ("v3.29 + runner 6.0/0.60", replace(C.BASE, keep_fn=partial(C.keep_prog, x_atr=6.0, keep_hi=0.60)))]

if __name__ == "__main__":
    ctx, _ = N.get_ctx()
    r2 = R.summary([t["pnl_usd"] for t in R.load(R.RATCHET_BT2)])
    print(f"REAL Backtest_2 (v3.28): n={r2['n']} net=${r2['net']:.1f} ({r2['net']*ZAR:,.0f} ZAR) PF={r2['pf']}  "
          f"equity DD 36.14%")
    for mode in ("atr", "usd", "none"):
        print(f"--- execution model: {mode}")
        for lbl, p in CFG:
            df, trs = N.mc(p, seeds=range(48), mode=mode, keep_trades=True)
            eq = [D.equity_dd(ctx, tr) for tr in trs]
            eqd = sum(e[0] for e in eq) / len(eq)
            eqp = 100 * sum(e[1] for e in eq) / len(eq)
            print(f"  {lbl:<26} n={df.n.mean():5.1f}  net=${df.net.mean():6.1f} (~{df.net.mean()*ZAR:,.0f} ZAR, "
                  f"sd ${df.net.std() if len(df) > 1 else 0:5.1f})  PF={df.pf.mean():.3f}  "
                  f"closedDD=${df.closed_dd.mean():5.1f}  equityDD=${eqd:5.1f} ({eqp:4.1f}%)", flush=True)
