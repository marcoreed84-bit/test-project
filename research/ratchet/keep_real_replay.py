"""
Supporting check for robust_keep.py, on the REAL fills: take every real trade
in both 2026-09-23 reports, rebuild its give-back trail exactly as TrailStop()
runs it (peak = best bar-OPEN bid/ask since entry, updated once per new bar),
and for trades whose peak reached X ATR replay ONLY the exit with keep_hi
instead of 0.30 on the real M5 bars, stopping at the real exit if the tighter
stop never fills first. Everything else - entries, the other trades - is the
real report's.

This is an exit-only static replay: it cannot see the (small) cascade of an
earlier exit freeing the slot sooner, so it is evidence alongside the
sequential simulator, not a verdict on its own. Slippage: the measured mean
SL slip in ATR units is applied to replayed fills. For the 6ATR->0.60 cell it
also rebuilds the real max equity drawdown (paradox.py's M1 reconstruction)
with the replayed exits swapped in.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B    # noqa: E402
import noise as N   # noqa: E402
import paradox as P  # noqa: E402
import report as R  # noqa: E402


def replay(ctx, trips, x_atr, keep_hi, slip_atr):
    t64, o, h, l, sp, atr = ctx["t64"], ctx["o"], ctx["h"], ctx["l"], ctx["spread"] * 0.01, ctx["atr"]
    out = []
    for r in trips:
        i0 = int(np.searchsorted(t64, np.datetime64(N.key(r["entry_time"]))))
        i1 = int(np.searchsorted(t64, np.datetime64(N.key(r["exit_time"]))))
        a, d, e = atr[i0 - 1], r["side"], r["entry"]
        peak, armed, sl, new_exit, new_t = e, False, None, None, None
        for t in range(i0 + 1, i1 + 1):
            cur = o[t] if d > 0 else o[t] + sp[t]
            peak = max(peak, cur) if d > 0 else min(peak, cur)
            pf = (peak - e) * d
            if pf >= x_atr * a:
                armed = True
                cand = e + d * keep_hi * pf
                cand = min(cand, cur - 0.01) if d > 0 else max(cand, cur + 0.01)
                sl = cand if sl is None else (max(sl, cand) if d > 0 else min(sl, cand))
            if armed and sl is not None:
                hit = (l[t] <= sl) if d > 0 else (h[t] + sp[t] >= sl)
                # on the real exit bar, only count it if the tighter stop sits above the real fill
                if hit and (t < i1 or (sl - r["exit"]) * d > 0):
                    new_exit = sl + (slip_atr * a if d > 0 else -slip_atr * a)
                    new_t = pd.Timestamp(t64[t]) + pd.Timedelta(minutes=4)
                    break
        new_pnl = (new_exit - e) * d if new_exit is not None else r["pnl_usd"]
        out.append((armed, r["pnl_usd"], new_pnl, new_t))
    return out


def replayed_trips(trips, res):
    """Real round-trips with the replayed exits swapped in (ZAR at each trade's own rate)."""
    out = []
    for r, (armed, old, new, nt) in zip(trips, res):
        r = dict(r)
        if nt is not None:
            rate = r["zar_per_usd"] or 16.5
            r["profit_ccy"] = new * rate
            r["exit_time"] = nt.to_pydatetime()
        out.append(r)
    return out


if __name__ == "__main__":
    ctx, noise = N.get_ctx()
    slip = float(noise["atr"][1].mean())
    m1 = B.load_m1()
    w = m1[(m1.time >= "2025-12-31") & (m1.time <= "2026-09-22")].reset_index(drop=True)
    for path, lbl in [(R.RATCHET_BT1, "Backtest_1"), (R.RATCHET_BT2, "Backtest_2")]:
        trips = R.load(path)
        base = sum(t["pnl_usd"] for t in trips)
        print(f"== {lbl}: real net ${base:.2f}")
        for x, k in [(4, 0.6), (5, 0.5), (5, 0.6), (5, 0.7), (6, 0.6), (8, 0.6)]:
            res = replay(ctx, trips, x, k, slip)
            arm = [z for z in res if z[0]]
            d = sum(z[2] - z[1] for z in res)
            print(f"   {x}ATR->{k:.2f}: {len(arm):3d} trades reach it (real P/L of those ${sum(z[1] for z in arm):7.2f})"
                  f"  exit-only replay delta ${d:+7.2f}  -> net ${base + d:.2f}")
            if (x, k) == (6, 0.6):
                ec = P.equity_curve(replayed_trips(trips, res), w)
                dd, ddp, pk, tr, peakv = P.max_dd(ec)
                ec0 = P.equity_curve(trips, w)
                dd0, ddp0, *_ = P.max_dd(ec0)
                print(f"      real max equity DD {dd0:,.0f} ZAR ({100*ddp0:.2f}%) -> replayed {dd:,.0f} ZAR "
                      f"({100*ddp:.2f}%)")
