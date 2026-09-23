"""
Step 2: the Backtest_1 vs Backtest_2 drawdown paradox, from the REAL trades.

  Backtest_1 (mom OFF, wick OFF): 960 trades, net 11,590.72 ZAR, PF 1.206,
      Equity DD Maximal 5,756.73 (29.24%), Balance DD Maximal 3,592.65
  Backtest_2 (mom ON,  wick ON) : 443 trades, net  8,582.91 ZAR, PF 1.335,
      Equity DD Maximal 5,460.00 (36.14%), Balance DD Maximal 2,445.17

Rebuilds each report's real equity curve (10,000 ZAR deposit + closed P/L +
floating P/L of the one open position) on real GOLD# M1 bars - floating P/L
marked at each M1 bar's high/low (bid for longs; ask = price+spread for
shorts), converted to ZAR at that trade's own realized ZAR/USD rate - checks
the rebuilt max equity DD against the report's own figure, then takes the
worst episode apart: how much of it is floating profit handed back on a
single trade vs realized losses, and which trades drove it.
"""
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
import bars as B    # noqa: E402
import report as R  # noqa: E402

DEP = 10000.0


def equity_curve(trips, m1):
    """Per-M1-bar (time, eq_hi, eq_lo, bal). Also per-trade peak floating (ZAR)."""
    t = m1["time"].values
    hi, lo, sp = m1["high"].values, m1["low"].values, m1["spread"].values * B.POINT
    eq_hi = np.full(len(t), np.nan)
    eq_lo = np.full(len(t), np.nan)
    bal_arr = np.full(len(t), np.nan)
    bal = DEP
    last = 0
    rate_fallback = np.nanmedian([x["zar_per_usd"] for x in trips if x["zar_per_usd"]])
    for x in trips:
        a = np.searchsorted(t, np.datetime64(pd.Timestamp(x["entry_time"]).floor("1min")))
        b = np.searchsorted(t, np.datetime64(pd.Timestamp(x["exit_time"]).floor("1min")), side="right")
        eq_hi[last:a] = bal
        eq_lo[last:a] = bal
        bal_arr[last:a] = bal
        rate = x["zar_per_usd"] or rate_fallback
        if x["side"] > 0:
            fh = (hi[a:b] - x["entry"]) * rate
            fl = (lo[a:b] - x["entry"]) * rate
        else:
            fh = (x["entry"] - (lo[a:b] + sp[a:b])) * rate
            fl = (x["entry"] - (hi[a:b] + sp[a:b])) * rate
        # the exit bar can't have floated past the actual exit on the losing side
        if b - a > 0:
            fl[-1] = max(fl[-1], min(x["profit_ccy"], fl[-1]))
        eq_hi[a:b] = bal + fh
        eq_lo[a:b] = bal + fl
        bal_arr[a:b] = bal
        x["peak_float_zar"] = float(fh.max()) if b > a else 0.0
        x["worst_float_zar"] = float(fl.min()) if b > a else 0.0
        bal += x["profit_ccy"]
        last = b
    eq_hi[last:] = bal
    eq_lo[last:] = bal
    bal_arr[last:] = bal
    return pd.DataFrame(dict(time=t, eq_hi=eq_hi, eq_lo=eq_lo, bal=bal_arr))


def max_dd(ec):
    peak = np.maximum.accumulate(np.concatenate(([DEP], ec["eq_hi"].values[:-1])))
    dd = peak - ec["eq_lo"].values
    k = int(np.nanargmax(dd))
    pk = int(np.nanargmax(ec["eq_hi"].values[:k + 1] >= peak[k] - 1e-9)) if k > 0 else 0
    # locate the bar where that peak was set
    pk = int(np.where(ec["eq_hi"].values[:k + 1] >= peak[k] - 1e-6)[0][-1]) if k > 0 else 0
    return dd[k], dd[k] / peak[k], pk, k, peak[k]


