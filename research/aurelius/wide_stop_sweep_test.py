"""
User's ask, after the trailing-peak exit was rejected: keep exiting only
on a real reversal signal (not a trail), but try a WIDER safety stop -
the hypothesis being that the 2-5xATR stops already tested might be
clipping trades on ordinary pullbacks before the actual reversal has a
chance to fire, on both of the session's two strongest hold-to-reversal
candidates:
  - BOS-confirmed structure entries (k=5), held to the next opposite
    BOS confirmation (bos_confirm_test.py's best cell was 3.0xATR,
    net=1446.78, 78.3th percentile, 3/5 blocks).
  - The 21/50 EMA cross, held to the next opposite cross
    (ema21_50_cross_hold_test.py's best cell was 3.0xATR, net=2812.02,
    99.7th percentile, 3/5 blocks).

Both already used sim_cross_to_cross, which exits at the opposite event
OR the safety stop, whichever comes first - this just widens the stop
grid (out to 15xATR) using the exact same exit mechanism, entries
unchanged, for a direct apples-to-apples comparison against the
already-committed narrower-stop numbers.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from ema21_50_cross_hold_test import sim_cross_to_cross
from bos_confirm_test import bos_confirmed_events

POINT = E.POINT
N_RANDOM_SEEDS = 300
WIDE_GRID = (2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 15.0)


def run_sweep(label, events, close, high, low, spread, atr, n, time):
    print("=" * 70)
    print(f"{label}: {len(events)} entries -> {len(events)/(n/288):.3f}/day\n")
    best = None
    for sl in WIDE_GRID:
        trades = sim_cross_to_cross(events, close, high, low, spread, atr, n, sl)
        if not trades:
            print(f"  safety_sl={sl}xATR: 0 trades"); continue
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        cutoff = int(n * 0.7)
        is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
        holds = np.array([t[1] - t[0] for t in trades])
        print(f"  safety_sl={sl:5.1f}xATR: n={len(trades)} net={pnls.sum():9.2f} "
              f"win%={100*(pnls>0).mean():.1f} pf={pf:.3f} IS={is_net:8.2f} OOS={oos_net:8.2f} "
              f"median_hold={np.median(holds):.0f}bars")
        if best is None or pnls.sum() > best[0]:
            best = (pnls.sum(), sl, trades)

    if best is None:
        print("  no trades resolved anywhere in the grid\n")
        return

    best_net, best_sl, best_trades = best
    print(f"\n  best: safety_sl={best_sl}xATR net={best_net:.2f} n={len(best_trades)}")

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
    print(f"  random-direction control: null mean={random_nets.mean():.2f} std={random_nets.std():.2f} "
          f"-> real net percentile={pct:.1f}")

    pnls = np.array([t[2] for t in best_trades])
    entries = np.array([t[0] for t in best_trades])
    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    print(f"  5-block walk-forward:")
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            print(f"    block {b+1}: 0 trades"); continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
        t0 = pd.to_datetime(time[lo]).date(); t1 = pd.to_datetime(time[min(hi, n-1)]).date()
        print(f"    block {b+1} [{t0}->{t1}]: n={nb} net={netb:.2f} win%={100*(pnls[m]>0).mean():.1f}")
    print(f"    -> positive in {pos}/5 blocks\n")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    time = df5["time"].values

    ema21 = E.ma(close, 21, "ema")
    ema50 = E.ma(close, 50, "ema")
    above = ema21 > ema50
    cross_up = above & ~np.concatenate(([False], above[:-1]))
    cross_dn = (~above) & np.concatenate(([False], above[:-1]))
    cross_events = [(i, 1.0) for i in np.where(cross_up)[0]] + [(i, -1.0) for i in np.where(cross_dn)[0]]
    cross_events.sort(key=lambda e: e[0])

    bos_events = bos_confirmed_events(close, high, low, k=5)

    run_sweep("21/50 EMA cross, held to opposite cross (wide-stop grid)",
              cross_events, close, high, low, spread, atr, n, time)
    run_sweep("BOS-confirmed (k=5), held to opposite BOS confirmation (wide-stop grid)",
              bos_events, close, high, low, spread, atr, n, time)
