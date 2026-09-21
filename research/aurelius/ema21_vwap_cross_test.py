"""
User's ask: instead of 21 EMA crossing the 50 EMA, test 21 EMA crossing
VWAP as the trend-turn trigger - directly motivated by what's visible on
the real Aurelius M5 chart (150 EMA / VWAP / 50 EMA / 21 EMA stack).
VWAP resets every session (cumulative typical-price*volume from each
day's start), so it behaves differently from a smoothed EMA - it can
sit anywhere relative to the 50/150 EMAs depending on how far the
session has run and how strong the move is, which is exactly why this
is a genuinely different signal from the EMA-only cross, not just a
relabeled version of it.

Uses engine.py's own session_vwap()/ma() output (build_context's `vwap`
and `m21` arrays) - the real indicators Aurelius_EA.mq5 computes, not a
reimplementation. Held cross-to-cross exactly like
ema21_50_cross_hold_test.py (same sim_cross_to_cross, same safety-stop
mechanism) - and since wide_stop_sweep_test.py just confirmed 3.0xATR
is already near-optimal for both existing hold-to-reversal candidates,
that same narrow 2-5xATR grid is used here rather than re-testing wide
stops from scratch.

Real M5 data, real spread, correct single-position sequencing by
construction, random-direction control from the start, walk-forward
alongside the aggregate.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from ema21_50_cross_hold_test import sim_cross_to_cross

POINT = E.POINT
N_RANDOM_SEEDS = 300

if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    m21, vwap = ctx["m21"], ctx["vwap"]
    time = df5["time"].values

    above = m21 > vwap
    valid = ~np.isnan(m21) & ~np.isnan(vwap)
    above_prev = np.concatenate(([False], above[:-1]))
    valid_prev = np.concatenate(([False], valid[:-1]))
    cross_up = above & ~above_prev & valid & valid_prev
    cross_dn = (~above) & above_prev & valid & valid_prev
    events = [(i, 1.0) for i in np.where(cross_up)[0]] + [(i, -1.0) for i in np.where(cross_dn)[0]]
    events.sort(key=lambda e: e[0])
    print(f"n_bars={n} (~{n/288:.0f} trading days), {len(events)} 21EMA/VWAP crosses "
          f"-> {len(events)/(n/288):.3f}/day\n")

    print("=" * 70)
    best = None
    for safety_sl in (2.0, 3.0, 4.0, 5.0):
        trades = sim_cross_to_cross(events, close, high, low, spread, atr, n, safety_sl)
        if not trades:
            print(f"safety_sl={safety_sl}xATR: 0 trades"); continue
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        cutoff = int(n * 0.7)
        is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
        holds = np.array([t[1] - t[0] for t in trades])
        print(f"safety_sl={safety_sl}xATR: n={len(trades)} net={pnls.sum():.2f} win%={100*(pnls>0).mean():.1f} "
              f"pf={pf:.3f} IS={is_net:.2f} OOS={oos_net:.2f} median_hold={np.median(holds):.0f}bars")
        if best is None or pnls.sum() > best[0]:
            best = (pnls.sum(), safety_sl, trades)

    print("\n" + "=" * 70)
    if best is None:
        print("no trades resolved anywhere in the grid")
        sys.exit(0)

    best_net, best_sl, best_trades = best
    print(f"best: safety_sl={best_sl}xATR net={best_net:.2f} n={len(best_trades)}")

    print(f"\nrandom-direction control (real net={best_net:.2f}):")
    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(events))
        rev = [(i, d) for (i, _), d in zip(events, rdirs)]
        rev.sort(key=lambda e: e[0])
        trades_r = sim_cross_to_cross(rev, close, high, low, spread, atr, n, best_sl)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < best_net).mean()
    print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")

    pnls = np.array([t[2] for t in best_trades])
    entries = np.array([t[0] for t in best_trades])
    edges = np.linspace(0, n, 6).astype(int)
    print(f"\n5-block walk-forward (safety_sl={best_sl}xATR):")
    pos = 0
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            print(f"  block {b+1}: 0 trades"); continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
        t0 = pd.to_datetime(time[lo]).date(); t1 = pd.to_datetime(time[min(hi, n-1)]).date()
        print(f"  block {b+1} [{t0}->{t1}]: n={nb} net={netb:.2f} win%={100*(pnls[m]>0).mean():.1f}")
    print(f"  -> positive in {pos}/5 blocks")
