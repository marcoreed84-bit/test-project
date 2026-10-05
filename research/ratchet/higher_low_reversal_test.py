"""
NEW CANDIDATE (2026-10-05, user's own idea, single construction, own K=1):
a price-STRUCTURE reversal pattern, distinct from both of today's earlier
constructions (VWAP-extension, oscillator divergence) - no oscillator
involved at all, just price's own swing lows against each other.

Pattern (long side; the EA family's existing MA periods, 21/50, reused for
consistency - not a new free choice):
  1. BEAR CROSS: 21-EMA crosses below the 50-EMA (downtrend begins).
  2. LOW1: the first confirmed swing-low pivot (5-bar fractal, N=2, same
     definition and no-lookahead confirm-bar convention as
     research/divergence_standalone/divergence_standalone_test.py's
     swing_pivots() - reused via import, not reimplemented) to form after
     the cross.
  3. RETEST: price comes back up and touches/exceeds the 21-EMA (high >=
     ema21) at some bar after LOW1's confirm bar, WHILE STILL CLOSING
     BELOW the 50-EMA (clarified by the user: the whole pattern happens
     below the moving averages - this is a touch of the faster MA from
     below, not a breakout back above the broader downtrend structure).
  4. LOW2: the next confirmed swing-low pivot after the retest bar.
  5. SIGNAL: if LOW2's price is HIGHER than LOW1's price (a genuine higher
     low, not an equal/lower one) -> BUY, filled at the open of the bar
     after LOW2's confirm bar. If LOW2 <= LOW1, the pattern is invalidated;
     wait for a fresh bear cross before trying again (a design choice,
     stated explicitly: this does NOT try to recycle LOW2 as a new LOW1 to
     keep searching within the same downtrend - kept simple on purpose).
  A fresh bear-cross always resets the pattern search, discarding any
  in-progress earlier attempt.

Exit (target picked by the assistant, since none was specified - stated
clearly as a design choice, not tuned): close back above the 50-EMA
(undoes the original bear cross - a natural, construction-tied target,
not an arbitrary price/ATR level) OR a 2.0xATR stop below entry (this
project's plain round default all day) OR a 200-bar timeout safety cap,
whichever comes first.

No mirror (short) side implemented - the user specifically described the
long/bullish-reversal case; mirroring it would double the honest K for a
question that was only asked one way.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/test-project/research/ratchet")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "divergence_standalone"))
import bars as B  # noqa: E402
from divergence_standalone_test import swing_pivots  # noqa: E402

POINT = B.POINT
ATR_STOP = 2.0
MAX_BARS = 200
PIVOT_LR = 2   # left=right=2, the 5-bar fractal swing_pivots() already uses


def find_signals(ema21, ema50, is_low, low, high, close, n):
    """Single forward pass, pattern state machine. Returns a list of
    (signal_confirm_bar,) - the bar LOW2's pivot is confirmed on; the
    caller fills at signal_confirm_bar+1's open."""
    signals = []
    state = "WAIT_CROSS"
    low1_px = None
    low1_confirm = None
    retest_bar = None
    for i in range(PIVOT_LR, n - PIVOT_LR):
        fresh_cross = ema21[i] < ema50[i] and ema21[i - 1] >= ema50[i - 1]
        if fresh_cross:
            state = "WAIT_LOW1"
            low1_px = None
            low1_confirm = None
            retest_bar = None
            continue
        pivot_bar = i - PIVOT_LR   # this iteration CONFIRMS the pivot at pivot_bar
        if pivot_bar < 0:
            continue
        if state == "WAIT_LOW1":
            if is_low[pivot_bar]:
                low1_px = low[pivot_bar]
                low1_confirm = i
                state = "WAIT_RETEST"
        elif state == "WAIT_RETEST":
            # scan every bar (not just confirm bars) after low1's confirm for the
            # retest - must touch the 21-EMA from below WHILE STILL CLOSING below
            # the 50-EMA (user's clarification: the whole pattern stays below the
            # moving averages, this is not a breakout back above the downtrend).
            if i > low1_confirm and high[i] >= ema21[i] and close[i] < ema50[i]:
                retest_bar = i
                state = "WAIT_LOW2"
        elif state == "WAIT_LOW2":
            if pivot_bar > retest_bar and is_low[pivot_bar]:
                low2_px = low[pivot_bar]
                if low2_px > low1_px:
                    signals.append(i)   # i = low2's confirm bar
                state = "WAIT_CROSS"   # either way, pattern cycle ends here
    return signals


