"""
Follow-up to structure_turn_test.py. That test found the raw idea is
directionally correct - a fractal higher-low/lower-high really does
form ~12-17 bars BEFORE the matching 21/50 EMA cross on average (this
corrects a sign bug in that script's own diagnostic print, verified
below) - but trading the higher-low/lower-high itself loses money at
every window size except the slowest (k=5), and even there it's weak
(70th percentile vs random, net carried almost entirely by one walk-
forward block). Reason: most higher-lows/lower-highs are noise - minor
wiggles that don't turn into a real trend change, so the early-entry
benefit is swamped by false reversals.

This tests the stricter, well-known fix: don't trade the higher-low
itself, wait for it to be CONFIRMED by an actual break of structure
(BOS) - price closing back beyond the prior opposing swing extreme.
i.e. in what had been a downtrend: (1) a higher low forms (first
warning, "change of character"), (2) THEN price must close above the
most recent swing HIGH before entering long (the actual break of
structure). Symmetric for a lower high needing a close below the prior
swing low to confirm short. This gives up some of the earlier-entry
edge (the whole point of testing it) in exchange for filtering out
the wiggles - the standard tradeoff between the two known price-action
approaches.

A new higher-low/lower-high forming before confirmation completes
overrides (cancels) the pending one - the freshest structure read wins,
same as how a real trader would update their read as new bars print.

Same rigor/comparability as the rest of today's line of testing: same
M5 data, same cross-to-cross hold + safety-stop grid via
sim_cross_to_cross, random-direction control from the start, walk-
forward blocks alongside the aggregate.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from ema21_50_cross_hold_test import sim_cross_to_cross
from structure_turn_test import find_fractals

POINT = E.POINT
N_RANDOM_SEEDS = 300


def bos_confirmed_events(close, high, low, k):
    """Higher-low/lower-high 'change of character' followed by an actual
    break-of-structure close through the prior opposing swing extreme.
    Causal: the pending reversal is only confirmed once a later bar's
    CLOSE actually breaks the reference level; a fresher change-of-
    character before that happens overrides the pending one."""
    n = len(close)
    is_low, is_high = find_fractals(high, low, k)
    swing_lo_idx = np.where(is_low)[0]
    swing_hi_idx = np.where(is_high)[0]
    pts = [(i + k, "L", i) for i in swing_lo_idx if i + k < n] + \
          [(i + k, "H", i) for i in swing_hi_idx if i + k < n]
    pts.sort(key=lambda t: t[0])

    events = []
    prev_lo_val, prev_hi_val = None, None
    last_hi_val, last_lo_val = None, None
    state = None
    pending, pending_ref = None, None
    pt_idx = 0
    n_pts = len(pts)

    for j in range(n):
        # process any swing confirmations that land exactly on this bar
        while pt_idx < n_pts and pts[pt_idx][0] == j:
            confirm_bar, kind, form_bar = pts[pt_idx]
            pt_idx += 1
            if kind == "L":
                val = low[form_bar]
                if prev_lo_val is not None and val > prev_lo_val and state != "up" and last_hi_val is not None:
                    pending, pending_ref = "up", last_hi_val
                prev_lo_val = val
                last_lo_val = val
            else:
                val = high[form_bar]
                if prev_hi_val is not None and val < prev_hi_val and state != "down" and last_lo_val is not None:
                    pending, pending_ref = "down", last_lo_val
                prev_hi_val = val
                last_hi_val = val

        if pending == "up" and close[j] > pending_ref:
            state = "up"
            events.append((j, 1.0))
            pending, pending_ref = None, None
        elif pending == "down" and close[j] < pending_ref:
            state = "down"
            events.append((j, -1.0))
            pending, pending_ref = None, None

    return events


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

    print(f"n_bars={n} (~{n/288:.0f} trading days)\n")
    print("=" * 70)

    overall_best = None
    for k in (2, 3, 5):
        events = bos_confirmed_events(close, high, low, k)
        gaps = []
        for i, d in events:
            cands = [ci for ci, cd in cross_events if cd == d and ci >= i - 50]
            if cands:
                gaps.append(min(cands, key=lambda ci: abs(ci - i)) - i)
        gaps = np.array(gaps)
        lead_txt = (f"matched cross is {gaps.mean():.1f} bars later on average "
                    f"(positive=BOS still earlier than the cross, n_matched={len(gaps)}/{len(events)})"
                    if len(gaps) else "no matches")
        print(f"\n--- fractal window k={k} ({len(events)} BOS-confirmed events, "
              f"{len(events)/(n/288):.3f}/day) ---")
        print(f"  timing vs 21/50 cross: {lead_txt}")

        for safety_sl in (2.0, 3.0, 4.0, 5.0):
            trades = sim_cross_to_cross(events, close, high, low, spread, atr, n, safety_sl)
            if not trades:
                print(f"    safety_sl={safety_sl}xATR: 0 trades"); continue
            pnls = np.array([t[2] for t in trades])
            entries = np.array([t[0] for t in trades])
            gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
            pf = gw / gl if gl > 0 else float("inf")
            cutoff = int(n * 0.7)
            is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
            print(f"    safety_sl={safety_sl}xATR: n={len(trades)} net={pnls.sum():.2f} "
                  f"win%={100*(pnls>0).mean():.1f} pf={pf:.3f} IS={is_net:.2f} OOS={oos_net:.2f}")
            if overall_best is None or pnls.sum() > overall_best[0]:
                overall_best = (pnls.sum(), k, safety_sl, events, trades)

    print("\n" + "=" * 70)
    if overall_best is None:
        print("no trades resolved anywhere in the grid")
        sys.exit(0)

    best_net, best_k, best_sl, best_events, best_trades = overall_best
    print(f"best cell: k={best_k} safety_sl={best_sl}xATR net={best_net:.2f} n={len(best_trades)}")

    print(f"\nrandom-direction control (best cell, real net={best_net:.2f}):")
    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(best_events))
        rev = [(i, d) for (i, _), d in zip(best_events, rdirs)]
        rev.sort(key=lambda e: e[0])
        trades_r = sim_cross_to_cross(rev, close, high, low, spread, atr, n, best_sl)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < best_net).mean()
    print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")

    pnls = np.array([t[2] for t in best_trades])
    entries = np.array([t[0] for t in best_trades])
    edges = np.linspace(0, n, 6).astype(int)
    print(f"\n5-block walk-forward (k={best_k}, safety_sl={best_sl}xATR):")
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
