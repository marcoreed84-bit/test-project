"""
User's idea, worked through directly: in a genuine trend, by the time
price pulls back to retest a moving average, that average has risen
since entry (for a long) - so a full round-trip of price back through
the ENTRY PRICE ITSELF (not just a dip toward a fast-moving MA) is a
more specific early-failure signal than an ordinary pullback. This is
NOT the same idea as meridian_price21exit_test.py (rejected) - that one
checked price against the 21 EMA, which sits close to price at all
times and gets brushed by noise constantly. Entry price is a FIXED
level; in a real trend the MA structure moves away from it, so a full
retrace through it should be rarer and more meaningful.

Caveat tested for, not assumed: a zero-buffer, zero-confirmation version
("exit the instant price ticks below entry") risks the same noise
problem Price21Exit had, just anchored differently - plenty of genuine
trend trades dip slightly below entry before continuing. Sweeps buffer
(0 to 0.5xATR) x confirm_bars (1 to 4) including the literal zero-
tolerance version the user described, to see where (if anywhere) this
actually helps versus just cutting winners short again.

Built on top of the current shipped best (150+VWAP+S/R entries,
safety_sl=2.5xATR, real-MT5-confirmed net=51394.84 ZAR / DD 29.82%
equity). Same real M5 data/spread, correct single-position sequencing,
drawdown reported for every variant (the actual target).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
SAFETY_SL = 2.5


def sim_with_entry_breach_exit(raw_events, entry_ok, close, high, low, spread, atr, n,
                                safety_sl_atr, buffer_atr, confirm_bars):
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
        buf = buffer_atr * atr[i]
        cap = min(i_next + 1, n)
        exit_bar, exit_px = None, None
        adverse_streak = 0
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
            adverse = (close[kk] < entry - buf) if is_buy else (close[kk] > entry + buf)
            adverse_streak = adverse_streak + 1 if adverse else 0
            if adverse_streak >= confirm_bars:
                exit_bar, exit_px = kk, close[kk]
                break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
    return trades


def evaluate(label, trades, close, spread, n, time):
    print(f"\n--- {label} ---")
    if not trades:
        print("  0 trades"); return None
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
    return dict(label=label, n=len(trades), net=net, pf=pf, closed_dd=closed_dd, float_dd=float_dd)


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    m21, m50, m150, vwap = ctx["m21"], ctx["m50"], ctx["m150"], ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    time = df5["time"].values

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    raw_events = sorted([(i, 1.0) for i in np.where(above & ~above_prev)[0]] +
                         [(i, -1.0) for i in np.where((~above) & above_prev)[0]], key=lambda e: e[0])

    cond_150 = close > m150
    cond_vwap = close > vwap
    base_ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        base_ok[i] = (cond_150[i] and cond_vwap[i]) if d > 0 else ((not cond_150[i]) and (not cond_vwap[i]))
    MIN_SR = 0.50
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = base_ok[i] and not (sr >= 0.0 and sr < MIN_SR)

    print("=" * 70)
    print("shipped baseline for reference: net=3420.71 pf=1.356 closedDD%=9.8 floatDD%=11.1 walk-forward=5/5\n")

    results = []
    for buffer_atr, confirm_bars in ((0.0, 1), (0.1, 1), (0.1, 2), (0.2, 2), (0.3, 2), (0.2, 4), (0.5, 2)):
        trades = sim_with_entry_breach_exit(raw_events, sr_ok, close, high, low, spread, atr, n,
                                             SAFETY_SL, buffer_atr, confirm_bars)
        results.append(evaluate(f"entry-breach exit: buffer={buffer_atr}xATR confirm={confirm_bars}bars",
                                 trades, close, spread, n, time))

    print("\n" + "=" * 70)
    print("SUMMARY (sorted by floating-DD % of net, best first):")
    for r in sorted([r for r in results if r and r["net"] > 0], key=lambda r: r["float_dd"] / r["net"]):
        print(f"  {r['label']:<50} net={r['net']:8.2f} pf={r['pf']:.3f} "
              f"floatDD%={100*r['float_dd']/r['net']:5.1f}  n={r['n']}")
