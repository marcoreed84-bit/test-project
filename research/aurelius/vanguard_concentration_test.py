"""
User's direct question: can Vanguard's trade concentration (top 20
trades = 109% of real net, remove them and it's negative) be improved?

Meridian's own sibling research this session already tried nine
different drawdown/concentration ideas (price21exit, entry-breach-exit,
fixed-tp, 13/21-exit, breakeven, position-sizing, partial-scaleout,
atr-percentile-filter, h4-trend-filter) - ALL REJECTED, because clipping
early costs more of the fat-tail winners than it protects in a trend-
following "let winners run" system. But that was tested on Meridian's
21/50-cross construction, not Vanguard's trendline breakout - different
signal, different holding pattern, worth checking directly rather than
assuming the same conclusion transfers unverified.

Tests two concrete, real levers on Vanguard's own construction
(+VWAP+S/R, k=100, sl=4.0xATR - the shipped v1.02/v1.03 recipe):
  1. Partial profit-taking: bank half the "position" at a fixed ATR
     profit target, let the other half ride to the normal
     hold-to-reversal exit - does this reduce concentration without
     costing too much of the edge?
  2. Trailing/breakeven stop after some profit - does locking in gains
     progressively change the concentration picture?

Same rigor as the rest of this session: real M5 data/spread, walk-
forward, net AND concentration reported side by side so a "looks
better" number can't hide a concentration cost (or vice versa).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
FRACTAL_K = 100
SAFETY_SL = 4.0
MIN_SR = 0.50


def concentration(trades):
    pnls = sorted([t[2] for t in trades], reverse=True)
    net = sum(pnls)
    top20 = sum(pnls[:20])
    return net, top20, (100 * top20 / net if net else float("nan")), (net - top20)


def sim_partial(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr,
                 bank_frac=0.5, bank_atr=None):
    """Same base construction as sim_trendline_filtered, but if bank_atr
    is set: bank_frac of the position is closed the first time price
    reaches bank_atr x ATR of open profit (banked pnl = that move x
    bank_frac), the remaining (1-bank_frac) rides the normal
    hold-to-reversal/stop exit unchanged. bank_atr=None reproduces the
    unfiltered baseline exactly (for a same-code sanity check)."""
    trades = []
    last_exit = -1
    for idx, (i, d) in enumerate(events):
        if not entry_ok[i]:
            continue
        if i < last_exit:
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
        for j in range(idx + 1, len(events)):
            if events[j][1] != d:
                cap = min(events[j][0] + 1, n)
                break

        bank_px = None
        if bank_atr is not None:
            bank_px = entry + bank_atr * atr[i] if is_buy else entry - bank_atr * atr[i]

        exit_bar, exit_px, banked_pnl = None, None, 0.0
        banked = False
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
            if bank_px is not None and not banked:
                if (is_buy and high[kk] >= bank_px) or ((not is_buy) and low[kk] <= bank_px):
                    banked = True
                    banked_pnl = (bank_px - entry) * bank_frac if is_buy else (entry - bank_px) * bank_frac
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        remainder_frac = (1 - bank_frac) if banked else 1.0
        full_pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        pnl = banked_pnl + full_pnl * remainder_frac
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    entry_ok = vwap_ok & sr_ok

    print("=" * 70)
    baseline = sim_partial(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL, bank_atr=None)
    net, top20, pct, ex_top20 = concentration(baseline)
    print(f"BASELINE (no partial exit): n={len(baseline)} net={net:.2f} top20={pct:.1f}% of net  net-ex-top20={ex_top20:.2f}")

    print("\npartial profit-taking sweep (bank_frac x bank_atr):")
    for bank_frac in (0.3, 0.5, 0.7):
        for bank_atr in (1.0, 2.0, 3.0):
            trades = sim_partial(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL,
                                  bank_frac=bank_frac, bank_atr=bank_atr)
            net, top20, pct, ex_top20 = concentration(trades)
            pnls = np.array([t[2] for t in trades])
            gw = pnls[pnls>0].sum(); gl=-pnls[pnls<=0].sum()
            pf = gw/gl if gl>0 else float('inf')
            print(f"  bank {bank_frac:.0%} @ {bank_atr}xATR: net={net:8.2f} (vs {sum(t[2] for t in baseline):.2f} baseline)  "
                  f"pf={pf:.3f} top20%={pct:5.1f}  net-ex-top20={ex_top20:8.2f}")
