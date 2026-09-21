"""
User's idea: "fan trendlines" - the classical three-line fan principle
(Edwards & Magee). Genuinely different mechanic from trendline_break_
test.py's validated single-line construction (which just tracks the
last TWO swing points and updates continuously). A fan keeps the
ORIGIN fixed (the swing extreme that started the trend) and draws
successive lines from that SAME origin out to each new, shallower
swing point as price keeps failing to reverse. The classical signal is
the break of the THIRD such line, not the first - each break increases
confidence rather than being a signal on its own.

State machine (bearish fan shown, for reversal-to-long signals -
mirrored for bullish fan / reversal-to-short):
  - origin = the highest confirmed swing high seen since the last
    reset. Resets (fresh downtrend, fan restarts) whenever an even
    HIGHER high forms.
  - anchor = the most recent LOWER swing high used to draw the
    CURRENT active fan line (origin -> anchor).
  - break_count = how many distinct fan lines (origin -> some anchor)
    have been broken (price closed back above that line) in sequence.
  - On each new bar: if price closes above the active line and this
    anchor's break hasn't been counted yet, increment break_count and
    mark this anchor "used" (waiting for the NEXT lower high to define
    the next, shallower line).
  - Signal fires when break_count reaches 3 (the classical "third
    line" confirmation).

Same swing detection (k-bar fractal) already validated this session,
same hold-to-reversal exit style that's worked throughout, same rigor:
real M5 data/spread, correct single-position sequencing, drawdown,
walk-forward, random-direction control.
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


def build_fan_events(high, low, close, n, fractal_k, break_target=3):
    is_low, is_high = find_fractals(high, low, fractal_k)
    hi_events = sorted([(i + fractal_k, i, high[i]) for i in np.where(is_high)[0] if i + fractal_k < n])
    lo_events = sorted([(i + fractal_k, i, low[i]) for i in np.where(is_low)[0] if i + fractal_k < n])

    events = []

    # --- bearish fan: origin=highest high, anchors=successive lower
    # highs, break = close crosses ABOVE the active line -> eventual BUY
    origin = None          # (bar, price)
    anchor = None           # (bar, price) - current active anchor
    break_count = 0
    anchor_broken = False   # has the CURRENT anchor's line been broken yet
    hii = 0

    # --- bullish fan: origin=lowest low, anchors=successive higher
    # lows, break = close crosses BELOW the active line -> eventual SELL
    originL = None
    anchorL = None
    break_countL = 0
    anchor_brokenL = False
    li = 0

    for i in range(n):
        # --- process new confirmed swing highs (bearish fan side) ---
        while hii < len(hi_events) and hi_events[hii][0] == i:
            _, form_bar, price = hi_events[hii]
            hii += 1
            if origin is None or price > origin[1]:
                origin, anchor, break_count, anchor_broken = (form_bar, price), None, 0, False
            elif anchor is None:
                anchor = (form_bar, price)
            elif price < anchor[1] and anchor_broken:
                anchor = (form_bar, price)
                anchor_broken = False

        # --- process new confirmed swing lows (bullish fan side) ---
        while li < len(lo_events) and lo_events[li][0] == i:
            _, form_bar, price = lo_events[li]
            li += 1
            if originL is None or price < originL[1]:
                originL, anchorL, break_countL, anchor_brokenL = (form_bar, price), None, 0, False
            elif anchorL is None:
                anchorL = (form_bar, price)
            elif price > anchorL[1] and anchor_brokenL:
                anchorL = (form_bar, price)
                anchor_brokenL = False

        # --- check breaks on the bearish fan (price closing ABOVE the active line) ---
        if origin is not None and anchor is not None and not anchor_broken:
            b1, p1 = origin; b2, p2 = anchor
            if b2 > b1:
                slope = (p2 - p1) / (b2 - b1)
                line_val = p2 + slope * (i - b2)
                if close[i] > line_val:
                    anchor_broken = True
                    break_count += 1
                    if break_count >= break_target:
                        events.append((i, 1.0))
                        origin, anchor, break_count, anchor_broken = None, None, 0, False

        # --- check breaks on the bullish fan (price closing BELOW the active line) ---
        if originL is not None and anchorL is not None and not anchor_brokenL:
            b1, p1 = originL; b2, p2 = anchorL
            if b2 > b1:
                slope = (p2 - p1) / (b2 - b1)
                line_val = p2 + slope * (i - b2)
                if close[i] < line_val:
                    anchor_brokenL = True
                    break_countL += 1
                    if break_countL >= break_target:
                        events.append((i, -1.0))
                        originL, anchorL, break_countL, anchor_brokenL = None, None, 0, False

    events.sort(key=lambda e: e[0])
    return events


def sim_fan_hold(events, close, high, low, spread, atr, n, safety_sl_atr):
    """IMPORTANT FIX: a trade still open when the data runs out (no more
    opposite-fan-break events available, cap defaults to n) is EXCLUDED
    from returned trades entirely - found via a real artifact where the
    single best "trade" in every top config was the SAME position,
    entered mid-2024, that only "exited" because the dataset ended in
    Aug 2026, capturing the entire remaining bull run for free. A real
    account would still be holding that position today with unknown
    future risk, not miraculously exited at the best available price -
    counting it as a realized win overstated every result in this file
    (removing it flipped every "best" config from positive to flat/
    negative). Still-open positions are the standard exclusion in any
    correct backtest; this was missing before."""
    trades = []
    last_exit = -1
    skipped = 0
    excluded_open = 0
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
        cap = n
        has_opposite_cap = False
        for j in range(idx + 1, len(events)):
            if events[j][1] != d:
                cap = min(events[j][0] + 1, n)
                has_opposite_cap = True
                break
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
        if exit_bar is None:
            if not has_opposite_cap or cap >= n - 1:
                # no real opposite signal arrived (or it lands on the very
                # last bar) before the data ran out - still open, exclude
                excluded_open += 1
                last_exit = cap
                continue
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades, skipped, excluded_open


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]

    print("=" * 70)
    print("sweeping fractal window x safety stop for the 3-line fan construction:")
    results = []
    for k in (15, 25, 40, 60, 100):
        events = build_fan_events(high, low, close, n, k)
        print(f"\nk={k}: {len(events)} fan-break (3rd line) events -> {len(events)/(n/288):.3f}/day")
        for sl in (2.0, 3.0, 4.0):
            trades, skipped, excluded_open = sim_fan_hold(events, close, high, low, spread, atr, n, sl)
            if not trades:
                print(f"  sl={sl}: 0 trades (excluded {excluded_open} still-open)"); continue
            pnls = np.array([t[2] for t in trades])
            gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
            pf = gw / gl if gl > 0 else float("inf")
            closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
            dd_str = f"floatDD%={100*float_dd/net:.1f}" if net > 0 else "net<=0"
            print(f"  sl={sl}xATR: n={len(trades)} (excl {excluded_open} still-open) net={net:9.2f} "
                  f"win%={100*(pnls>0).mean():.1f} pf={pf:.3f} {dd_str}")
            results.append((k, sl, net, pf, len(trades)))

    print("\n" + "=" * 70)
    print("SUMMARY (top 8 by net):")
    for k, sl, net, pf, ntr in sorted(results, key=lambda x: -x[2])[:8]:
        print(f"  k={k:3d} sl={sl}xATR: net={net:9.2f} pf={pf:.3f} n={ntr}")
