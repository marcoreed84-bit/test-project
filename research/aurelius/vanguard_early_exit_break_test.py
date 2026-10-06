"""
Vanguard version of the early-exit-on-break idea - per the user's request
to check every EA, adapted to Vanguard's OWN actual structure (it trades
a diagonal trendline breakout, not a 21/50 EMA cross - no EMAs exist in
its signal at all, so this reuses the trendline level itself, not a
borrowed EMA).

Base loop forked from research/aurelius/vanguard_giveback_event_driven_test.py's
run() - the real, validated per-bar Vanguard loop (real entry gate: VWAP +
S/R distance on a trendline breakout; real exit: SL or ride to the next
opposite breakout event, same "undefined-duration hold" shape as
Meridian). Real shipped defaults used throughout: InpFractalK=100,
InpSafetyStopATR=4.0, InpMinSRDistATR=0.50.

RULE: once price FIRST comes back within RETEST_TOL_ATR x ATR of the
trendline that was just broken to trigger entry (the trendline's own
LIVE value at each bar - it's diagonal, already time-varying), every bar
after that touch is checked for resolution: closing back on the
breakout side of the trendline (bounce) keeps the trade open as normal;
closing back on the ORIGINAL side (broke back through) exits
immediately - the breakout failed, don't wait for the stop or the next
opposite signal. Same thresholds as every other EA tested tonight
(RETEST_TOL_ATR=0.30), no re-tuning. Honest K=1.
"""
import sys

sys.path.insert(0, "/home/user/test-project/research/aurelius")
import numpy as np
import engine as E
from trendline_break_test import build_trendline_values, build_breakout_events

POINT = E.POINT
RETEST_TOL_ATR = 0.30
FRACTAL_K = 100
SAFETY_SL_ATR = 4.0
MIN_SR = 0.50


def run(ctx, close, high, low, spread, n, early_exit=False):
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
        fill_i = i + 1
        if fill_i >= n or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        is_buy = d > 0
        line = desc_line if is_buy else asc_line   # the trendline that was just broken
        sc = spread[fill_i] * POINT
        entry_px = close[i] + sc if is_buy else close[i] - sc
        risk = atr[i]
        sl = entry_px - SAFETY_SL_ATR * risk if is_buy else entry_px + SAFETY_SL_ATR * risk
        cap = n
        for j in range(idx + 1, len(events)):
            if events[j][1] != d:
                cap = min(events[j][0] + 1, n)
                break
        exit_bar, exit_px, reason = None, None, None
        touched, resolved = False, False
        for kk in range(fill_i, cap):
            hit_sl = (low[kk] <= sl) if is_buy else (high[kk] >= sl)
            if hit_sl:
                exit_bar, exit_px, reason = kk, sl, "SL"
                break
            if early_exit and not resolved and not np.isnan(line[kk]):
                a = atr[kk]
                if a > 0:
                    tol = RETEST_TOL_ATR * a
                    if not touched:
                        if abs(close[kk] - line[kk]) <= tol:
                            touched = True
                    else:
                        bounced = close[kk] > line[kk] if is_buy else close[kk] < line[kk]
                        broke = close[kk] < line[kk] if is_buy else close[kk] > line[kk]
                        if bounced:
                            resolved = True  # first retest resolved favorably - never check again
                        elif broke:
                            exit_bar, exit_px, reason = kk, close[kk], "EARLY_EXIT_BROKE"
                            break
        if exit_bar is None:
            exit_bar = cap - 1 if cap > fill_i else fill_i
            exit_px = close[min(exit_bar, n - 1)]
            reason = "CAP"
        pnl = (exit_px - entry_px) * (1 if is_buy else -1)
        trades.append(dict(entry_i=i, exit_i=exit_bar, pnl=pnl, dir=1 if is_buy else -1, reason=reason))
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
    print(f"Walk-forward cutoff (70%): {df['time'].iloc[cutoff_i]}\n")

    cand_trades = run(ctx, close, high, low, spread, n, early_exit=True)
    real_trades = run(ctx, close, high, low, spread, n, early_exit=False)

    print(f"{'='*92}\nCANDIDATE: shipped Vanguard + early-exit-on-trendline-break rule\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in cand_trades if t["entry_i"] < cutoff_i]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in cand_trades if t["entry_i"] >= cutoff_i])):
        report(label, trs)

    print(f"\n{'='*92}\nFor reference: shipped Vanguard (no early-exit rule)\n{'='*92}")
    for label, trs in (("IN-SAMPLE (first 70%)", [t for t in real_trades if t["entry_i"] < cutoff_i]),
                        ("OUT-OF-SAMPLE (last 30%)", [t for t in real_trades if t["entry_i"] >= cutoff_i])):
        report(label, trs)
