"""
Follow-up to meridian_dd_confluence_test.py, which tested Aurelius's own
validated entry-side confluence filters (momentum, pullback, volume,
S/R distance, slope, crisscross) on Meridian's 150+VWAP-confirmed 21/50
cross. Result: only S/R distance helped even marginally (floating DD
12.3%->11.3% of net); momentum/volume/crisscross made DD WORSE despite
cutting trade count, and the slope filter is nearly incompatible with
a fresh cross by construction (a 21/50 cross happens near the 50 EMA's
slope INFLECTION, not after it's already built 0.5xATR/20bar of
momentum - only 1 of 2603 trades satisfied both at once). Entry-side
filtering alone does not fix this drawdown.

Aurelius_EA.mq5's own real header has already solved almost exactly
this problem once: InpUsePrice21Exit - closing a trade as soon as
price closes InpPrice21BufferATR past the 21 EMA for
InpPrice21ConfirmBars consecutive closed bars, instead of waiting for
the full alignment break - "the first idea this session to improve
profit and drawdown together" there, cutting Aurelius's Python-model
max drawdown 183.4->148.0 (-19%). This tests the same mechanic on
Meridian: an early-warning exit that fires DURING a trade, before the
opposite 21/50 cross or the 3.0xATR safety stop, whichever comes
first. Same real M5 data/spread, same corrected single-position
sequencing, now reporting closed AND floating drawdown for every
variant (the actual target here) alongside net/PF/walk-forward.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
from meridian_dd_confluence_test import drawdown_stats, evaluate

POINT = E.POINT
SAFETY_SL = 3.0


def sim_with_price21_exit(raw_events, entry_ok, close, high, low, spread, atr, m21, n,
                           safety_sl_atr, buffer_atr, confirm_bars):
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
        buf = buffer_atr * atr[i]
        cap = min(i_next + 1, n)
        exit_bar, exit_px = None, None
        adverse_streak = 0
        for kk in range(fill_i, cap):
            if is_buy and low[kk] <= sl:
                exit_bar, exit_px = kk, sl; break
            if (not is_buy) and high[kk] >= sl:
                exit_bar, exit_px = kk, sl; break
            if np.isnan(m21[kk]):
                continue
            adverse = (close[kk] < m21[kk] - buf) if is_buy else (close[kk] > m21[kk] + buf)
            adverse_streak = adverse_streak + 1 if adverse else 0
            if adverse_streak >= confirm_bars:
                exit_bar, exit_px = kk, close[kk]
                break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
        pnl = (exit_px - entry) if is_buy else (entry - exit_px)
        trades.append((i, exit_bar, pnl, is_buy))
    return trades


def evaluate_price21(label, raw_events, entry_ok, close, high, low, spread, atr, m21, n, time,
                      buffer_atr, confirm_bars):
    trades = sim_with_price21_exit(raw_events, entry_ok, close, high, low, spread, atr, m21, n,
                                    SAFETY_SL, buffer_atr, confirm_bars)
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
        print(f"  closed DD={closed_dd:.2f} ({100*closed_dd/net:.1f}% of net)  "
              f"floating DD={float_dd:.2f} ({100*float_dd/net:.1f}% of net)")
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
    print(line + f"-> {pos}/5 positive")
    return dict(label=label, n=len(trades), net=net, pf=pf, closed_dd=closed_dd, float_dd=float_dd)


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, atr, spread = ctx["close"], ctx["high"], ctx["low"], ctx["atr"], ctx["spread"]
    m21, m50, m150, vwap = ctx["m21"], ctx["m50"], ctx["m150"], ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    time = df5["time"].values

    above = m21 > m50
    above_prev = np.concatenate(([False], above[:-1]))
    raw_events = sorted([(i, 1.0) for i in np.where(above & ~above_prev)[0]] +
                         [(i, -1.0) for i in np.where((~above) & above_prev)[0]], key=lambda e: e[0])

    cond_150 = close > m150
    cond_vwap = close > vwap
    base_ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        base_ok[i] = (cond_150[i] and cond_vwap[i]) if d > 0 else ((not cond_150[i]) and (not cond_vwap[i]))

    MIN_SR_ATR = 0.50
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in raw_events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = base_ok[i] and not (sr >= 0.0 and sr < MIN_SR_ATR)

    print("=" * 70)
    print("baseline exit for reference: net=3184.61 pf=1.300 closedDD%=10.1 floatDD%=12.3 (opposite-cross exit)\n")

    results = []
    for buffer_atr, confirm_bars in ((0.7, 8), (0.5, 8), (0.7, 4), (1.0, 8), (0.5, 4), (0.3, 4)):
        results.append(evaluate_price21(
            f"150+VWAP entries, Price21Exit buffer={buffer_atr}xATR confirm={confirm_bars}bars",
            raw_events, base_ok, close, high, low, spread, atr, m21, n, time, buffer_atr, confirm_bars))

    print("\n" + "=" * 70)
    print("best Price21Exit setting combined with the +S/R entry filter:")
    valid = [r for r in results if r and r["net"] > 0]
    valid.sort(key=lambda r: r["float_dd"] / r["net"])
    if valid:
        best_label = valid[0]["label"]
        # re-derive its (buffer,confirm) from the label text is fragile - just
        # re-run the actual best pair directly instead
        best_pair = None
        best_score = None
        for buffer_atr, confirm_bars in ((0.7, 8), (0.5, 8), (0.7, 4), (1.0, 8), (0.5, 4), (0.3, 4)):
            for r in results:
                if r and f"buffer={buffer_atr}xATR confirm={confirm_bars}bars" in r["label"]:
                    score = r["float_dd"] / r["net"]
                    if best_score is None or score < best_score:
                        best_score, best_pair = score, (buffer_atr, confirm_bars)
        buffer_atr, confirm_bars = best_pair
        evaluate_price21(f"150+VWAP+S/R entries, Price21Exit buffer={buffer_atr}xATR confirm={confirm_bars}bars",
                          raw_events, sr_ok, close, high, low, spread, atr, m21, n, time, buffer_atr, confirm_bars)

    print("\n" + "=" * 70)
    print("SUMMARY (sorted by floating-DD % of net, best first):")
    for r in sorted([r for r in results if r and r["net"] > 0], key=lambda r: r["float_dd"] / r["net"]):
        print(f"  {r['label']:<70} net={r['net']:8.2f} pf={r['pf']:.3f} "
              f"floatDD%={100*r['float_dd']/r['net']:5.1f}  n={r['n']}")
