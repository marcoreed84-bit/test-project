"""
User asked whether the giveback-to-breakeven finding (meridian_giveback_
exit_test.py, meridian_giveback_discriminator_test.py - a targeted rule
that improved Meridian's real net by +$2902/+87%, robust across a $8-$40
cutoff sweep) generalizes to Aurelius and Vanguard, or is specific to
Meridian's construction. Real, honest check before assuming it transfers -
same discipline as everything else this session (a finding on one system
is never assumed to hold on another without checking).

Aurelius: uses sim.py's EA-faithful simulator directly (already validated
to match 471/473 real MT5 entries).

Vanguard: no dedicated EA-faithful simulator exists yet in this repo (only
research scripts) - reconstructed here from vanguard_dd_focused_test.py's
own real shipped construction: fractal trendline breakout + VWAP + S/R
filter (entry_ok), InpSafetyStopATR=4.0 (the real shipped default). Does
NOT include InpUseAureliusFilter (the cross-EA position-conflict filter) -
that file's own header already established it removes ~15 trades with
ZERO real drawdown effect (they never touch the worst stretch), so this
omission should not materially change the real picture, but is disclosed
here rather than silently assumed.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
from sim import simulate as aurelius_simulate
from trendline_break_test import build_trendline_values, build_breakout_events

np.random.seed(42)

MIN_PEAK = 5.0
GIVEBACK_THRESH = 1.0
PEAK_CUTOFFS = (10, 15, 20, 25, 30)
POINT = E.POINT


def analyze_generic(entries, high, low, n, min_peak, giveback_thresh):
    """entries: list of (entry_i, exit_i, dir, entry_px, real_pnl)."""
    tagged = []
    for entry_i, exit_i, d, entry_px, real_pnl in entries:
        peak = 0.0
        giveback_bar = None
        for k in range(entry_i, min(exit_i, n - 1) + 1):
            fav = (high[k] - entry_px) if d > 0 else (entry_px - low[k])
            adv = (low[k] - entry_px) if d > 0 else (entry_px - high[k])
            if fav > peak:
                peak = fav
            if peak >= min_peak and giveback_bar is None and adv <= giveback_thresh:
                giveback_bar = k
        tagged.append(dict(entry_i=entry_i, exit_i=exit_i, dir=d, entry_px=entry_px,
                            peak=peak, giveback_bar=giveback_bar, real_pnl=real_pnl))
    return tagged


def sweep_report(tagged, close, label):
    all_real = np.array([t["real_pnl"] for t in tagged])
    entries_arr = np.array([t["entry_i"] for t in tagged])
    print(f"\n{label}: n={len(tagged)}  real net=${all_real.sum():.2f}")
    for cutoff in PEAK_CUTOFFS:
        vals = []
        n_cut = 0
        for t in tagged:
            if t["giveback_bar"] is not None and t["peak"] >= MIN_PEAK and t["peak"] < cutoff:
                exit_px = close[t["giveback_bar"]]
                pnl = (exit_px - t["entry_px"]) * t["dir"]
                vals.append(pnl)
                n_cut += 1
            else:
                vals.append(t["real_pnl"])
        vals = np.array(vals)
        cutoff_t = entries_arr.min() + (entries_arr.max() - entries_arr.min()) * 0.7
        is_diff = vals[entries_arr < cutoff_t].sum() - all_real[entries_arr < cutoff_t].sum()
        oos_diff = vals[entries_arr >= cutoff_t].sum() - all_real[entries_arr >= cutoff_t].sum()
        print(f"  peak_cutoff=${cutoff:>3}: net=${vals.sum():9.2f}  diff=${vals.sum()-all_real.sum():8.2f}  "
              f"n_cut={n_cut:>4}  IS_diff={is_diff:7.2f}  OOS_diff={oos_diff:7.2f}")


if __name__ == "__main__":
    df5 = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df5, h4, params=E.P)
    n = ctx["n"]
    close, high, low, spread = ctx["close"], ctx["high"], ctx["low"], ctx["spread"]

    # --- AURELIUS: real EA-faithful entries ---
    a_trades_real = aurelius_simulate(ctx, params=E.P)
    a_entries = [(t["entry_i"], t["exit_i"], t["dir"], t["entry_px"],
                  (t["exit_px"] - t["entry_px"]) * t["dir"]) for t in a_trades_real]
    a_tagged = analyze_generic(a_entries, high, low, n, MIN_PEAK, GIVEBACK_THRESH)
    sweep_report(a_tagged, close, "AURELIUS real entries")

    # --- VANGUARD: reconstructed from its own real shipped construction
    # (fractal trendline breakout + VWAP + S/R, safety_sl_atr=4.0) ---
    vwap = ctx["vwap"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=100)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    vwap_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok[i] = cond_vwap[i] if d > 0 else (not cond_vwap[i])
    sr_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok[i] = not (sr >= 0.0 and sr < 0.50)
    entry_ok = vwap_ok & sr_ok

    safety_sl_atr = 4.0
    v_entries = []
    last_exit = -1
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
        sl = entry_px - safety_sl_atr * ctx["atr"][i] if is_buy else entry_px + safety_sl_atr * ctx["atr"][i]
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
        pnl = (exit_px - entry_px) * (1 if is_buy else -1)
        v_entries.append((i, exit_bar, 1 if is_buy else -1, entry_px, pnl))
        last_exit = exit_bar

    v_tagged = analyze_generic(v_entries, high, low, n, MIN_PEAK, GIVEBACK_THRESH)
    sweep_report(v_tagged, close, "VANGUARD real-construction entries "
                                   "(no Aurelius cross-filter - disclosed negligible DD effect)")
