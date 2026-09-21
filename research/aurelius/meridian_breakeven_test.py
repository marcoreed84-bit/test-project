"""
Untried lever for drawdown, distinct from the two exit ideas already
rejected (Price21Exit, entry-price-breach): both of those fired on ANY
early adverse move against a fresh trade, which turned out to punish
the ordinary early chop this system's big winners need room for (win
rate collapsed to 7-18% in the entry-breach test). A breakeven stop is
different in kind - it only activates AFTER a trade has already moved
meaningfully in profit, so it shouldn't touch normal early noise at
all. It targets a specific, different failure mode: a trade that gets
deep into profit and then fully reverses before the 2.5xATR safety
stop or the opposite cross ever fires - exactly the shape of a bad
floating-drawdown event.

Mechanic: once the running favorable excursion since entry reaches
breakeven_trigger_atr x ATR-at-entry, ratchet the stop up (long) /
down (short) to entry + breakeven_lock_atr x ATR (a small locked-in
gain, never back down). Same intrabar-ordering care as the (corrected)
trailing-exit test earlier this session: the stop level used to check
a bar is always what was set BEFORE that bar's own high/low - never
upgraded using the same bar's extreme before checking it, which would
be unearned information.

Built on the shipped v1.02 base (21/50 EMA cross, 250 SMA + VWAP + S/R
confirm, safety_sl=2.5xATR). Same real M5 data/spread, correct single-
position sequencing, drawdown (closed + floating) reported for every
variant since that's the actual target.
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


def sim_with_breakeven(raw_events, entry_ok, close, high, low, spread, atr, n,
                        safety_sl_atr, breakeven_trigger_atr, breakeven_lock_atr):
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
        be_trigger = breakeven_trigger_atr * atr[i]
        be_lock = entry + breakeven_lock_atr * atr[i] if is_buy else entry - breakeven_lock_atr * atr[i]
        be_armed = False
        cap = min(i_next + 1, n)
        exit_bar, exit_px = None, None
        peak = entry
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
            # update AFTER checking - this bar's own extreme can only affect
            # the stop level used on LATER bars, never this one's own check
            if is_buy:
                peak = max(peak, high[kk])
                if not be_armed and (peak - entry) >= be_trigger:
                    be_armed = True
                    sl = max(sl, be_lock)
            else:
                peak = min(peak, low[kk])
                if not be_armed and (entry - peak) >= be_trigger:
                    be_armed = True
                    sl = min(sl, be_lock)
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
    for trigger, lock in ((0.5, 0.1), (1.0, 0.1), (1.0, 0.3), (1.5, 0.3), (1.5, 0.5), (2.0, 0.5), (2.0, 1.0)):
        trades = sim_with_breakeven(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL, trigger, lock)
        r = evaluate(f"breakeven trigger={trigger}xATR lock={lock}xATR", trades, close, spread, n)
        if r: results.append(r)

    print("\n" + "=" * 70)
    print("SUMMARY (sorted by floating-DD % of net, best first):")
    valid = [r for r in results if r["net"] > 0]
    valid.sort(key=lambda r: r["float_dd"] / r["net"])
    for r in valid:
        print(f"  {r['label']:<40} net={r['net']:8.2f} pf={r['pf']:.3f} "
              f"floatDD%={100*r['float_dd']/r['net']:5.1f}  n={r['n']}")

    if valid:
        best = valid[0]
        print(f"\nrandom-direction control on best ({best['label']}, real net={best['net']:.2f}):")
        rng = np.random.default_rng(0)
        entry_bars = [t[0] for t in best["trades"]]
        # re-derive trigger/lock from best label for the control re-sim
        import re
        m = re.search(r"trigger=([\d.]+)xATR lock=([\d.]+)xATR", best["label"])
        trig, lock = float(m.group(1)), float(m.group(2))
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
            trades_r = sim_with_breakeven(rev, ok_r, close, high, low, spread, atr, n, SAFETY_SL, trig, lock)
            random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
        random_nets = np.array(random_nets)
        pct = 100 * (random_nets < best["net"]).mean()
        print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")
