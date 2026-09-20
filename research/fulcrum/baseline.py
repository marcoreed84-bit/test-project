"""
Fulcrum baseline at the TRUE shipped defaults, full real data range, M5 and M15.

Everything is in price units; at the shipped LOT_FIXED/InpLots=0.01 on GOLD#
1 price unit == $1, so `net` reads directly as dollars for the shipped config.
"""
import collections
import sys
import time

import numpy as np

import engine as E
import sim as S


def hold_stats(trades):
    bars = np.array([t["exit_i"] - t["entry_i"] for t in trades])
    return dict(median_bars=int(np.median(bars)), mean_bars=round(float(bars.mean()), 1),
                max_bars=int(bars.max()))


def describe(tag, ctx, p, trades, rep):
    st = S.stats(trades)
    rk = S.risk_stats(trades, ctx)
    reasons = collections.Counter(t["reason"] for t in trades)
    print(f"\n================ {tag} ================")
    print(f"  bars={ctx['n']}  trades={st['n']}  net={st['net']:.1f}  PF={st['pf']:.3f}  "
          f"win={100*st['win_rate']:.1f}%  avg_win={st['avg_win']:.2f}  avg_loss={st['avg_loss']:.2f}")
    print(f"  closed_dd={rk['closed_dd']:.1f}  float_dd={rk['float_dd']:.1f}  "
          f"worst_mae={rk['worst_mae']:.1f} ({rk['worst_mae_atr']:.2f} x entry ATR)")
    print(f"  exit reasons: {dict(reasons)}")
    print(f"  holding: {hold_stats(trades)}   both-SL-and-TP-in-one-bar: {rep['both_hit_bars']}")
    longs = sum(1 for t in trades if t["dir"] > 0)
    print(f"  direction: {longs} long / {len(trades)-longs} short")
    print(f"  by year (net, n): {S.yearly(trades)}")
    is_, oos = S.split_stats(trades, ctx["n"])
    print(f"  IS  70%: n={is_['n']} net={is_['net']:.1f} PF={is_['pf']:.3f} win={100*is_['win_rate']:.1f}%")
    print(f"  OOS 30%: n={oos['n']} net={oos['net']:.1f} PF={oos['pf']:.3f} win={100*oos['win_rate']:.1f}%")
    print(f"  tail: {S.tail_concentration(trades)}")
    # initial risk distribution - the number InpMinStopATR's comment quotes
    r = np.array([abs(t["entry_px"] - t["stop0"]) / t["entry_atr"] for t in trades if "stop0" in t])
    if len(r):
        print(f"  initial risk (x ATR): median={np.median(r):.2f} p10={np.percentile(r,10):.2f} "
              f"p90={np.percentile(r,90):.2f}")
    return st, rk


def run(tag, params):
    t0 = time.time()
    df, h4, ctx = E.build_all(params)
    t1 = time.time()
    rep = {}
    trades = S.simulate(ctx, params=params, report=rep)
    t2 = time.time()
    print(f"[{tag}] context {t1-t0:.1f}s, simulate {t2-t1:.1f}s")
    describe(tag, ctx, params, trades, rep)
    # sensitivity: flip the both-hit tie-break to the optimistic side
    rep2 = {}
    tr2 = S.simulate(ctx, params=params, both_hit="target", report=rep2)
    s2 = S.stats(tr2)
    print(f"  [both-hit tie-break = TARGET instead of STOP] net={s2['net']:.1f} PF={s2['pf']:.3f} "
          f"win={100*s2['win_rate']:.1f}%  (n={s2['n']})")
    return ctx, trades


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("both", "m5"):
        run("FULCRUM M5  (Fulcrum_EA.mq5 v2.13 shipped defaults)", E.P)
    if which in ("both", "m15"):
        run("FULCRUM M15 (Fulcrum_M15_EA.mq5 shipped defaults)", E.P15)
