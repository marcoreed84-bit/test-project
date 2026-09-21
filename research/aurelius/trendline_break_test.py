"""
User's chart (Sep 18-21 2026, Aurelius): a descending trendline drawn
through consecutive lower highs (marked LH), price approaching/testing
it from below. Genuinely different construct from every S/R test this
session so far - those were all HORIZONTAL levels; this is a DIAGONAL
line connecting swing points, extrapolated forward. My interpretation
(stated explicitly since this is a new, expensive-to-build construction
and I'd rather flag the read than guess wrong silently): trade the
BREAKOUT when price closes back above a descending trendline built
from the last two confirmed lower highs - a bullish continuation
signal - and the mirror (ascending trendline through higher lows,
trade the breakdown below it) for shorts.

Swing points: same k=5 fractal detection already validated earlier
this session (structure_turn_test.py's find_fractals) - reused, not
reinvented. Trendline = straight line through the last TWO confirmed
swing highs (for the descending/LH case) or two confirmed swing lows
(ascending/HL case), extrapolated forward bar-by-bar via its own
slope. Only counts as a genuine "lower highs" trendline when the
second high actually IS lower than the first (mirror for lows) -
otherwise there's no trendline to break in the direction implied.

Exit: hold until the trendline itself flips (the opposite trendline
produces its own breakout) or a wide ATR safety stop, matching the
exit style that worked best for Meridian (this is a trend-continuation
signal, not a range/target trade like the S/R rejection tests) - NOT
copied from the S/R construction's target-based exit, which was a
different kind of trade (range/reversion) than this (trend/breakout).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from structure_turn_test import find_fractals
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
N_RANDOM_SEEDS = 300
FRACTAL_K = 5
SAFETY_ATR = 3.0


def build_trendline_values(high, low, n, fractal_k=FRACTAL_K):
    """Returns (desc_line, asc_line): per-bar extrapolated trendline value
    from the last two confirmed swing highs (descending, for LH breakouts)
    and last two confirmed swing lows (ascending, for HL breakdowns).
    NaN where fewer than 2 confirmed swings exist yet, or where the
    swing sequence doesn't actually form the implied slope direction."""
    is_low, is_high = find_fractals(high, low, fractal_k)
    lo_events = sorted([(i + fractal_k, i, low[i]) for i in np.where(is_low)[0] if i + fractal_k < n])
    hi_events = sorted([(i + fractal_k, i, high[i]) for i in np.where(is_high)[0] if i + fractal_k < n])

    desc_line = np.full(n, np.nan)
    asc_line = np.full(n, np.nan)

    prev_hi, cur_hi = None, None   # (formation_bar, price)
    prev_lo, cur_lo = None, None
    li, hii = 0, 0
    for i in range(n):
        while hii < len(hi_events) and hi_events[hii][0] == i:
            _, form_bar, price = hi_events[hii]
            prev_hi, cur_hi = cur_hi, (form_bar, price)
            hii += 1
        while li < len(lo_events) and lo_events[li][0] == i:
            _, form_bar, price = lo_events[li]
            prev_lo, cur_lo = cur_lo, (form_bar, price)
            li += 1

        if prev_hi is not None and cur_hi is not None and cur_hi[1] < prev_hi[1]:
            b1, p1 = prev_hi; b2, p2 = cur_hi
            slope = (p2 - p1) / (b2 - b1)
            desc_line[i] = p2 + slope * (i - b2)
        if prev_lo is not None and cur_lo is not None and cur_lo[1] > prev_lo[1]:
            b1, p1 = prev_lo; b2, p2 = cur_lo
            slope = (p2 - p1) / (b2 - b1)
            asc_line[i] = p2 + slope * (i - b2)
    return desc_line, asc_line


def build_breakout_events(close, desc_line, asc_line, n):
    above_desc = close > desc_line
    below_asc = close < asc_line
    valid_desc = ~np.isnan(desc_line)
    valid_asc = ~np.isnan(asc_line)

    above_desc_prev = np.concatenate(([False], above_desc[:-1]))
    valid_desc_prev = np.concatenate(([False], valid_desc[:-1]))
    buy_edge = above_desc & ~above_desc_prev & valid_desc & valid_desc_prev

    below_asc_prev = np.concatenate(([False], below_asc[:-1]))
    valid_asc_prev = np.concatenate(([False], valid_asc[:-1]))
    sell_edge = below_asc & ~below_asc_prev & valid_asc & valid_asc_prev

    events = [(i, 1.0) for i in np.where(buy_edge)[0]] + [(i, -1.0) for i in np.where(sell_edge)[0]]
    events.sort(key=lambda e: e[0])
    return events


def sim_trendline_hold(events, close, high, low, spread, atr, n, safety_sl_atr=SAFETY_ATR):
    """Hold-to-reversal exit (matches Meridian's best-performing style),
    correct single-position sequencing."""
    trades = []
    last_exit = -1
    skipped = 0
    for idx, (i, d) in enumerate(events):
        if i < last_exit:
            skipped += 1
            continue
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        is_buy = d > 0
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry = raw + sc if is_buy else raw - sc
        sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
        # cap = next OPPOSITE-direction event (the reversal), not just the next event
        cap = n
        for j in range(idx + 1, len(events)):
            if events[j][1] != d:
                cap = min(events[j][0] + 1, n)
                break
        exit_bar, exit_px = None, None
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
        last_exit = exit_bar
    return trades, skipped


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    time = df5["time"].values

    print("building diagonal trendlines from k=5 fractal swings...")
    desc_line, asc_line = build_trendline_values(high, low, n)
    events = build_breakout_events(close, desc_line, asc_line, n)
    print(f"n_bars={n} (~{n/288:.0f} trading days), {len(events)} trendline-breakout events "
          f"-> {len(events)/(n/288):.3f}/day\n")

    print("=" * 70)
    for sl in (1.5, 2.0, 3.0, 4.0, 5.0):
        trades, skipped = sim_trendline_hold(events, close, high, low, spread, atr, n, sl)
        if not trades:
            print(f"sl={sl}xATR: 0 trades"); continue
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        holds = np.array([t[1] - t[0] for t in trades])
        gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
        print(f"\n--- safety_sl={sl}xATR ---")
        print(f"n={len(trades)} (skipped {skipped}) net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
              f"median_hold={np.median(holds)*5/60:.1f}h")
        if net > 0:
            print(f"closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")
        edges = np.linspace(0, n, 6).astype(int)
        pos = 0
        for b in range(5):
            lo, hi = edges[b], edges[b + 1]
            m = (entries >= lo) & (entries < hi)
            if m.sum() == 0: continue
            if pnls[m].sum() > 0: pos += 1
        print(f"walk-forward: {pos}/5 blocks positive")

    # random-direction control + full walk-forward on best cell
    best_net, best_sl = -1e18, None
    for sl in (1.5, 2.0, 3.0, 4.0, 5.0):
        trades, _ = sim_trendline_hold(events, close, high, low, spread, atr, n, sl)
        net = sum(t[2] for t in trades) if trades else -1e18
        if net > best_net:
            best_net, best_sl = net, sl

    print("\n" + "=" * 70)
    print(f"random-direction control on best (safety_sl={best_sl}xATR, real net={best_net:.2f}):")
    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(events))
        rev = [(i, d) for (i, _), d in zip(events, rdirs)]
        rev.sort(key=lambda e: e[0])
        trades_r, _ = sim_trendline_hold(rev, close, high, low, spread, atr, n, best_sl)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < best_net).mean()
    print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")
