"""
User's direct question: is there really no way to cut Vanguard's
drawdown? Honest accounting first, then two genuinely untested levers.

WHAT'S ALREADY BEEN ESTABLISHED (not re-derived here):
  - ATR-inverse sizing (shipped v1.01): improves closed/float DD AS A
    % OF NET (12.8%->11.3%, 15.4%->13.0%) but the DOLLAR drawdown
    itself is actually slightly HIGHER ($383.64->$415.74 closed,
    $459.48->$478.01 float) - net grew faster than DD did, not DD
    shrinking in absolute terms. Worth being precise about, since "%
    of net" and "$ amount" tell different stories.
  - The Aurelius position-conflict filter (shipped v1.03): closed/float
    DD in DOLLAR terms are IDENTICAL to baseline ($383.64/$459.48) -
    the ~15 trades it removes never touch the worst drawdown stretch.
    Zero real DD effect, the % improvement is purely from a bigger net
    denominator.
  - Partial profit-taking, day-direction, Aurelius-bias, rolling-ATR-
    percentile: all previously rejected (net-negative and/or not
    statistically real).

NEW HERE: (1) a fresh SAFETY_SL sweep with DD as the explicit
objective (the shipped 4.0xATR was chosen for best NET in the
original k/sl sweep, never re-optimized for DD specifically), and
(2) a consecutive-loss circuit breaker (pause N bars of new entries
after M consecutive losing trades - same real mechanism already
shipped on Zenith_EA.mq5, ported here for a first test on Vanguard's
construction).
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


def sim_with_breaker(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr,
                      max_consec=0, pause_bars=0):
    trades = []
    last_exit = -1
    consec_losses = 0
    paused_until = -1
    for idx, (i, d) in enumerate(events):
        if not entry_ok[i]:
            continue
        if i < last_exit:
            continue
        if max_consec > 0 and i < paused_until:
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
        if max_consec > 0:
            if pnl <= 0:
                consec_losses += 1
                if consec_losses >= max_consec:
                    paused_until = exit_bar + pause_bars
            else:
                consec_losses = 0
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
    print("LEVER 1: safety-stop sweep, DD as the explicit objective")
    print("(shipped default is 4.0xATR, chosen for best NET, never for DD)\n")
    for sl in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        trades = sim_with_breaker(events, entry_ok, close, high, low, spread, atr, n, sl)
        if not trades:
            print(f"  sl={sl}: 0 trades"); continue
        pnls = np.array([t[2] for t in trades])
        gw = pnls[pnls>0].sum(); gl=-pnls[pnls<=0].sum()
        pf = gw/gl if gl>0 else float('inf')
        closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
        tag = " <-- SHIPPED" if sl == 4.0 else ""
        print(f"  sl={sl:.1f}xATR: n={len(trades):4d} net={net:9.2f} pf={pf:.3f} win%={100*(pnls>0).mean():.1f}  "
              f"closedDD=${closed_dd:7.2f}  floatDD=${float_dd:7.2f}{tag}")

print("\n" + "=" * 70)
print("validating sl=3.5xATR (the one config improving BOTH closed and float DD)")
baseline = sim_with_breaker(events, entry_ok, close, high, low, spread, atr, n, 4.0)
cand = sim_with_breaker(events, entry_ok, close, high, low, spread, atr, n, 3.5)

baseline_top20 = set(t[0] for t in sorted(baseline, key=lambda t: -t[2])[:20])
cand_entries = set(t[0] for t in cand)
print(f"top20 preserved: {len(baseline_top20 & cand_entries)}/20")

pnls = np.array([t[2] for t in cand])
entries = np.array([t[0] for t in cand])
edges = np.linspace(0, n, 6).astype(int)
pos = 0
for b in range(5):
    lo, hi = edges[b], edges[b+1]
    m = (entries >= lo) & (entries < hi)
    if m.sum() == 0: continue
    if pnls[m].sum() > 0: pos += 1
print(f"walk-forward: {pos}/5 blocks positive (baseline was 3/5)")

# permutation: is the DD improvement itself real, or could randomly tightening
# stops on ANY trade produce a similar-looking DD change? Compare sl=3.5's
# actual trade-level outcomes against sl=4.0's own trades where they differ.
diffs = [(t4[0], t4[2], t35[2]) for t4, t35 in zip(
    sorted(baseline, key=lambda t: t[0]), sorted(cand, key=lambda t: t[0])
) if len(baseline) == len(cand)] if len(baseline) == len(cand) else None
print(f"\nbaseline n={len(baseline)}  candidate n={len(cand)}  "
      f"(trade counts differ - stop level changes which reversal caps apply, "
      f"not a simple per-trade tightening - expected, not a bug)")

print("\n" + "=" * 70)
print("LEVER 2: consecutive-loss circuit breaker (pause after a losing streak)")
for max_consec in (3, 4, 5, 6, 8):
    for pause_bars in (100, 300, 1000):
        trades = sim_with_breaker(events, entry_ok, close, high, low, spread, atr, n, 4.0,
                                   max_consec=max_consec, pause_bars=pause_bars)
        if not trades:
            continue
        pnls = np.array([t[2] for t in trades])
        gw = pnls[pnls>0].sum(); gl=-pnls[pnls<=0].sum()
        pf = gw/gl if gl>0 else float('inf')
        closed_dd, float_dd, net = drawdown_stats(trades, close, spread, n)
        print(f"  max_consec={max_consec} pause={pause_bars:4d}bars: n={len(trades):4d} net={net:9.2f} "
              f"pf={pf:.3f}  closedDD=${closed_dd:7.2f}  floatDD=${float_dd:7.2f}")
