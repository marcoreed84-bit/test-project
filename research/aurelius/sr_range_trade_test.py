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
touched level by SAFETY_ATR, time cap = MAX_HOLD_BARS (200 bars /
~16.7h, matching this session's own finding that the top winning
Meridian trades had a median natural leg length of ~16.7h - reused
as a principled cap, not an arbitrary one). Whichever comes first.
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


def sim_range_trade(events, close, high, low, spread, atr, sr_hi, sr_lo, n):
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
        target = sr_hi[i] if is_buy else sr_lo[i]
        touched_lvl = sr_lo[i] if is_buy else sr_hi[i]
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
    sr_hi, sr_lo = ctx["sr_hi"], ctx["sr_lo"]
    time = df5["time"].values

    events = build_range_bounce_triggers(ctx)
    print(f"n_bars={n} (~{n/288:.0f} trading days), {len(events)} support/resistance "
          f"rejection triggers -> {len(events)/(n/288):.3f}/day\n")

    trades, skipped = sim_range_trade(events, close, high, low, spread, atr, sr_hi, sr_lo, n)
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
        trades_r, _ = sim_range_trade(rev, close, high, low, spread, atr, sr_hi, sr_lo, n)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < net).mean()
    print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")
