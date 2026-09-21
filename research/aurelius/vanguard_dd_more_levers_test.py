"""
Follow-up to vanguard_dd_focused_test.py (found sl=3.5xATR and a
consecutive-loss circuit breaker as real, working DD levers). User
asked for more - testing two more genuinely different mechanisms not
yet tried on Vanguard:

  1. Breakeven stop-move: once a trade reaches breakeven_atr x ATR of
     open profit, move the stop to entry (locking in a scratch, not a
     loss) - different from partial profit-taking (rejected: banks
     PROFIT and caps the winner's remaining upside). This only removes
     the downside risk of giving back an entire winner, doesn't touch
     how far it can still run once triggered.
  2. Stale-exit: cut a losing trade loose early (at breakeven or a
     small loss) if it's been open stale_bars without reaching
     stale_min_profit_atr - same real mechanism as Aurelius_EA.mq5's
     own InpUseStaleExit, first test of it on Vanguard's construction.
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
SAFETY_SL = 4.0


def sim_breakeven(events, entry_ok, close, high, low, spread, atr, n, safety_sl_atr,
                   breakeven_atr=None):
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
        be_trigger = entry + breakeven_atr * atr[i] if (breakeven_atr and is_buy) else \
                     (entry - breakeven_atr * atr[i] if breakeven_atr else None)
        be_done = False
        cap = n
        for j in range(idx + 1, len(events)):
            if events[j][1] != d:
                cap = min(events[j][0] + 1, n)
                break
        exit_bar, exit_px = None, None
        for kk in range(fill_i, cap):
            cur_sl = entry if be_done else sl
            if is_buy and low[kk] <= cur_sl:
                exit_bar, exit_px = kk, cur_sl; break
            if (not is_buy) and high[kk] >= cur_sl:
                exit_bar, exit_px = kk, cur_sl; break
            if be_trigger is not None and not be_done:
                if (is_buy and high[kk] >= be_trigger) or ((not is_buy) and low[kk] <= be_trigger):
                    be_done = True
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
        last_exit = exit_bar
    return trades


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


def report(label, trades, baseline_top20=None):
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
    print(f"  {label:32s} n={len(trades):4d} net={net:9.2f} pf={pf:.3f} win%={100*(pnls>0).mean():.1f} "
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

    baseline = sim_breakeven(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL)
    baseline_top20 = set(t[0] for t in sorted(baseline, key=lambda t: -t[2])[:20])
    print("=" * 70)
    print("LEVER 3: breakeven stop-move (locks in scratch once profit reaches X)")
    report("baseline (no breakeven)", baseline, baseline_top20)
    for be in (1.0, 1.5, 2.0, 2.5, 3.0):
        trades = sim_breakeven(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL, breakeven_atr=be)
        report(f"breakeven @ {be}xATR", trades, baseline_top20)

    print("\n" + "=" * 70)
    print("LEVER 4: stale-exit (cut a non-performing trade loose early)")
    for sb in (100, 200, 500, 1000):
        for minp in (0.0, -0.5):
            trades = sim_stale(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL,
                                stale_bars=sb, stale_min_profit_atr=minp)
            report(f"stale_bars={sb} min_profit={minp}xATR", trades, baseline_top20)

print("\n" + "=" * 70)
print("refining stale_bars around the promising 200-bar setting:")
for sb in (150, 175, 200, 225, 250, 275, 300):
    trades = sim_stale(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL,
                        stale_bars=sb, stale_min_profit_atr=0.0)
    report(f"stale_bars={sb}", trades, baseline_top20)

print("\n" + "=" * 70)
print("random-direction control on the best (stale_bars=200):")
best = sim_stale(events, entry_ok, close, high, low, spread, atr, n, SAFETY_SL,
                  stale_bars=200, stale_min_profit_atr=0.0)
best_net = sum(t[2] for t in best)
rng = np.random.default_rng(0)
random_nets = []
for s in range(300):
    rdirs = rng.choice([1.0, -1.0], size=len(events))
    rev = [(i, d) for (i, _), d in zip(events, rdirs)]
    rev.sort(key=lambda e: e[0])
    trades_r = sim_stale(rev, entry_ok, close, high, low, spread, atr, n, SAFETY_SL,
                          stale_bars=200, stale_min_profit_atr=0.0)
    random_nets.append(sum(t[2] for t in trades_r) if trades_r else 0.0)
random_nets = np.array(random_nets)
pct = 100 * (random_nets < best_net).mean()
print(f"  stale_bars=200: net={best_net:.2f}  random-direction percentile={pct:.1f} "
      f"(null mean={random_nets.mean():.2f})")
print(f"  (baseline's own percentile was 99.7 - checking this hasn't degraded significance)")
