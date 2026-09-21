"""
User's idea, directly from a real chart showing price respecting daily
support and resistance (yellow-circled rejections in the screenshot):
trade the REJECTION off support, holding through to resistance (and
the mirror at resistance, targeting support) - a standalone RANGE/
mean-reversion construction, genuinely different from every Meridian
test this session (all of which were 21/50 trend-continuation trades).
Also different from sr_reject_test.py's real, already-tested result
(touch-and-reject as an ENTRY FILTER on Aurelius's trend-following
gate - real result: 181 trades, only 63rd percentile vs a random
same-size draw from the baseline, not statistically real). This is
the rejection ITSELF as the trade, targeting the OPPOSITE level, not
a confirmation for a different system's entries.

Levels: engine.build_context's real sr_hi/sr_lo (trailing 3 completed
D1 bars' high/low, matching Aurelius's own SRDistanceATR() construction
exactly - not reinvented).

Signal: price touches/tests a level within TOUCH_TOL_ATR over the
trailing LOOKBACK_BARS, then closes back away from it by REJECT_ATR -
same touched_and_rejected() logic as sr_reject_test.py, reused rather
than reimplemented, but used here as the TRIGGER itself (buy off
sr_lo, sell off sr_hi), not as a filter on a different signal.

Exit: target = the OPPOSITE level, safety stop = re-break past the
touched level by SAFETY_ATR, time cap = MAX_HOLD_BARS.

CORRECTION: the original 200-bar (~16.7h) cap was a real mistake -
reused from an unrelated number (median natural LEG length of
Meridian's top TREND trades) without checking it against what THIS
construction actually needs. Diagnostic on the original run: median
hold for winning trades was EXACTLY 200 bars - the cap itself - and
200 of 207 "wins" (96.6%) were timeouts, not real target hits; only
7 of 1487 trades (0.5%) ever actually reached the opposite S/R level.
The median real range width (sr_hi - sr_lo) is $64.99 - a genuine,
tradeable distance (consistent with the ~$164 support-to-resistance
move in the user's own chart) - but 16.7 hours is nowhere near enough
time for gold to travel it; the user's own chart example took ~6 days.
Fixed below with a realistic multi-day cap swept properly instead of
guessed once. Whichever exit (target/stop/timeout) comes first.
Correct single-position sequencing (buy/sell rejection triggers are
NOT inherently alternating like an MA cross, so this is enforced
explicitly).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
N_RANDOM_SEEDS = 300
LOOKBACK_BARS = 12
TOUCH_TOL_ATR = 0.30
REJECT_ATR = 0.30
SAFETY_ATR = 0.50
MAX_HOLD_BARS = 200


def build_range_bounce_triggers(ctx):
    """BOUNCE logic, NOT sr_reject_test.py's breakout-retest logic (that
    function deliberately uses the RESISTANCE level for buys - a price-
    already-broke-above-it-and-is-retesting-from-above pattern, wrong
    for this construction). Here: buy bounces UP off SUPPORT (sr_lo),
    sell bounces DOWN off RESISTANCE (sr_hi) - the opposite level
    mapping, matching "trade the rejection of support, target
    resistance" as actually described. Edge-triggered: fires once per
    fresh rejection, not every bar the condition stays true."""
    n = ctx["n"]
    atr, low, high, close = ctx["atr"], ctx["low"], ctx["high"], ctx["close"]
    sr_hi, sr_lo = ctx["sr_hi"], ctx["sr_lo"]

    def touched_and_rejected_from(i, is_buy):
        if np.isnan(atr[i]) or atr[i] <= 0:
            return False
        lvl = sr_lo[i] if is_buy else sr_hi[i]   # support for buys, resistance for sells
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

    buy_raw = np.array([touched_and_rejected_from(i, True) for i in range(n)])
    sell_raw = np.array([touched_and_rejected_from(i, False) for i in range(n)])
    buy_edge = buy_raw & ~np.concatenate(([False], buy_raw[:-1]))
    sell_edge = sell_raw & ~np.concatenate(([False], sell_raw[:-1]))
    events = [(i, 1.0) for i in np.where(buy_edge)[0]] + [(i, -1.0) for i in np.where(sell_edge)[0]]
    events.sort(key=lambda e: e[0])
    return events


def sim_range_trade(events, close, high, low, spread, atr, sr_hi, sr_lo, n, max_hold_bars=MAX_HOLD_BARS):
    trades = []
    last_exit = -1
    skipped = 0
    timeouts = 0
    for i, d in events:
        if i < last_exit:
            skipped += 1
            continue
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        is_buy = d > 0
        target = sr_hi[i] if is_buy else sr_lo[i]
        touched_lvl = sr_lo[i] if is_buy else sr_hi[i]
        if np.isnan(target) or np.isnan(touched_lvl):
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry = raw + sc if is_buy else raw - sc
        sl = touched_lvl - SAFETY_ATR * atr[i] if is_buy else touched_lvl + SAFETY_ATR * atr[i]
        cap = min(fill_i + max_hold_bars, n)
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
            timeouts += 1
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades, skipped, timeouts


def evaluate(label, events, close, high, low, spread, atr, sr_hi, sr_lo, n, time, max_hold_bars,
             run_control=False):
    print(f"\n--- {label} ---")
    trades, skipped, timeouts = sim_range_trade(events, close, high, low, spread, atr, sr_hi, sr_lo, n,
                                                 max_hold_bars=max_hold_bars)
    if not trades:
        print("  0 trades"); return None
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    holds = np.array([t[1] - t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    print(f"  n={len(trades)} (skipped {skipped} overlaps, {timeouts} timeouts={100*timeouts/len(trades):.1f}%) "
          f"net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
          f"median_hold={np.median(holds)*5/60:.1f}h mean_hold={holds.mean()*5/60:.1f}h")
    if net > 0:
        print(f"  closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")

    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        if m.sum() == 0: continue
        if pnls[m].sum() > 0: pos += 1
    print(f"  walk-forward: {pos}/5 blocks positive")

    if run_control:
        rng = np.random.default_rng(0)
        random_nets = []
        for s in range(N_RANDOM_SEEDS):
            rdirs = rng.choice([1.0, -1.0], size=len(events))
            rev = [(i, d) for (i, _), d in zip(events, rdirs)]
            rev.sort(key=lambda e: e[0])
            trades_r, _, _ = sim_range_trade(rev, close, high, low, spread, atr, sr_hi, sr_lo, n,
                                              max_hold_bars=max_hold_bars)
            random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
        random_nets = np.array(random_nets)
        pct = 100 * (random_nets < net).mean()
        print(f"  random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")
    return dict(label=label, n=len(trades), net=net, pf=pf, timeouts=timeouts)


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    sr_hi, sr_lo = ctx["sr_hi"], ctx["sr_lo"]
    time = df5["time"].values

    events = build_range_bounce_triggers(ctx)
    print(f"n_bars={n} (~{n/288:.0f} trading days), {len(events)} support/resistance "
          f"rejection triggers -> {len(events)/(n/288):.3f}/day\n")
    print("for reference, the original (broken) 16.7h cap gave net=-547.69, "
          "96.6% of 'wins' were actually timeouts, only 0.5% of all trades reached the real target\n")

    print("=" * 70)
    print("realistic multi-day hold caps:")
    results = []
    # bars: 3d=864, 7d=2016, 14d=4032, 21d=6048, 30d=8640 (288 M5 bars/trading day)
    for days, bars in ((3, 864), (7, 2016), (14, 4032), (21, 6048), (30, 8640)):
        r = evaluate(f"max_hold={days}d ({bars} bars)", events, close, high, low, spread, atr,
                     sr_hi, sr_lo, n, time, bars)
        if r: results.append(r)

    print("\n" + "=" * 70)
    print("SUMMARY:")
    for r in sorted(results, key=lambda r: -r["net"]):
        print(f"  {r['label']:<24} net={r['net']:9.2f} pf={r['pf']:.3f} timeouts={100*r['timeouts']/r['n']:5.1f}%  n={r['n']}")

    day_bars = {(f"max_hold={d}d ({b} bars)"): b for d, b in ((3, 864), (7, 2016), (14, 4032), (21, 6048), (30, 8640))}
    best = max(results, key=lambda r: r["net"]) if results else None
    if best:
        print(f"\nfull random-direction control on best ({best['label']}):")
        evaluate(best["label"], events, close, high, low, spread, atr,
                 sr_hi, sr_lo, n, time, day_bars[best["label"]], run_control=True)