def simulate(df, ema50, atr, signals, start_i, end_i, entry_bars_override=None):
    o, h, l, c, sp_pts = (df[k].values for k in ("open", "high", "low", "close", "spread"))
    n = len(df)
    trades = []
    pos = None
    sig_set = set(entry_bars_override) if entry_bars_override is not None else set(s + 1 for s in signals)
    for t in range(start_i, end_i):
        sp = sp_pts[t] * POINT
        if pos is not None:
            hit_sl = l[t] <= pos["sl"]
            crossed_back = c[t] > ema50[t]
            timed_out = (t - pos["entry_i"]) >= MAX_BARS
            if hit_sl:
                trades.append(dict(entry_i=pos["entry_i"], pnl=pos["sl"] - pos["entry"], reason="SL"))
                pos = None
            elif crossed_back:
                px = o[t] if t + 1 >= n else o[min(t + 1, n - 1)]
                trades.append(dict(entry_i=pos["entry_i"], pnl=px - pos["entry"], reason="TARGET"))
                pos = None
            elif timed_out:
                trades.append(dict(entry_i=pos["entry_i"], pnl=c[t] - pos["entry"], reason="TIMEOUT"))
                pos = None
        if pos is None and t in sig_set and start_i <= t < end_i:
            a = atr[t - 1]
            if not (a > 0):
                continue
            entry = o[t] + sp
            sl = entry - ATR_STOP * a
            pos = dict(entry_i=t, entry=entry, sl=sl)
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
    for r in ("TARGET", "SL", "TIMEOUT"):
        cnt = sum(1 for t in trades if t["reason"] == r)
        print(f"      {r}: {cnt} ({100*cnt/n:.1f}%)")


def random_entry_matched(start_i, end_i, n_target, seed):
    rng = np.random.default_rng(seed)
    eligible = np.arange(start_i + 1, end_i)
    chosen = rng.choice(eligible, size=min(n_target, len(eligible)), replace=False)
    return set(int(t) for t in chosen)


if __name__ == "__main__":
    m5 = B.load_m5()
    h, l, c = m5["high"].values, m5["low"].values, m5["close"].values
    ema21, ema50 = B.ema(c, 21), B.ema(c, 50)
    atr = B.wilder_atr(h, l, c, 14)
    is_high, is_low = swing_pivots(h, l, left=PIVOT_LR, right=PIVOT_LR)
    n_bars = len(m5)
    cutoff = int(n_bars * 0.70)
    print(f"Real GOLD M5: {m5['time'].iloc[0]} .. {m5['time'].iloc[-1]}  ({n_bars} bars)")
    print(f"Walk-forward cutoff (70%): {m5['time'].iloc[cutoff]}")
    print(f"Construction: 21/50 EMA bear cross -> swing low1 -> 21-EMA retest -> swing low2 > low1 -> BUY, "
          f"stop={ATR_STOP}xATR, target=close back above 50-EMA, {MAX_BARS}-bar timeout")

    all_signals = find_signals(ema21, ema50, is_low, l, h, c, n_bars)
    print(f"\n  total pattern signals found across full history: {len(all_signals)}")

    print(f"\n{'='*92}\nIN-SAMPLE (first 70%) - transparency only\n{'='*92}")
    is_signals = [s for s in all_signals if s + 1 < cutoff]
    is_trades = simulate(m5, ema50, atr, is_signals, 60, cutoff)
    report("higher-low reversal", is_trades)

    print(f"\n{'='*92}\nOUT-OF-SAMPLE (last 30%, untouched) - this is the verdict\n{'='*92}")
    oos_signals = [s for s in all_signals if s + 1 >= cutoff]
    oos_trades = simulate(m5, ema50, atr, oos_signals, cutoff, n_bars)
    report("higher-low reversal", oos_trades)
    n_oos = len(oos_trades)

    print(f"\n{'='*92}\nRANDOM-TIMING NULL (OOS only), 2000 draws\n{'='*92}")
    if n_oos < 5:
        print(f"  only {n_oos} OOS trades - too few to run a meaningful null")
    else:
        real_pf = pf([t["pnl"] for t in oos_trades])
        print(f"  real: n={n_oos}, PF={real_pf:.3f}")
        NDRAWS = 2000
        null_pfs = []
        for seed in range(NDRAWS):
            chosen = random_entry_matched(cutoff, n_bars, n_oos, seed)
            ntrades = simulate(m5, ema50, atr, [], cutoff, n_bars, entry_bars_override=chosen)
            pnl = [t["pnl"] for t in ntrades]
            null_pfs.append(pf(pnl) if pnl else 0.0)
        null_pfs = np.array(null_pfs)
        p_value = (null_pfs >= real_pf).mean()
        print(f"  null PF: median={np.median(null_pfs):.3f}  p05={np.percentile(null_pfs,5):.3f}  "
              f"p95={np.percentile(null_pfs,95):.3f}")
        print(f"  real PF {real_pf:.3f} sits at the {100*(null_pfs < real_pf).mean():.1f}th percentile of {NDRAWS} draws")
        print(f"  p-value = {p_value:.4f}  {'[SURVIVES p<0.05]' if p_value < 0.05 else '[DOES NOT beat random timing at p<0.05]'}")

    print(f"\n  Honest K for this idea: 1 (single pre-specified construction, long side only, no sweep run).")
