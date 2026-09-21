"""
Direct follow-up to trendline_break_test.py's validated result (k=100
fractal trendline breakout, safety_sl=4.0xATR: net=3254.33, PF=1.493,
99.7th pct, floatDD=18.8% of net). User's ask: does layering Meridian's
already-proven confirmation filters (VWAP agreement, S/R distance,
250 SMA confirm line) on top of the trendline breakout tighten it up
further, the same way they helped the 21/50 cross construction.

Filters gate ENTRY only (matching the validated Meridian pattern) -
exit stays the same hold-to-reversal-or-stop design. Tested
individually and combined, same rigor: real M5 data/spread, correct
single-position sequencing, drawdown (closed + floating), walk-forward,
random-direction control on the best.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events, sim_trendline_hold
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
N_RANDOM_SEEDS = 300
FRACTAL_K = 100
SAFETY_SL = 4.0
MIN_SR = 0.50


def sim_trendline_filtered(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr=SAFETY_SL):
    """Same hold-to-reversal exit as sim_trendline_hold, but entries not
    passing entry_ok are skipped (still count for the reversal-cap
    lookup of surrounding trades, matching Meridian's proven pattern)."""
    trades = []
    last_exit = -1
    skipped = 0
    for idx, (i, d) in enumerate(events):
        if not entry_ok[i]:
            continue
        if i < last_exit:
            skipped += 1
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
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades, skipped


def evaluate(label, events, entry_ok, close, high, low, spread, atr, n, run_control=False):
    print(f"\n--- {label} ---")
    trades, skipped = sim_trendline_filtered(events, entry_ok, close, high, low, spread, atr, n)
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
    result = dict(label=label, n=len(trades), net=net, pf=pf, closed_dd=closed_dd, float_dd=float_dd)
    if run_control:
        rng = np.random.default_rng(0)
        random_nets = []
        for s in range(N_RANDOM_SEEDS):
            rdirs = rng.choice([1.0, -1.0], size=len(events))
            rev = [(i, d) for (i, _), d in zip(events, rdirs)]
            rev.sort(key=lambda e: e[0])
            trades_r, _ = sim_trendline_filtered(rev, entry_ok, close, high, low, spread, atr, n)
            random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
        random_nets = np.array(random_nets)
        pct = 100 * (random_nets < net).mean()
        print(f"  random-direction percentile={pct:.1f} (null mean={random_nets.mean():.2f})")
        result["pct"] = pct
    return result


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    m_confirm = E.ma(close, 250, "sma")

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    print(f"{len(events)} trendline-breakout events\n")

    base_ok = np.ones(n, dtype=bool)
    print("=" * 70)
    evaluate("BASELINE (no filters, already validated)", events, base_ok, close, high, low, spread, atr, n,
              run_control=True)

    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    evaluate("+VWAP agreement", events, vwap_ok, close, high, low, spread, atr, n)

    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    evaluate("+S/R distance", events, sr_ok, close, high, low, spread, atr, n)

    cond_confirm = close > m_confirm
    confirm_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        confirm_ok[i] = cond_confirm[i] if d > 0 else (not cond_confirm[i])
    evaluate("+250 SMA confirm", events, confirm_ok, close, high, low, spread, atr, n)

    vwap_sr_ok = vwap_ok & sr_ok
    evaluate("+VWAP+S/R", events, vwap_sr_ok, close, high, low, spread, atr, n, run_control=True)

    all_ok = vwap_ok & sr_ok & confirm_ok
    evaluate("+VWAP+S/R+250SMA (all three)", events, all_ok, close, high, low, spread, atr, n, run_control=True)
