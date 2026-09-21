"""
Direct follow-up to sr_range_trade_test.py's rejection (net=-547.69,
52.7th pct - essentially random). User's point, looking at the real
chart again: that test only used ONE coarse level pair (trailing 3-day
D1 high/low) as both touch-reference and target - not the layered
support/resistance structure a real chart actually shows (many swing
highs/lows at different distances). Targeting the FAR edge of a wide
3-day range against a stop set close to the touched level was a bad
risk:reward by construction, independent of whether the rejection
concept itself has merit.

This rebuilds it with real multi-level structure: fractal swing highs/
lows (k=5, the "slowest, most reliable" window found earlier this
session in structure_turn_test.py - reused, not reinvented), kept in a
rolling pool of the most recent CONFIRMED swings (no lookahead - a
swing at bar i is only known at bar i+k). Touch/reject checks the
NEAREST pooled level below/above price; target is the NEAREST pooled
level on the other side, not a fixed 3-day extreme - a much closer,
more realistic target that changes the risk:reward this test is
specifically checking.
"""
import sys
sys.path.insert(0, ".")
import bisect
import numpy as np
import pandas as pd
import engine as E
from structure_turn_test import find_fractals
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
N_RANDOM_SEEDS = 300
FRACTAL_K = 5
POOL_SIZE = 60          # most recent confirmed swings kept per side
LOOKBACK_BARS = 12
TOUCH_TOL_ATR = 0.30
REJECT_ATR = 0.30
SAFETY_ATR = 0.50
MAX_HOLD_BARS = 200


def nearest_below(sorted_prices, x):
    idx = bisect.bisect_left(sorted_prices, x)
    return sorted_prices[idx - 1] if idx > 0 else None


def nearest_above(sorted_prices, x):
    idx = bisect.bisect_right(sorted_prices, x)
    return sorted_prices[idx] if idx < len(sorted_prices) else None


def build_multilevel_signals(close, high, low, atr, n):
    is_low, is_high = find_fractals(high, low, FRACTAL_K)
    lo_events = sorted([(i + FRACTAL_K, low[i]) for i in np.where(is_low)[0] if i + FRACTAL_K < n])
    hi_events = sorted([(i + FRACTAL_K, high[i]) for i in np.where(is_high)[0] if i + FRACTAL_K < n])

    nearest_support = np.full(n, np.nan)
    nearest_resistance = np.full(n, np.nan)
    lo_pool, hi_pool = [], []   # kept sorted by price (bisect.insort)
    lo_order, hi_order = [], []  # confirm order, to evict oldest when pool full
    li, hi_i = 0, 0
    for i in range(n):
        while li < len(lo_events) and lo_events[li][0] == i:
            price = lo_events[li][1]
            bisect.insort(lo_pool, price)
            lo_order.append(price)
            if len(lo_order) > POOL_SIZE:
                oldest = lo_order.pop(0)
                pos = bisect.bisect_left(lo_pool, oldest)
                if pos < len(lo_pool) and lo_pool[pos] == oldest:
                    lo_pool.pop(pos)
            li += 1
        while hi_i < len(hi_events) and hi_events[hi_i][0] == i:
            price = hi_events[hi_i][1]
            bisect.insort(hi_pool, price)
            hi_order.append(price)
            if len(hi_order) > POOL_SIZE:
                oldest = hi_order.pop(0)
                pos = bisect.bisect_left(hi_pool, oldest)
                if pos < len(hi_pool) and hi_pool[pos] == oldest:
                    hi_pool.pop(pos)
            hi_i += 1
        c = close[i]
        nb = nearest_below(lo_pool, c)
        na = nearest_above(hi_pool, c)
        if nb is not None:
            nearest_support[i] = nb
        if na is not None:
            nearest_resistance[i] = na
    return nearest_support, nearest_resistance


