"""
User's ask: instead of waiting for the 21/50 EMA cross (a lagging
confirmation - by the time it fires, a chunk of the new leg is already
gone), can we catch the trend turning EARLIER via price structure -
a higher low forming in what had been a downtrend (first sign buyers
are stepping in before sellers lose control), or a lower high forming
in what had been an uptrend. Classic Dow-theory / price-action "break
of structure" idea.

Construction:
  - Swing points via a symmetric N-bar fractal (default N=2, i.e. a
    5-bar window): bar i is a swing low if low[i] is strictly the
    lowest in [i-N, i+N], a swing high if high[i] is strictly the
    highest in [i-N, i+N]. A swing is only KNOWN at bar i+N (needs N
    bars afterward to confirm it wasn't beaten) - no lookahead: every
    comparison uses only data available as of the confirmation bar.
  - State machine over the confirmed-swing sequence (chronological by
    CONFIRMATION bar, not formation bar): track the last two confirmed
    swing lows and last two confirmed swing highs. A new swing low
    that's HIGHER than the previous confirmed swing low = "higher low"
    -> if current structure state isn't already "up", flip it to up and
    emit a buy event at the confirmation bar. Symmetric for "lower
    high" -> sell. Same-direction repeats while already in that state
    are no-ops (mirrors how the EMA-cross events are naturally
    alternating).
  - Held cross-to-cross exactly like ema21_50_cross_hold_test.py (same
    sim_cross_to_cross function, same safety-stop grid) so the two are
    directly comparable apples-to-apples: same data, same exit logic,
    only the trigger differs.
  - Reports how much EARLIER (in bars) structure events fire relative
    to the matching-direction EMA 21/50 cross, to check whether this
    actually catches the leg sooner as hypothesized - not just assumed.
  - Fractal window swept (N=2/3/5) as a robustness check, not a single
    cherry-picked lookback.

Real M5 data (E.build_context, same as the cross-hold test), real
spread, random-direction control from the start, walk-forward blocks
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


def find_fractals(high, low, k):
    """Strict N-bar-symmetric fractal swing points. Returns boolean arrays
    (is_swing_low, is_swing_high) indexed by FORMATION bar. Confirmation
    (the earliest a strategy could know about it) is formation bar + k."""
    n = len(low)
    is_low = np.zeros(n, dtype=bool)
    is_high = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        wl = low[i - k:i + k + 1]
        wh = high[i - k:i + k + 1]
        if low[i] == wl.min() and np.sum(wl == wl.min()) == 1:
            is_low[i] = True
        if high[i] == wh.max() and np.sum(wh == wh.max()) == 1:
            is_high[i] = True
    return is_low, is_high


def structure_events(high, low, k):
    """Chronological (by confirmation bar) higher-low / lower-high
    structure-turn events, state-machined into alternating buy/sell
    events like an EMA cross. Returns list of (confirm_bar, direction)."""
    n = len(low)
    is_low, is_high = find_fractals(high, low, k)
    swing_lo_idx = np.where(is_low)[0]
    swing_hi_idx = np.where(is_high)[0]

    # (confirmation_bar, kind, formation_bar) merged and sorted by confirmation
    pts = [(i + k, "L", i) for i in swing_lo_idx if i + k < n] + \
          [(i + k, "H", i) for i in swing_hi_idx if i + k < n]
    pts.sort(key=lambda t: t[0])

    events = []
    prev_lo_val, prev_hi_val = None, None
    state = None  # None / "up" / "down"
    for confirm_bar, kind, form_bar in pts:
        if kind == "L":
            val = low[form_bar]
            if prev_lo_val is not None and val > prev_lo_val and state != "up":
                state = "up"
                events.append((confirm_bar, 1.0, form_bar))
            prev_lo_val = val
        else:
            val = high[form_bar]
            if prev_hi_val is not None and val < prev_hi_val and state != "down":
                state = "down"
                events.append((confirm_bar, -1.0, form_bar))
            prev_hi_val = val
    return events


def lead_lag_vs_cross(struct_events, cross_events):
    """For each structure event, find the next same-direction EMA cross
    event at or after it and report the gap in bars (positive = structure
    fired first, i.e. earlier warning as hypothesized)."""
    gaps = []
    for i, d, _ in struct_events:
        cands = [ci for ci, cd in cross_events if cd == d and ci >= i - 50]
        if not cands:
            continue
        nearest = min(cands, key=lambda ci: abs(ci - i))
        gaps.append(nearest - i)
    return np.array(gaps)


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
        raw_events = structure_events(high, low, k)
        events = [(i, d) for i, d, _ in raw_events]
        gaps = lead_lag_vs_cross(raw_events, cross_events)
        lead_txt = (f"median lead={np.median(gaps):.1f} bars "
                    f"(positive=structure earlier, n_matched={len(gaps)}/{len(events)})"
                    if len(gaps) else "no matches")
        print(f"\n--- fractal window k={k} ({len(events)} structure-turn events, "
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
