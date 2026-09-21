"""
Joint sl x stale_bars sweep on M5, per user's explicit instruction:
don't just stack the two individually-good settings (sl=3.5xATR,
stale_bars=225) and assume they combine additively - sweep them
TOGETHER to find the real joint optimum, since exits interact (a
tighter stop changes which trades are even still open when the
stale-exit check would fire).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
FRACTAL_K = 100
MIN_SR = 0.50


def sim_full(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr,
             stale_bars=None, stale_min_profit_atr=0.0):
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
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
            if stale_bars and (kk - fill_i) >= stale_bars:
                cur_profit = ((close[kk] - entry) if is_buy else (entry - close[kk])) / atr[i]
                if cur_profit < stale_min_profit_atr:
                    exit_bar, exit_px = kk, close[kk]; break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades


def report(label, trades, close, spread, atr, n, baseline_top20=None):
    pnls = np.array([t[2] for t in trades])
    gw = pnls[pnls>0].sum(); gl=-pnls[pnls<=0].sum()
    pf = gw/gl if gl>0 else float('inf')
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    entries = np.array([t[0] for t in trades])
    edges = np.linspace(0, n, 6).astype(int)
    pos = sum(1 for b in range(5) if pnls[(entries>=edges[b])&(entries<edges[b+1])].sum() > 0)
    top20_str = ""
    if baseline_top20 is not None:
        kept = len(baseline_top20 & set(t[0] for t in trades))
        top20_str = f" top20={kept}/20"
    print(f"  {label:34s} n={len(trades):4d} net={net:9.2f} pf={pf:.3f} win%={100*(pnls>0).mean():.1f} "
          f"closedDD=${closed_dd:7.2f} floatDD=${float_dd:7.2f} wf={pos}/5{top20_str}")


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

    shipped = sim_full(events, entry_ok, close, high, low, spread, atr, n, 4.0)
    shipped_top20 = set(t[0] for t in sorted(shipped, key=lambda t: -t[2])[:20])
    print("SHIPPED (sl=4.0, no stale-exit):")
    report("shipped baseline", shipped, close, spread, atr, n, shipped_top20)

    print("\nsingle levers alone (for reference):")
    report("sl=3.5 alone", sim_full(events, entry_ok, close, high, low, spread, atr, n, 3.5), close, spread, atr, n, shipped_top20)
    report("stale=225 alone", sim_full(events, entry_ok, close, high, low, spread, atr, n, 4.0, stale_bars=225), close, spread, atr, n, shipped_top20)

    print("\nJOINT sweep (sl x stale_bars):")
    best = None
    for sl in (3.0, 3.5, 4.0, 4.5):
        for sb in (150, 200, 225, 250, 300, None):
            trades = sim_full(events, entry_ok, close, high, low, spread, atr, n, sl, stale_bars=sb)
            if not trades: continue
            closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
            label = f"sl={sl} stale={sb}"
            report(label, trades, close, spread, atr, n, shipped_top20)