def build_triggers(close, high, low, atr, nearest_support, nearest_resistance, n):
    def touched_and_rejected(i, is_buy):
        if np.isnan(atr[i]) or atr[i] <= 0:
            return False
        lvl = nearest_support[i] if is_buy else nearest_resistance[i]
        if np.isnan(lvl):
            return False
        tol = TOUCH_TOL_ATR * atr[i]
        rej = REJECT_ATR * atr[i]
        touched = False
        for j in range(max(0, i - LOOKBACK_BARS + 1), i + 1):
            if is_buy and low[j] <= lvl + tol:
                touched = True; break
            if (not is_buy) and high[j] >= lvl - tol:
                touched = True; break
        if not touched:
            return False
        return (close[i] - lvl >= rej) if is_buy else (lvl - close[i] >= rej)

    buy_raw = np.array([touched_and_rejected(i, True) for i in range(n)])
    sell_raw = np.array([touched_and_rejected(i, False) for i in range(n)])
    buy_edge = buy_raw & ~np.concatenate(([False], buy_raw[:-1]))
    sell_edge = sell_raw & ~np.concatenate(([False], sell_raw[:-1]))
    events = [(i, 1.0) for i in np.where(buy_edge)[0]] + [(i, -1.0) for i in np.where(sell_edge)[0]]
    events.sort(key=lambda e: e[0])
    return events


def sim_range_trade(events, close, high, low, spread, atr, nearest_support, nearest_resistance, n):
    trades = []
    last_exit = -1
    skipped = 0
    for i, d in events:
        if i < last_exit:
            skipped += 1
            continue
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        is_buy = d > 0
        target = nearest_resistance[i] if is_buy else nearest_support[i]
        touched_lvl = nearest_support[i] if is_buy else nearest_resistance[i]
        if np.isnan(target) or np.isnan(touched_lvl):
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry = raw + sc if is_buy else raw - sc
        sl = touched_lvl - SAFETY_ATR * atr[i] if is_buy else touched_lvl + SAFETY_ATR * atr[i]
        cap = min(fill_i + MAX_HOLD_BARS, n)
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy:
                if high[kk] >= target: exit_bar, exit_px = kk, target; break
                if low[kk] <= sl: exit_bar, exit_px = kk, sl; break
            else:
                if low[kk] <= target: exit_bar, exit_px = kk, target; break
                if high[kk] >= sl: exit_bar, exit_px = kk, sl; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades, skipped


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    time = df5["time"].values

    print("building multi-level swing structure (k=5 fractal, rolling pool of 60/side)...")
    nearest_support, nearest_resistance = build_multilevel_signals(close, high, low, atr, n)
    dist_to_target = np.nanmedian(np.abs(nearest_resistance - nearest_support))
    print(f"median support-resistance gap at any bar: {dist_to_target:.2f} (vs old single-level 3-day range, "
          f"typically much wider)\n")

    events = build_triggers(close, high, low, atr, nearest_support, nearest_resistance, n)
    print(f"n_bars={n} (~{n/288:.0f} trading days), {len(events)} multi-level rejection triggers "
          f"-> {len(events)/(n/288):.3f}/day\n")

    trades, skipped = sim_range_trade(events, close, high, low, spread, atr, nearest_support, nearest_resistance, n)
    print("=" * 70)
    if not trades:
        print("0 trades"); sys.exit(0)
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    holds = np.array([t[1] - t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    print(f"n={len(trades)} (skipped {skipped} overlaps) net={net:.2f} win%={100*(pnls>0).mean():.1f} "
          f"pf={pf:.3f} median_hold={np.median(holds)*5:.0f}min mean_hold={holds.mean()*5/60:.1f}h")
    if net > 0:
        print(f"closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")

    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    print("\nwalk-forward:")
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

    print(f"\nrandom-direction control (real net={net:.2f}):")
    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(events))
        rev = [(i, d) for (i, _), d in zip(events, rdirs)]
        rev.sort(key=lambda e: e[0])
        trades_r, _ = sim_range_trade(rev, close, high, low, spread, atr, nearest_support, nearest_resistance, n)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < net).mean()
    print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")
