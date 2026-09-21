"""
User's ask: more confluence to cut losing trades, not another entry-
timing/exit tweak. Genuinely untested idea (S/R already uses H4-derived
DAILY levels, but never H4 TREND direction): require the H4 trend to
agree with the M5 entry direction - trade only with the bigger picture.
A standard, well-established real-world confluence idea that hasn't
been checked for Meridian at all yet.

H4 trend = H4 close vs H4 EMA(N), swept over a few N. Each M5 bar maps
to the LAST FULLY-CLOSED H4 bar as of that bar's time (H4 bars open on
the 'time' column per this project's convention, so a bar closes at
time+4H - an M5 bar can only see H4 bars whose close time is <= its own
time, no lookahead).

Layered on top of the shipped v1.02 base (21/50 cross, 250 SMA + VWAP +
S/R confirm, safety_sl=2.5xATR).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m5_stack_variants_fixed_test import sim_filtered_entries
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
SAFETY_SL = 2.5
MIN_SR = 0.50


def map_h4_trend_to_m5(df5, h4, h4_ema_period):
    h4c = h4.copy()
    h4c["h4_ema"] = E.ma(h4c["close"].values.astype(float), h4_ema_period, "ema")
    h4c["h4_trend_up"] = h4c["close"].values > h4c["h4_ema"]
    h4c["close_time"] = h4c["time"] + pd.Timedelta(hours=4)
    h4c = h4c.sort_values("close_time")

    m5 = df5[["time"]].copy().sort_values("time")
    merged = pd.merge_asof(m5, h4c[["close_time", "h4_trend_up"]],
                            left_on="time", right_on="close_time", direction="backward")
    return merged["h4_trend_up"].values


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    m21 = E.ma(close, 21, "ema")
    m50 = E.ma(close, 50, "ema")
    m_confirm = E.ma(close, 250, "sma")

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    raw_events = sorted([(i, 1.0) for i in np.where(above & ~above_prev)[0]] +
                         [(i, -1.0) for i in np.where((~above) & above_prev)[0]], key=lambda e: e[0])

    cond_confirm = close > m_confirm
    cond_vwap = close > vwap
    base_ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        cc = cond_confirm[i] if d > 0 else (not cond_confirm[i])
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if np.isnan(m_confirm[i]) or not (cc and cv):
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        base_ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    print("=" * 70)
    print("shipped v1.02 baseline for reference: net=3432.72 pf=1.357 floatDD%=11.1 "
          "walk-forward=5/5 win%=25.1\n")

    for h4_ema_period in (20, 50, 100, 200):
        h4_trend_up = map_h4_trend_to_m5(df5, h4, h4_ema_period)
        ok = np.zeros(n, dtype=bool)
        for i, d in raw_events:
            if not base_ok[i] or h4_trend_up[i] is None or (isinstance(h4_trend_up[i], float) and np.isnan(h4_trend_up[i])):
                continue
            agree = bool(h4_trend_up[i]) if d > 0 else (not bool(h4_trend_up[i]))
            ok[i] = base_ok[i] and agree

        trades = sim_filtered_entries(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL)
        print(f"\n--- H4 trend filter, EMA({h4_ema_period}) ({ok.sum()} entries, "
              f"{100*ok.sum()/base_ok.sum():.0f}% of baseline kept) ---")
        if not trades:
            print("  0 trades"); continue
        pnls = np.array([t[2] for t in trades])
        entries = np.array([t[0] for t in trades])
        gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
        pf = gw / gl if gl > 0 else float("inf")
        closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
        print(f"  n={len(trades)} net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f}")
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