def analyse(path, label, m1):
    trips = R.load(path)
    res = R.load_results(path)
    w = m1[(m1.time >= "2025-12-31") & (m1.time <= "2026-09-22")].reset_index(drop=True)
    ec = equity_curve(trips, w)
    dd, ddp, pk, tr, peakv = max_dd(ec)
    print(f"\n=== {label}")
    print(f"  REPORT Equity DD Maximal {res['Equity Drawdown Maximal']}   REBUILT {dd:,.2f} ({100*ddp:.2f}%)")
    tpk, ttr = pd.Timestamp(ec.time[pk]), pd.Timestamp(ec.time[tr])
    print(f"  peak {tpk} equity {peakv:,.2f} (balance then {ec.bal[pk]:,.2f})  ->  trough {ttr} "
          f"equity {ec.eq_lo[tr]:,.2f} (balance then {ec.bal[tr]:,.2f})")
    float_at_peak = peakv - ec.bal[pk]
    realized = ec.bal[tr] - ec.bal[pk]
    float_at_trough = ec.eq_lo[tr] - ec.bal[tr]
    print(f"  decomposition: floating profit ON at the peak {float_at_peak:,.2f}  +  realized P/L peak->trough "
          f"{realized:,.2f}  +  floating at trough {float_at_trough:,.2f}")
    ep = [x for x in trips if pd.Timestamp(x["exit_time"]) >= tpk and pd.Timestamp(x["entry_time"]) <= ttr]
    print(f"  trades touching the episode: {len(ep)}")
    for x in ep[:6]:
        print(f"    {x['entry_time']} {'BUY ' if x['side']>0 else 'SELL'} held {x['hold_min']:.0f}m  peak float "
              f"{x['peak_float_zar']:,.0f}  closed {x['profit_ccy']:,.2f} ({x['reason']})")
    if len(ep) > 6:
        rest = ep[6:]
        print(f"    ... +{len(rest)} more, realized {sum(x['profit_ccy'] for x in rest):,.2f}")
    # giveback on each trade = peak floating - realized; largest ones
    gb = sorted(trips, key=lambda x: x["peak_float_zar"] - x["profit_ccy"], reverse=True)[:5]
    print("  largest single-trade givebacks (peak floating ZAR -> realized ZAR):")
    for x in gb:
        print(f"    {x['entry_time']} peak {x['peak_float_zar']:,.0f} -> {x['profit_ccy']:,.0f}  "
              f"(gave back {x['peak_float_zar'] - x['profit_ccy']:,.0f}, held {x['hold_min']:.0f}m)")
    return trips, ec, dict(dd=dd, ddp=ddp, peak=peakv, tpk=tpk, ttr=ttr)


def concentration(trips, label):
    p = np.array(sorted([x["profit_ccy"] for x in trips], reverse=True))
    net = p.sum()
    print(f"  {label}: net {net:,.0f}; top-1 {100*p[0]/net:.0f}%  top-5 {100*p[:5].sum()/net:.0f}%  "
          f"top-10 {100*p[:10].sum()/net:.0f}% of net;  net EXCLUDING top-5 {p[5:].sum():,.0f}")


if __name__ == "__main__":
    m1 = B.load_m1()
    t1, ec1, d1 = analyse(R.RATCHET_BT1, "Backtest_1 (mom OFF, wick OFF)", m1)
    t2, ec2, d2 = analyse(R.RATCHET_BT2, "Backtest_2 (mom ON, wick ON - shipped v3.28)", m1)
    print("\n=== concentration")
    concentration(t1, "BT1")
    concentration(t2, "BT2")
    print("\n=== the % denominator")
    for lbl, d in [("BT1", d1), ("BT2", d2)]:
        print(f"  {lbl}: DD {d['dd']:,.0f} ZAR measured against an equity peak of {d['peak']:,.0f} "
              f"-> {100*d['ddp']:.2f}%  (same ZAR DD against the other run's peak would read "
              f"{100*d['dd']/(d1['peak'] if lbl=='BT2' else d2['peak']):.2f}%)")
