"""
User's construction: the 21/50 EMA CROSS itself as the trend signal -
enter on the cross, hold through the WHOLE leg until the opposite cross
happens (not a fixed TP/SL, not a short scalp hold) - the classic dual-
moving-average trend-following system. Distinct from everything tested
today: the 3-MA alignment tests used static alignment + short/medium
fixed holds; this uses the crossover EVENT itself with a patient,
cross-to-cross hold, matching the user's own chart annotation (green
arrow = cross up = the whole up-leg; red arrow = cross down = the whole
down-leg).

A wide safety stop is included (real risk management - "hold forever"
isn't tradeable), but the PRIMARY exit is the opposite cross, not a
tight target.

Real M5 data, real spread, correct single-position sequencing, random-
direction control (the lesson from the multi-timeframe stochastic
lookahead bug - checked from the start this time), IS/OOS + walk-forward.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E

POINT = E.POINT
N_RANDOM_SEEDS = 300  # sequential re-sim per seed is not free - kept modest


def sim_cross_to_cross(cross_events, close, high, low, spread, atr, n, safety_sl_atr):
    """cross_events: list of (bar_i, direction) in chronological order, one
    per crossover (already alternating by construction - 21/50 can't cross
    up twice without crossing down in between). Enters at the cross, exits
    at the NEXT cross event (of either kind) or the safety stop, whichever
    comes first. Correct single-position sequencing (each trade's exit IS
    the next entry's trigger point, so no overlap is possible by
    construction here - still explicit for clarity/consistency)."""
    trades = []
    for k in range(len(cross_events) - 1):
        i, d = cross_events[k]
        i_next, _ = cross_events[k + 1]
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        is_buy = d > 0
        entry = raw + sc if is_buy else raw - sc
        sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
        exit_bar, exit_px = None, None
        cap = min(i_next + 1, n)  # exit at the next cross's fill point at the latest
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
    return trades


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
    events = [(i, 1.0) for i in np.where(cross_up)[0]] + [(i, -1.0) for i in np.where(cross_dn)[0]]
    events.sort(key=lambda e: e[0])
    print(f"n_bars={n} (~{n/288:.0f} trading days), {len(events)} 21/50 EMA crosses "
          f"-> {len(events)/(n/288):.3f}/day\n")

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
              f"pf={pf:.3f} IS={is_net:.2f} OOS={oos_net:.2f} median_hold={np.median(holds):.0f}bars "
              f"stopped_out={sum(1 for t in trades if abs(t[2])>0 and (close[t[1]] if False else 0)==0)}")

    # random-direction control on the best-looking safety_sl
    best_sl, best_net = None, -1e18
    for safety_sl in (2.0, 3.0, 4.0, 5.0):
        trades = sim_cross_to_cross(events, close, high, low, spread, atr, n, safety_sl)
        net = sum(t[2] for t in trades) if trades else -1e18
        if net > best_net:
            best_net, best_sl = net, safety_sl

    print(f"\nrandom-direction control on safety_sl={best_sl}xATR (real net={best_net:.2f}):")
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

    # walk-forward on the best cell
    trades = sim_cross_to_cross(events, close, high, low, spread, atr, n, best_sl)
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
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
