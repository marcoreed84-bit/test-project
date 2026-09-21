"""
Direct follow-up to a real finding in Vanguard's actual MT5 backtest
deals: comparing Vanguard_EA.mq5's real trades against Aurelius_EA.mq5's
real trades on the SAME account/period, trades where Aurelius was
ALSO in the same direction at some point during the trade were
dramatically better (198 trades, net +$88,782.64, win% 58.1%) than
trades with no Aurelius overlap at all (486 trades, net -$27,751.25,
win% 17.5%) - holding up independently in every year 2023-2026, not
just a recency artifact.

That comparison used hindsight (did Aurelius ever agree at ANY point
during the whole trade). This tests the real, forward-looking version:
was Aurelius's OWN bias signal (Aligned() in Aurelius_EA.mq5 - the
21>50>150>600 + price vs 2400 alignment check, ALIGN_MID, its real
shipped default) already pointing the same way at the EXACT bar
Vanguard's trendline breakout fires - the only version of this that
could actually gate a live entry. engine.py's aligned_buy/aligned_sell
already implement this (verified against Aurelius_EA.mq5's real
Aligned() function and current shipped defaults p150=250/m150=sma,
p600=500/m600=smma - not re-derived, reused directly).

User's own explicit requirement: Vanguard must stay standalone -
Aurelius's bias gets computed INSIDE Vanguard's own code (self-
contained, no runtime dependency on Aurelius's EA actually running),
matching how this filter would actually ship.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events
from trendline_confluence_test import sim_trendline_filtered
from meridian_dd_confluence_test import drawdown_stats

N_RANDOM_SEEDS = 300
FRACTAL_K = 100
SAFETY_SL = 4.0
MIN_SR = 0.50


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
    result = dict(label=label, n=len(trades), net=net, pf=pf)
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
    return result


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    aligned_buy, aligned_sell = ctx["aligned_buy"], ctx["aligned_sell"]

    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    print(f"{len(events)} trendline-breakout events\n")

    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < MIN_SR)
    vwap_sr_ok = vwap_ok & sr_ok

    print("=" * 70)
    evaluate("VALIDATED BASELINE (+VWAP+S/R, already shipped in v1.01/v1.02)",
              events, vwap_sr_ok, close, high, low, spread, atr, n, run_control=True)

    bias_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        bias_ok[i] = aligned_buy[i] if d > 0 else aligned_sell[i]
    evaluate("+Aurelius bias ALONE (no VWAP/S-R)", events, bias_ok, close, high, low, spread, atr, n,
              run_control=True)

    combo_ok = vwap_sr_ok & bias_ok
    evaluate("+VWAP+S/R+Aurelius bias (all three)", events, combo_ok, close, high, low, spread, atr, n,
              run_control=True)

    bias_sr_ok = sr_ok & bias_ok
    evaluate("+S/R+Aurelius bias (drop VWAP)", events, bias_sr_ok, close, high, low, spread, atr, n)

print("\n" + "=" * 70)
print("year-by-year, +VWAP+S/R+Aurelius bias vs baseline +VWAP+S/R:")
import pandas as pd
df5 = E.load_m5()
time = df5["time"].values
years = pd.to_datetime(time).year if not hasattr(time[0], 'year') else [t.year for t in time]
years = np.array([pd.Timestamp(t).year for t in time])

h4 = E.load_h4()
ctx = E.build_context(df5, h4, params=E.P)
n = ctx["n"]
close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
vwap = ctx["vwap"]
sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
aligned_buy, aligned_sell = ctx["aligned_buy"], ctx["aligned_sell"]
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
bias_ok = np.zeros(n, dtype=bool)
for i, d in events:
    bias_ok[i] = aligned_buy[i] if d > 0 else aligned_sell[i]
vwap_sr_ok = vwap_ok & sr_ok
combo_ok = vwap_sr_ok & bias_ok

for label, mask in [("baseline +VWAP+S/R", vwap_sr_ok), ("+Aurelius bias too", combo_ok)]:
    trades, _ = sim_trendline_filtered(events, mask, close, high, low, spread, atr, n)
    by_year = {}
    for i, ex, pnl, isbuy in trades:
        y = years[i]
        by_year.setdefault(y, []).append(pnl)
    print(f"\n{label}:")
    for y in sorted(by_year):
        ps = by_year[y]
        print(f"  {y}: n={len(ps):3d} net={sum(ps):9.2f} win%={100*np.mean([p>0 for p in ps]):.1f}")
