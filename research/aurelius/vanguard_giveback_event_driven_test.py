"""
PROPER re-test of the giveback exit on Vanguard, fixing the same flaw as
giveback_event_driven_test.py (Aurelius) and the Meridian exit_fn re-test:
giveback_generalization_test.py's vanguard_entries() sequenced breakout
events using `last_exit` from the ORIGINAL (safety-stop-only) exit, then
a post-hoc script swapped in a giveback exit on that FIXED list - it could
never see that an earlier giveback exit changes `last_exit`, which changes
which LATER breakout events get skipped vs taken.

Fix: walk each breakout event bar-by-bar checking BOTH the safety stop AND
the giveback condition together, whichever fires first is the REAL exit
bar, and that real exit bar is what `last_exit` uses for event sequencing
- exactly mirroring sim.py/msim.py's real per-bar exit-priority loops.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events

np.random.seed(42)
POINT = E.POINT


def run(ctx, close, high, low, spread, n, fractal_k, safety_sl_atr, min_sr,
        min_peak=None, peak_cutoff=None, threshold=None):
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=fractal_k)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < min_sr)
    entry_ok = vwap_ok & sr_ok
    use_giveback = min_peak is not None

    trades, last_exit = [], -1
    n_giveback = 0
    for idx, (i, d) in enumerate(events):
        if not entry_ok[i] or i < last_exit:
            continue
        fill_i = i + 1
        if fill_i >= n or np.isnan(ctx["atr"][i]) or ctx["atr"][i] <= 0:
            continue
        is_buy = d > 0
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry_px = raw + sc if is_buy else raw - sc
        risk = ctx["atr"][i]
        sl = entry_px - safety_sl_atr * risk if is_buy else entry_px + safety_sl_atr * risk
        cap = n
        for j in range(idx + 1, len(events)):
            if events[j][1] != d:
                cap = min(events[j][0] + 1, n)
                break
        exit_bar, exit_px, reason = None, None, None
        peak = 0.0
        for kk in range(fill_i, cap):
            hit_sl = (low[kk] <= sl) if is_buy else (high[kk] >= sl)
            if hit_sl:
                exit_bar, exit_px, reason = kk, sl, "SL"
                break
            if use_giveback:
                fav = (high[kk] - entry_px) if is_buy else (entry_px - low[kk])
                adv = (low[kk] - entry_px) if is_buy else (entry_px - high[kk])
                if fav > peak:
                    peak = fav
                if peak >= min_peak and peak < peak_cutoff and adv <= threshold:
                    exit_bar, exit_px, reason = kk, close[kk], "GIVEBACK"
                    n_giveback += 1
                    break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
            reason = "CAP"
        pnl = (exit_px - entry_px) * (1 if is_buy else -1)
        trades.append((i, exit_bar, pnl, is_buy, reason))
        last_exit = exit_bar
    return trades, n_giveback


def report(trades, n, label):
    pnl = np.array([t[2] for t in trades])
    entries = np.array([t[0] for t in trades])
    gw = pnl[pnl > 0].sum(); gl = -pnl[pnl <= 0].sum()
    pf = gw / gl if gl > 0 else float("inf")
    cutoff = int(n * 0.7)
    is_p = pnl[entries < cutoff]; oos_p = pnl[entries >= cutoff]
    print(f"{label}: n={len(trades)} net={pnl.sum():.2f} pf={pf:.3f} win%={100*(pnl>0).mean():.1f}")
    print(f"  IS net={is_p.sum():.2f} n={len(is_p)}   OOS net={oos_p.sum():.2f} n={len(oos_p)}")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, spread = ctx["close"], ctx["high"], ctx["low"], ctx["spread"]

    print("=" * 78)
    print("VANGUARD M5 - properly event-driven re-test")
    print("=" * 78)
    baseline, _ = run(ctx, close, high, low, spread, n, fractal_k=100, safety_sl_atr=4.0, min_sr=0.50)
    report(baseline, n, "  baseline (no giveback)")
    gb, n_gb = run(ctx, close, high, low, spread, n, fractal_k=100, safety_sl_atr=4.0, min_sr=0.50,
                    min_peak=5.0, peak_cutoff=30.0, threshold=1.0)
    report(gb, n, "  giveback cutoff=$30 (event-driven)")
    print(f"  ({n_gb} of {len(gb)} trades exited via GIVEBACK)")

    print()
    df15 = E.resample_m15_from_m5(df5)
    ctx15 = E.build_context(df15, h4, params=E.P15)
    n15 = ctx15["n"]
    close15, high15, low15, spread15 = ctx15["close"], ctx15["high"], ctx15["low"], ctx15["spread"]
    print("=" * 78)
    print("VANGUARD M15 - properly event-driven re-test")
    print("=" * 78)
    baseline15, _ = run(ctx15, close15, high15, low15, spread15, n15,
                         fractal_k=33, safety_sl_atr=3.0, min_sr=0.50)
    report(baseline15, n15, "  baseline (no giveback)")
    gb15, n_gb15 = run(ctx15, close15, high15, low15, spread15, n15,
                        fractal_k=33, safety_sl_atr=3.0, min_sr=0.50,
                        min_peak=5.0, peak_cutoff=30.0, threshold=1.0)
    report(gb15, n15, "  giveback cutoff=$30 (event-driven)")
    print(f"  ({n_gb15} of {len(gb15)} trades exited via GIVEBACK)")
