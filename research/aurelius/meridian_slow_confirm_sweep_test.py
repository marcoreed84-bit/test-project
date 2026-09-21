"""
Direct follow-up to discovering the ctx['m150'] mislabeling: those
earlier (mislabeled) Meridian numbers were accidentally testing
Aurelius's REAL, validated confirmation line (InpP150=250,
InpM150=MODE_SMA - a genuine, documented, real-tested Aurelius default,
not a bug in Aurelius itself - see Aurelius_EA.mq5 line ~554/578) rather
than a literal 150 EMA, and that accidental line outperformed the
literal 150 EMA (net 3420.71 vs 3253.93, floating DD 11.1% vs 14.9%).
Worth testing on purpose now: is Aurelius's own slow-confirmation
choice ALSO a good choice for Meridian's simpler 3-line stack, or does
Meridian's different structure (no 21/50/150/600/2400 full stack, no
momentum/pullback/volume/SR gating on this line) want something else?

Sweeps period x method for the slow confirmation line (replacing "150
EMA" in the 21/50-cross + [slow-confirm] + VWAP + S/R construction),
including the literal 150 EMA, Aurelius's real 250 SMA, and a few
neighbors, all on the SAME real M5 data/spread/sequencing/drawdown
methodology as every other test in this line of research.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from m5_stack_variants_fixed_test import sim_filtered_entries
from meridian_dd_confluence_test import drawdown_stats

POINT = E.POINT
N_RANDOM_SEEDS = 300
SAFETY_SL = 2.5
MIN_SR = 0.50


def build_and_run(df5, h4, period, method, label):
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    time = df5["time"].values

    m21 = E.ma(close, 21, "ema")
    m50 = E.ma(close, 50, "ema")
    m_slow = E.ma(close, period, method)

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    raw_events = sorted([(i, 1.0) for i in np.where(above & ~above_prev)[0]] +
                         [(i, -1.0) for i in np.where((~above) & above_prev)[0]], key=lambda e: e[0])

    cond_slow = close > m_slow
    cond_vwap = close > vwap
    ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        cs = cond_slow[i] if d > 0 else (not cond_slow[i])
        cv = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        if np.isnan(m_slow[i]) or not (cs and cv):
            continue
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        ok[i] = not (sr >= 0.0 and sr < MIN_SR)

    trades = sim_filtered_entries(raw_events, ok, close, high, low, spread, atr, n, SAFETY_SL)
    print(f"\n--- {label} ({len(raw_events)} raw crosses) ---")
    if not trades:
        print("  0 trades"); return None
    pnls = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnls[pnls > 0].sum(); gl = -pnls[pnls <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
    print(f"  n={len(trades)} net={net:.2f} win%={100*(pnls>0).mean():.1f} pf={pf:.3f}")
    edges = np.linspace(0, n, 6).astype(int)
    pos = 0
    line = "  walk-forward: "
    for b in range(5):
        lo, hi = edges[b], edges[b + 1]
        m = (entries >= lo) & (entries < hi)
        nb = m.sum()
        if nb == 0:
            line += f"[b{b+1}: 0] "; continue
        netb = pnls[m].sum()
        if netb > 0: pos += 1
        line += f"[b{b+1}: {netb:+.0f}] "
    if net > 0:
        print(f"  closedDD={closed_dd:.2f} ({100*closed_dd/net:.1f}%)  floatDD={float_dd:.2f} ({100*float_dd/net:.1f}%)")
    print(line + f"-> {pos}/5 positive")
    return dict(label=label, trades=trades, n=len(trades), net=net, pf=pf,
                closed_dd=closed_dd, float_dd=float_dd, raw_events=raw_events,
                close=close, high=high, low=low, spread=spread, atr=atr, n_bars=n)


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()

    results = []
    grid = [
        (150, "ema", "150 EMA (literal, what's shipped)"),
        (150, "sma", "150 SMA"),
        (200, "sma", "200 SMA"),
        (250, "sma", "250 SMA (Aurelius's real validated choice)"),
        (250, "ema", "250 EMA"),
        (300, "sma", "300 SMA"),
        (200, "ema", "200 EMA"),
    ]
    for period, method, label in grid:
        r = build_and_run(df5, h4, period, method, label)
        if r:
            results.append(r)

    print("\n" + "=" * 70)
    print("SUMMARY (sorted by floating-DD % of net, best first):")
    valid = [r for r in results if r["net"] > 0]
    valid.sort(key=lambda r: r["float_dd"] / r["net"])
    for r in valid:
        print(f"  {r['label']:<45} net={r['net']:8.2f} pf={r['pf']:.3f} "
              f"floatDD%={100*r['float_dd']/r['net']:5.1f}  n={r['n']}")

    if valid:
        best = valid[0]
        print(f"\nrandom-direction control on best ({best['label']}, real net={best['net']:.2f}):")
        rng = np.random.default_rng(0)
        n = best["n_bars"]
        close, high, low, atr, spread = best["close"], best["high"], best["low"], best["atr"], best["spread"]
        entry_bars = [t[0] for t in best["trades"]]
        random_nets = []
        for s in range(N_RANDOM_SEEDS):
            rdirs = rng.choice([1.0, -1.0], size=len(entry_bars))
            rev = sorted(zip(entry_bars, rdirs.tolist()), key=lambda e: e[0])
            rt = []
            for kk in range(len(rev)):
                i, d = rev[kk]
                fill_i = i + 1
                if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
                    continue
                cap = min(rev[kk + 1][0] + 1, n) if kk + 1 < len(rev) else n
                raw = close[i]
                sc = spread[fill_i] * POINT
                is_buy = d > 0
                entry = raw + sc if is_buy else raw - sc
                sl = entry - SAFETY_SL * atr[i] if is_buy else entry + SAFETY_SL * atr[i]
                eb, ep = None, None
                for k2 in range(fill_i, cap):
                    if is_buy and low[k2] <= sl: eb, ep = k2, sl; break
                    if (not is_buy) and high[k2] >= sl: eb, ep = k2, sl; break
                if eb is None:
                    eb = cap - 1 if cap > fill_i else fill_i
                    ep = close[min(eb, n - 1)]
                rt.append((ep - entry) if is_buy else (entry - ep))
            random_nets.append(sum(rt) if rt else 0.0)
        random_nets = np.array(random_nets)
        pct = 100 * (random_nets < best["net"]).mean()
        print(f"null mean={random_nets.mean():.2f} std={random_nets.std():.2f} -> real net percentile={pct:.1f}")
