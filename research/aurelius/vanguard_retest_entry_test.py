"""
Vanguard version of the "wait for a retest before entering" idea (2026-10-08,
user's own question) - the ENTRY-side mirror of vanguard_early_exit_break_test.py
(which tested a POST-entry neckline/trendline re-break exit and found a real
loss, because Vanguard already enters right at the break). This tests the
other half: instead of entering immediately at the trendline breakout,
require price to come back and retest the broken trendline first, and only
enter if that retest resolves as a genuine bounce (closes back on the
breakout side) within RETEST_MAX_BARS - same "next couple candles" framing
already established for Meridian's retest_entry_test.py, not a multi-hour
window. A breakout that never retests within the window, or retests and
breaks straight through, is skipped entirely (no trade) rather than entered
late.

Directly comparable to research/meridian/retest_entry_test.py's finding on
Meridian: there, "never retests" was the BEST outcome bucket (PF 3.775) and
gating entry on a retest was a real loss. This checks whether Vanguard's
own trendline-breakout structure behaves the same way or differently - no
assumption either way, honest K=1 for this specific construction.

Base loop and real shipped defaults identical to
vanguard_early_exit_break_test.py (forked from the same validated
vanguard_giveback_event_driven_test.py run()) - only the entry-fill logic
changes; the SL/cap exit machinery is untouched.
"""
import sys

sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events

POINT = E.POINT
RETEST_TOL_ATR = 0.30
RETEST_MAX_BARS = 3     # "the next couple candles", not hours - same pacing as Meridian's retest test
FRACTAL_K = 100
SAFETY_SL_ATR = 4.0
MIN_SR = 0.50


def run(ctx, close, high, low, spread, n, require_retest=False):
    vwap = ctx["vwap"]
    atr = ctx["atr"]
    sr_dist_buy, sr_dist_sell = ctx["sr_dist_buy"], ctx["sr_dist_sell"]
    desc_line, asc_line = build_trendline_values(high, low, n, fractal_k=FRACTAL_K)
    events = build_breakout_events(close, desc_line, asc_line, n)
    cond_vwap = close > vwap
    entry_ok = np.zeros(n, dtype=bool)
    for i, d in events:
        vwap_ok = cond_vwap[i] if d > 0 else (not cond_vwap[i])
        sr = sr_dist_buy[i] if d > 0 else sr_dist_sell[i]
        sr_ok = not (sr >= 0.0 and sr < MIN_SR)
        entry_ok[i] = vwap_ok and sr_ok

    trades, last_exit = [], -1
    for idx, (i, d) in enumerate(events):
        if not entry_ok[i] or i < last_exit:
            continue
        is_buy = d > 0
        line = desc_line if is_buy else asc_line   # the trendline that was just broken

        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue

        if require_retest:
            touched, confirmed_at, invalidated = False, None, False
            for kk in range(fill_i, min(fill_i + RETEST_MAX_BARS + 1, n)):
                a = atr[kk]
                if np.isnan(line[kk]) or a <= 0:
                    continue
                tol = RETEST_TOL_ATR * a
                if not touched:
                    if abs(close[kk] - line[kk]) <= tol:
                        touched = True
                    continue
                bounced = close[kk] > line[kk] if is_buy else close[kk] < line[kk]
                broke = close[kk] < line[kk] if is_buy else close[kk] > line[kk]
                if bounced:
                    confirmed_at = kk
                    break
                if broke:
                    invalidated = True
                    break
            if not touched or invalidated or confirmed_at is None:
                continue   # no genuine retest-confirmed setup within the window - skip, don't chase
            fill_i = confirmed_at + 1
            if fill_i >= n:
                continue

        sc = spread[fill_i] * POINT
        entry_px = close[fill_i - 1] + sc if is_buy else close[fill_i - 1] - sc
        risk = atr[i]
        sl = entry_px - SAFETY_SL_ATR * risk if is_buy else entry_px + SAFETY_SL_ATR * risk
        cap = n
        for j in range(idx + 1, len(events)):
            if events[j][1] != d:
                cap = min(events[j][0] + 1, n)
                break
        exit_bar, exit_px, reason = None, None, None
        for kk in range(fill_i, cap):
            hit_sl = (low[kk] <= sl) if is_buy else (high[kk] >= sl)
            if hit_sl:
                exit_bar, exit_px, reason = kk, sl, "SL"
                break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
            reason = "CAP"
        pnl = (exit_px - entry_px) * (1 if is_buy else -1)
        trades.append(dict(entry_i=i, fill_i=fill_i, exit_i=exit_bar, pnl=pnl, dir=1 if is_buy else -1, reason=reason))
        last_exit = exit_bar
    return trades


def pf(pnl):
    a = np.asarray(pnl)
    gw, gl = a[a > 0].sum(), -a[a <= 0].sum()
    return gw / gl if gl > 0 else float("inf")


def report(label, trades):
    n = len(trades)
    if n == 0:
        print(f"  {label}: n=0")
        return
    pnl = np.array([t["pnl"] for t in trades])
    print(f"  {label}: n={n:4d}  win%={100*(pnl>0).mean():5.1f}  PF={pf(pnl):6.3f}  "
          f"net={pnl.sum():9.2f}  avg={pnl.mean():7.3f}")
    reasons = {}
    for t in trades:
        reasons[t["reason"]] = reasons.get(t["reason"], 0) + 1
    for r, cnt in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    print(f"Real GOLD M5: {df['time'].iloc[0]} .. {df['time'].iloc[-1]}  ({len(df)} bars)")
    ctx = E.build_context(df, h4, E.P)
    close, high, low, spread = ctx["close"], ctx["high"], ctx["low"], ctx["spread"]
    n = ctx["n"]
    cutoff_i = int(n * 0.70)
    print(f"Walk-forward cutoff (70%): {df['time'].iloc[cutoff_i]}")
    print(f"RETEST_MAX_BARS = {RETEST_MAX_BARS}  (next couple candles, not hours)\n")

    cand_trades = run(ctx, close, high, low, spread, n, require_retest=True)
    real_trades = run(ctx, close, high, low, spread, n, require_retest=False)

    print(f"{'='*92}\nCANDIDATE: wait for confirmed retest of the trendline before entering "
          f"(skip if none within {RETEST_MAX_BARS} bars)\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in cand_trades if t["entry_i"] < cutoff_i]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in cand_trades if t["entry_i"] >= cutoff_i])):
        report(label, trs)

    print(f"\n{'='*92}\nFor reference: shipped Vanguard (immediate entry at the break, no retest-gating)\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in real_trades if t["entry_i"] < cutoff_i]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in real_trades if t["entry_i"] >= cutoff_i])):
        report(label, trs)

    print(f"\n{'='*92}\nBREAKDOWN: of all {len(real_trades)} real (immediate-entry) breakouts, how many would\n"
          f"have been RETEST-CONFIRMED vs SKIPPED by the candidate rule, and how did each group\n"
          f"actually perform under the REAL (immediate) exit machinery (same diagnostic approach as\n"
          f"Meridian's post_entry_classify.py)\n{'='*92}")
    cand_entry_is = set(t["entry_i"] for t in cand_trades)
    kept = [t for t in real_trades if t["entry_i"] in cand_entry_is]
    skipped = [t for t in real_trades if t["entry_i"] not in cand_entry_is]
    report("Would-be-RETEST-CONFIRMED (candidate keeps)", kept)
    report("Would-be-SKIPPED (never retested / broke through)", skipped)
