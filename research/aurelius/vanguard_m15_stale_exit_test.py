"""
M15 companion to vanguard_dd_more_levers_test.py's stale-exit finding
(M5: stale_bars=225 ~18.75h, net -2.0%, closedDD -11.8%, floatDD -9.3%,
walk-forward 3/5->4/5, all real). NOT a naive /3 bar-count rescale -
same discipline as every M5->M15 step this session (Meridian's naive
M15 port failed; trendline_m15_test.py's fresh k-sweep worked) - swept
fresh on M15's own bar structure and its own validated construction
(k=33, sl=3.0xATR).
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from meridian_m15_test import build_sr_distance
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
FRACTAL_K = 33
SAFETY_SL = 3.0
MIN_SR = 0.50


def sim_stale(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr,
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
    print(f"  {label:20s} n={len(trades):4d} net={net:9.2f} pf={pf:.3f} win%={100*(pnls>0).mean():.1f} "
          f"closedDD=${closed_dd:7.2f} floatDD=${float_dd:7.2f} wf={pos}/5{top20_str}")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    df15 = E.resample_m15_from_m5(df5)
    n = len(df15)
    close = df15["close"].values.astype(float)
    high = df15["high"].values.astype(float)
    low = df15["low"].values.astype(float)
    spread = df15["spread"].values.astype(float)

    atr = E.wilder_atr(high, low, close, 14)
    vwap = E.session_vwap(df15)
    sr_hi, sr_lo = build_sr_distance(df15, h4)
    with np.errstate(invalid="ignore", divide="ignore"):
        sr_dist_buy = np.abs(sr_hi - close) / atr
        sr_dist_sell = np.abs(close - sr_lo) / atr

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if not cv:
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        entry_ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    baseline = sim_stale(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL)
    baseline_top20 = set(t[0] for t in sorted(baseline, key=lambda t: -t[2])[:20])
    print(f"M15 baseline (+VWAP+S/R, k={FRACTAL_K}, sl={SAFETY_SL}xATR):")
    report("no stale-exit", baseline, close, spread, atr, n, baseline_top20)

    print("\nfresh stale_bars sweep on M15's own bar structure (96 bars/trading day on M15,")
    print("vs 288 on M5 - so wall-clock-equivalent bars differ by 3x, NOT assumed, swept fresh):")
    for sb in (30, 50, 75, 100, 125, 150, 200, 250, 300):
        trades = sim_stale(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL,
                            stale_bars=sb, stale_min_profit_atr=0.0)
        report(f"stale_bars={sb}", trades, close, spread, atr, n, baseline_top20)
