"""
User's idea: exit on a faster MA pair (13 EMA crossing 21 EMA) rather
than waiting for the entry pair (21/50) to fully reverse. Genuinely
different mechanic from every exit idea rejected so far this session:
Price21Exit used a fixed price-vs-21-EMA buffer+confirm-bars threshold
(rejected - fired on ordinary noise); entry-breach used a fixed price
level (rejected, same reason); breakeven ratcheted a stop (rejected,
too slow for the real tail-risk trades); fixed TP capped winners
outright (rejected, removed the payoff asymmetry the system depends
on). A 13/21 cross is a discrete two-line CROSSOVER event, not a
continuous distance-from-a-line check - closer in spirit to the entry
signal's own logic, just faster, so it deserves an honest test rather
than an assumption it fails the same way as Price21Exit.

Exit = whichever comes first: the safety stop, a 13/21 EMA cross
against the trade direction, or the next raw 21/50 reversal (kept as
an outer cap in case 13/21 never crosses before that - shouldn't bind
often since 13/21 should almost always resolve first).

Built on the shipped v1.02 entries (21/50 cross, 250 SMA + VWAP + S/R
confirm, safety_sl=2.5xATR). Same real M5 data/spread, correct single-
position sequencing, drawdown (closed + floating) for every variant.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
N_RANDOM_SEEDS = 300
SAFETY_SL = 2.5
MIN_SR = 0.50


def sim_with_fast_ma_exit(raw_events, entry_ok, close, high, low, spread, atr, m_fast, m_exit_ref, n,
                           safety_sl_atr):
    trades = []
    for k in range(len(raw_events) - 1):
        i, d = raw_events[k]
        if not entry_ok[i]:
            continue
        i_next, _ = raw_events[k + 1]
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        is_buy = d > 0
        entry = raw + sc if is_buy else raw - sc
        sl = entry - safety_sl_atr * atr[i] if is_buy else entry + safety_sl_atr * atr[i]
        cap = min(i_next + 1, n)
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
            if kk == 0 or np.isnan(m_fast[kk]) or np.isnan(m_fast[kk - 1]) or \
               np.isnan(m_exit_ref[kk]) or np.isnan(m_exit_ref[kk - 1]):
                continue
            above_now = m_fast[kk] > m_exit_ref[kk]
            above_prev = m_fast[kk - 1] > m_exit_ref[kk - 1]
            if above_now != above_prev:  # a fresh cross just happened
                crossed_up = above_now and not above_prev
                adverse_cross = (not crossed_up) if is_buy else crossed_up
                if adverse_cross:
                    exit_bar, exit_px = kk, close[kk]
                    break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
    return trades


def evaluate(label, trades, close, spread, n):
    print(f"\n--- {label} ---")
    if not trades:
        print("  0 trades"); return None
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    holds = np.array([t[1] - t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    print(f"  n={len(trades)} net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f} "
          f"median_hold={np.median(holds)*5:.0f}min")
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
    return dict(label=label, n=len(trades), net=net, pf=pf, closed_dd=closed_dd, float_dd=float_dd)


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
    ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        cc = cond_confirm[i] if d > 0 else (not cond_confirm[i])
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if np.isnan(m_confirm[i]) or not (cc and cv):
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    print("=" * 70)
    print("shipped v1.02 baseline for reference: net=3432.72 pf=1.357 floatDD%=11.1 "
          "walk-forward=5/5 median_hold~155min\n")

    results = []
    for fast_p, exit_ref_p in ((13, 21), (9, 21), (13, 34), (8, 13), (13, 50), (21, 50)):
        m_fast = E.ma(close, fast_p, "ema")
        m_exit_ref = E.ma(close, exit_ref_p, "ema")
        trades = sim_with_fast_ma_exit(raw_events, ok, close, high, low, spread, atr, m_fast, m_exit_ref, n, SAFETY_SL)
        r = evaluate(f"exit on {fast_p} EMA x {exit_ref_p} EMA cross", trades, close, spread, n)
        if r: results.append(r)

    print("\n" + "=" * 70)
    print("SUMMARY (sorted by floating-DD % of net, best first):")
    valid = [r for r in results if r["net"] > 0]
    valid.sort(key=lambda r: r["float_dd"] / r["net"])
    for r in valid:
        print(f"  {r['label']:<32} net={r['net']:8.2f} pf={r['pf']:.3f} "
              f"floatDD%={100*r['float_dd']/r['net']:5.1f}  n={r['n']}")
