"""
Follow-up to seasonal_pattern_test.py's Part 3 finding (both Vanguard
and Aurelius do better trading WITH the day's early move than against
it - Aurelius 100th percentile, Vanguard 92nd on a day-level
permutation test). That test used price-at-8am-vs-day's-open as the
reference, which is a REAL LOOKAHEAD BUG for any trade before 8am
server time (checked: this affected 34.7% of Vanguard's trades and
31.2% of Aurelius's) - the reference wasn't knowable yet at the time
of those trades.

Fixed here: 'day direction' is redefined as sign(current close -
today's open), evaluated AT THE EXACT BAR of each event - trivially
computable in real time with zero lookahead (a live EA already knows
today's open and the current price). Re-validates the finding under
this honest definition, then tests it as an actual ENTRY FILTER on
Vanguard's real trendline-breakout construction (not just a retrospective
trade classification), checking overlap with the already-shipped VWAP
filter before deciding if it adds anything real.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
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
    return dict(n=len(trades), net=net, pf=pf)


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]

    dates = df5["time"].dt.date.values
    day_open = pd.Series(close).groupby(pd.Series(dates)).transform("first").values
    day_dir_sign = np.sign(close - day_open)   # causal: no lookahead, knowable at every bar

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
    vwap_sr_ok = vwap_ok & sr_ok

    day_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        day_ok[i] = (day_dir_sign[i] == d)

    print("=" * 70)
    print("overlap check: at each of the", len(events), "breakout events, does")
    print("VWAP-agreement match day-direction-agreement?")
    vwap_vec = np.array([vwap_ok[i] for i, d in events])
    day_vec = np.array([day_ok[i] for i, d in events])
    agree = (vwap_vec == day_vec).mean()
    print(f"  agree (both true or both false): {100*agree:.1f}%")
    print(f"  VWAP true, day false: {100*np.mean(vwap_vec & ~day_vec):.1f}%   "
          f"VWAP false, day true: {100*np.mean(~vwap_vec & day_vec):.1f}%")

    print("\n" + "=" * 70)
    evaluate("BASELINE +VWAP+S/R (already shipped)", events, vwap_sr_ok, close, high, low, spread, atr, n,
              run_control=True)
    evaluate("+day-direction ALONE (no VWAP/S-R)", events, day_ok, close, high, low, spread, atr, n,
              run_control=True)
    combo = vwap_sr_ok & day_ok
    evaluate("+VWAP+S/R+day-direction (all three)", events, combo, close, high, low, spread, atr, n,
              run_control=True)
    day_sr_only = sr_ok & day_ok
    evaluate("+S/R+day-direction (day-direction REPLACING VWAP)", events, day_sr_only, close, high, low, spread, atr, n,
              run_control=True)

print("\n" + "=" * 70)
print("year-by-year: baseline +VWAP+S/R vs +VWAP+S/R+day-direction")
years = pd.to_datetime(df5["time"]).dt.year.values
for label, mask in [("baseline +VWAP+S/R", vwap_sr_ok), ("+day-direction too", combo)]:
    trades, _ = sim_trendline_filtered(events, mask, close, high, low, spread, atr, n)
    by_year = {}
    for i, ex, pnl, isbuy in trades:
        by_year.setdefault(years[i], []).append(pnl)
    print(f"\n{label}:")
    for y in sorted(by_year):
        ps = by_year[y]
        print(f"  {y}: n={len(ps):3d} net={sum(ps):9.2f} win%={100*np.mean([p>0 for p in ps]):.1f}")
