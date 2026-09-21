"""
User's ask: test variations of the moving-average stack visible on the
real Aurelius M5 chart - 150 EMA, VWAP, 50 EMA, 21 EMA (top-to-bottom in
the current downtrend, i.e. close < 21 < 50 < VWAP < 150 there) -
against the two winning hold-to-reversal candidates found so far (21/50
EMA cross, safety_sl=3.0xATR, net=2812.02, 99.7th pct, 3/5 blocks; 21
EMA/VWAP cross, safety_sl=5.0xATR, net=2575.83, 98.3th pct, 4/5 blocks).

Rather than building yet another independent fixed-TP/SL system (the
session already found hold-to-reversal beats that repeatedly), this
tests the wider stack as a CONFIRMATION FILTER on the two existing
winners: only take the cross when the additional line(s) also agree on
direction at that exact bar. This directly answers "different
variations of the moving averages" against constructions already known
to work, rather than starting over.

Filters tested, each applied separately to BOTH base crosses:
  +150      : close vs 150 EMA agrees with the cross direction
  +VWAP     : close vs VWAP agrees (only applied to the 21/50 base -
              redundant on the 21/VWAP base, which already uses VWAP)
  +50       : close vs 50 EMA agrees (only applied to the 21/VWAP base -
              redundant on the 21/50 base)
  +150+VWAP : both agree (21/50 base only)
  +150+50   : both agree (21/VWAP base only)

Same rigor: real M5 data, real spread, correct single-position
sequencing (filtering only REMOVES events, entries stay a subset of an
already-alternating sequence so no new overlap risk), random-direction
control re-run per filtered event count (not reused from the
unfiltered baseline - the null distribution depends on how many events
survive), walk-forward alongside the aggregate.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from ema21_50_cross_hold_test import sim_cross_to_cross

POINT = E.POINT
N_RANDOM_SEEDS = 300


def apply_filter(events, conditions):
    """conditions: list of boolean arrays, each True where that MA agrees
    with a BUY at that bar - the event's own direction decides which side
    of the condition it must land on."""
    out = []
    for i, d in events:
        ok = True
        for cond in conditions:
            agree = cond[i] if d > 0 else (not cond[i])
            if not agree:
                ok = False
                break
        if ok:
            out.append((i, d))
    return out


def evaluate(label, events, close, high, low, spread, atr, n, time, safety_sl):
    trades = sim_cross_to_cross(events, close, high, low, spread, atr, n, safety_sl)
    print(f"\n--- {label} ({len(events)} events) ---")
    if not trades:
        print("  0 trades"); return
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    cutoff = int(n * 0.7)
    is_net = pnls[entries < cutoff].sum(); oos_net = pnls[entries >= cutoff].sum()
    print(f"  n={len(trades)} net={pnls.sum():.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
          f"IS={is_net:.2f} OOS={oos_net:.2f}")

    rng = np.random.default_rng(0)
    random_nets = []
    for s in range(N_RANDOM_SEEDS):
        rdirs = rng.choice([1.0, -1.0], size=len(events))
        rev = [(i, d) for (i, _), d in zip(events, rdirs)]
        rev.sort(key=lambda e: e[0])
        trades_r = sim_cross_to_cross(rev, close, high, low, spread, atr, n, safety_sl)
        random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
    random_nets = np.array(random_nets)
    pct = 100 * (random_nets < pnls.sum()).mean()
    print(f"  random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")

    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    line = "  walk-forward: "
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            line += f"[b{b+1}: 0] "; continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
        line += f"[b{b+1}: {netb:+.0f}] "
    print(line + f"-> {pos}/5 positive")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    m21, m50, m150, vwap = ctx["m21"], ctx["m50"], ctx["m150"], ctx["vwap"]
    time = df5["time"].values

    above21_50 = m21 > m50
    above21_50_prev = np.concatenate(([False], above21_50[:-1]))
    cross_up_50 = above21_50 & ~above21_50_prev
    cross_dn_50 = (~above21_50) & above21_50_prev
    events_50 = sorted([(i, 1.0) for i in np.where(cross_up_50)[0]] +
                        [(i, -1.0) for i in np.where(cross_dn_50)[0]], key=lambda e: e[0])

    above21_vwap = m21 > vwap
    valid = ~np.isnan(m21) & ~np.isnan(vwap)
    above21_vwap_prev = np.concatenate(([False], above21_vwap[:-1]))
    valid_prev = np.concatenate(([False], valid[:-1]))
    cross_up_v = above21_vwap & ~above21_vwap_prev & valid & valid_prev
    cross_dn_v = (~above21_vwap) & above21_vwap_prev & valid & valid_prev
    events_vwap = sorted([(i, 1.0) for i in np.where(cross_up_v)[0]] +
                          [(i, -1.0) for i in np.where(cross_dn_v)[0]], key=lambda e: e[0])

    cond_150 = close > m150   # True = agrees with a BUY
    cond_vwap = close > vwap
    cond_50 = close > m50

    print("=" * 70)
    print("BASELINE (unfiltered, already committed):")
    evaluate("21/50 cross, safety_sl=3.0xATR", events_50, close, high, low, spread, atr, n, time, 3.0)
    evaluate("21/VWAP cross, safety_sl=5.0xATR", events_vwap, close, high, low, spread, atr, n, time, 5.0)

    print("\n" + "=" * 70)
    print("21/50 BASE + confirmation filters (safety_sl=3.0xATR):")
    evaluate("21/50 +150", apply_filter(events_50, [cond_150]), close, high, low, spread, atr, n, time, 3.0)
    evaluate("21/50 +VWAP", apply_filter(events_50, [cond_vwap]), close, high, low, spread, atr, n, time, 3.0)
    evaluate("21/50 +150+VWAP", apply_filter(events_50, [cond_150, cond_vwap]),
             close, high, low, spread, atr, n, time, 3.0)

    print("\n" + "=" * 70)
    print("21/VWAP BASE + confirmation filters (safety_sl=5.0xATR):")
    evaluate("21/VWAP +150", apply_filter(events_vwap, [cond_150]), close, high, low, spread, atr, n, time, 5.0)
    evaluate("21/VWAP +50", apply_filter(events_vwap, [cond_50]), close, high, low, spread, atr, n, time, 5.0)
    evaluate("21/VWAP +150+50", apply_filter(events_vwap, [cond_150, cond_50]),
             close, high, low, spread, atr, n, time, 5.0)
