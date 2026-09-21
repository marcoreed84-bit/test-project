"""
User's ask: can the walk-forward get to 5/5 blocks. Block 1 (2023-01 to
2023-09) has been the one losing/weak block across EVERY construction
tested this session, including Aurelius's own real, already-validated
year-by-year numbers (2023: net $76, PF 1.14 - barely positive, the
weakest year in the whole dataset). That's independent confirmation
this is a genuine low-volatility/non-trending regime in the data, not
an artifact of any one signal - so the honest way to chase 5/5 is a
real trend-STRENGTH regime filter (sit out when the market isn't
trending, in ANY period, by the same rule every time), not a parameter
hand-picked to flip block 1 positive - that would be reverse-
engineering to the test set, exactly the kind of snooping this project
has been careful to avoid all session.

ADX(14), Wilder's original trend-strength indicator, is not yet in
engine.py - implemented here the standard way (Wilder-smoothed +DM/-DM/
TR via engine.smma, matching the smoothing convention already used for
ATR elsewhere in this codebase). Requires ADX >= threshold at the
moment of the (already 150+VWAP-confirmed) 21/50 cross - the session's
best candidate so far (net=3114.71, PF=1.249, 99.7th pct, 4/5 blocks,
safety_sl=3.0xATR) - to take the trade at all.

Sweeps the ADX threshold and reports the FULL walk-forward for each,
not just whichever one happens to hit 5/5 - if none does, that's the
honest answer, not a reason to keep hunting until one does.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from ema21_50_cross_hold_test import sim_cross_to_cross
from m5_stack_variants_test import apply_filter

POINT = E.POINT
N_RANDOM_SEEDS = 300
SAFETY_SL = 3.0


def wilder_adx(high, low, close, period=14):
    n = len(close)
    up_move = np.zeros(n)
    down_move = np.zeros(n)
    up_move[1:] = high[1:] - high[:-1]
    down_move[1:] = low[:-1] - low[1:]
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = np.full(n, np.nan)
    tr[0] = high[0] - low[0]
    tr[1:] = np.maximum(high[1:] - low[1:],
                         np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))

    atr_s = E.smma(tr, period)
    plus_dm_s = E.smma(plus_dm, period)
    minus_dm_s = E.smma(minus_dm, period)

    with np.errstate(invalid="ignore", divide="ignore"):
        plus_di = 100.0 * plus_dm_s / atr_s
        minus_di = 100.0 * minus_dm_s / atr_s
        dx = 100.0 * np.abs(plus_di - minus_di) / (plus_di + minus_di)

    adx = np.full(n, np.nan)
    valid = ~np.isnan(dx)
    if valid.any():
        first = int(np.argmax(valid))
        adx[first:] = E.smma(dx[first:], period)
    return adx


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    m21, m50, m150, vwap = ctx["m21"], ctx["m50"], ctx["m150"], ctx["vwap"]
    time = df5["time"].values

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    cross_up = above & ~above_prev
    cross_dn = (~above) & above_prev
    events = sorted([(i, 1.0) for i in np.where(cross_up)[0]] +
                     [(i, -1.0) for i in np.where(cross_dn)[0]], key=lambda e: e[0])
    cond_150 = close > m150
    cond_vwap = close > vwap
    base_events = apply_filter(events, [cond_150, cond_vwap])

    adx = wilder_adx(high, low, close, 14)
    print(f"ADX(14): median={np.nanmedian(adx):.1f} p25={np.nanpercentile(adx[~np.isnan(adx)],25):.1f} "
          f"p50={np.nanpercentile(adx[~np.isnan(adx)],50):.1f} p75={np.nanpercentile(adx[~np.isnan(adx)],75):.1f}\n")

    print("=" * 70)
    print(f"baseline (150+VWAP-confirmed 21/50 cross, no ADX filter): {len(base_events)} events")

    for thresh in (0, 15, 20, 25, 30, 35, 40):
        cond_adx = ~np.isnan(adx) & (adx >= thresh)
        events_f = [(i, d) for i, d in base_events if cond_adx[i]]
        trades = sim_cross_to_cross(events_f, close, high, low, spread, atr, n, SAFETY_SL)
        print(f"\n--- ADX >= {thresh} ({len(events_f)} events, "
              f"{100*len(events_f)/len(base_events):.0f}% of baseline kept) ---")
        if not trades:
            print("  0 trades"); continue
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
            rdirs = rng.choice([1.0, -1.0], size=len(events_f))
            rev = [(i, d) for (i, _), d in zip(events_f, rdirs)]
            rev.sort(key=lambda e: e[0])
            trades_r = sim_cross_to_cross(rev, close, high, low, spread, atr, n, SAFETY_SL)
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
                line += f"[b{b+1}: 0trades] "; continue
            netb = pnls[m].sum()
            if netb > 0: pos += 1
            line += f"[b{b+1}: {netb:+.0f} n={nb}] "
        print(line + f"-> {pos}/5 positive")
