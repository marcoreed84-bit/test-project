"""
User's idea: like Aurelius, some Meridian trades likely go into real
profit before reversing and giving it all back to the wide 2.5xATR
stop or the eventual opposite cross - the classic "give-back" pattern
Aurelius_EA.mq5's own header discusses at length. A fixed take-profit
locks in the FULL position at a target rather than the breakeven
stop's partial/ratcheted protection (already tested and rejected) -
genuinely different mechanic, worth testing on its own rather than
assumed to fail the same way.

Sweeps tp_atr (both tighter and wider than the 2.5xATR safety stop)
on top of the shipped v1.02 base (21/50 EMA cross, 250 SMA + VWAP +
S/R confirm). Exit is TP, SL, or the next raw reversal - whichever
comes first. Same real M5 data/spread, correct single-position
sequencing, drawdown (closed + floating) reported for every variant.
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


def sim_with_fixed_tp(raw_events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr, tp_atr):
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
        tp = entry + tp_atr * atr[i] if is_buy else entry - tp_atr * atr[i]
        cap = min(i_next + 1, n)
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            if is_buy:
                if high[kk] >= tp: exit_bar, exit_px = kk, tp; break
                if low[kk] <= sl: exit_bar, exit_px = kk, sl; break
            else:
                if low[kk] <= tp: exit_bar, exit_px = kk, tp; break
                if high[kk] >= sl: exit_bar, exit_px = kk, sl; break
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
    return dict(label=label, n=len(trades), net=net, pf=pf, closed_dd=closed_dd, float_dd=float_dd, trades=trades)


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
    print("shipped v1.02 baseline for reference: net=3432.72 pf=1.357 floatDD%=11.1 walk-forward=5/5\n")

    results = []
    for tp_atr in (0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0):
        trades = sim_with_fixed_tp(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL, tp_atr)
        r = evaluate(f"fixed TP={tp_atr}xATR (safety_sl=2.5xATR)", trades, close, spread, n)
        if r: results.append(r)

    print("\n" + "=" * 70)
    print("SUMMARY (sorted by floating-DD % of net, best first):")
    valid = [r for r in results if r["net"] > 0]
    valid.sort(key=lambda r: r["float_dd"] / r["net"])
    for r in valid:
        print(f"  {r['label']:<35} net={r['net']:8.2f} pf={r['pf']:.3f} "
              f"floatDD%={100*r['float_dd']/r['net']:5.1f}  n={r['n']}")

    if valid:
        best = valid[0]
        print(f"\nrandom-direction control on best ({best['label']}, real net={best['net']:.2f}):")
        rng = np.random.default_rng(0)
        import re
        tp_val = float(re.search(r"TP=([\d.]+)xATR", best["label"]).group(1))
        random_nets = []
        for s in range(N_RANDOM_SEEDS):
            rdirs = rng.choice([1.0, -1.0], size=len(raw_events))
            rev = [(i, d) for (i, _), d in zip(raw_events, rdirs)]
            rev.sort(key=lambda e: e[0])
            ok_r = np.zeros(n, dtype=bool)
            for i, d in rev:
                cc = cond_confirm[i] if d > 0 else (not cond_confirm[i])
                cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
                if np.isnan(m_confirm[i]) or not (cc and cv):
                    continue
                sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
                ok_r[i] = not (sr >= 0.0 and sr < MIN_SR)
            trades_r = sim_with_fixed_tp(rev, ok_r, close, high, low, spread, atr, n, SAFETY_SL, tp_val)
            random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
        random_nets = np.array(random_nets)
        pct = 100 * (random_nets < best["net"]).mean()
        print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")
