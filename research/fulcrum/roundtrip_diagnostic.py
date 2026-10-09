"""
DIAGNOSTIC (2026-10-09, user's own framing): "there must be an early out
before price goes from profit to stop loss" - i.e. for real losing trades
that reversed all the way to the stop, how many actually touched real
profit first, and how much was given back? This is the round-trip version
of the arm-then-trail idea already tested and REJECTED for Fulcrum M15 (see
the v2.13 changelog in Fulcrum_M15_EA.mq5: 42/42 R/ATR arm-trail combos
worse, net $666 vs $1,320 even at Meridian's own shipped values) - this
doesn't re-run that construction, it just measures the RAW FACTS the
rejected construction already had to contend with: for real SL-exit
trades, what was the max favorable excursion (MFE) reached before the
reversal, in $ and in R (multiples of initial risk)?
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S

if __name__ == "__main__":
    df, h4, ctx = E.build_all(E.P15)
    trades = S.simulate(ctx, params=E.P15)
    h, l = ctx["high"], ctx["low"]

    sl_trades = [t for t in trades if t["reason"] == "STOP"]
    print(f"Fulcrum M15 real shipped trades: n={len(trades)}, SL-exit losers: n={len(sl_trades)}\n")

    mfe_dollars, mfe_r, gaveback = [], [], []
    for t in sl_trades:
        d = t["dir"]
        entry_px = t["entry_px"]
        risk = abs(entry_px - t["stop0"])
        i0, i1 = t["entry_i"] + 1, t["exit_i"]
        if i1 <= i0:
            mfe = 0.0
        else:
            if d > 0:
                mfe = (h[i0:i1 + 1].max() - entry_px)
            else:
                mfe = (entry_px - l[i0:i1 + 1].min())
        mfe = max(mfe, 0.0)
        mfe_dollars.append(mfe)
        mfe_r.append(mfe / risk if risk > 0 else 0.0)
        gaveback.append(mfe + risk)   # what was given up: peak profit + the full loss actually taken

    mfe_dollars = np.array(mfe_dollars)
    mfe_r = np.array(mfe_r)
    gaveback = np.array(gaveback)

    print("Of the real SL-exit losers, how far into profit did they get before reversing?")
    for thr_r in (0.1, 0.25, 0.5, 1.0, 2.0):
        frac = (mfe_r >= thr_r).mean()
        print(f"  reached >= {thr_r}R in favor before reversing: {100*frac:.1f}%  (n={int((mfe_r>=thr_r).sum())})")

    print(f"\nMFE distribution (R multiples of initial risk) across all {len(sl_trades)} SL losers:")
    print(f"  median={np.median(mfe_r):.2f}R  mean={mfe_r.mean():.2f}R  p75={np.percentile(mfe_r,75):.2f}R  "
          f"p90={np.percentile(mfe_r,90):.2f}R  max={mfe_r.max():.2f}R")

    print(f"\n$ figures (at shipped InpLots=0.01, 1 price unit = $1):")
    print(f"  median initial risk per trade: ${np.median([abs(t['entry_px']-t['stop0']) for t in sl_trades]):.2f}")
    print(f"  median MFE reached before reversing: ${np.median(mfe_dollars):.2f}")
    print(f"  mean MFE reached before reversing: ${mfe_dollars.mean():.2f}")

    never_profitable = (mfe_r < 0.1).mean()
    print(f"\n{100*never_profitable:.1f}% of SL losers NEVER even reached 0.1R in favor - "
          f"these are straight losers, nothing to 'protect', an early-out can't help them.")
    could_help = (mfe_r >= 1.0).mean()
    print(f"{100*could_help:.1f}% reached at least 1R in favor (i.e. at least gave back their own entire "
          f"risk amount in profit before reversing) - this is the group a breakeven/trail exit COULD "
          f"theoretically rescue.")
