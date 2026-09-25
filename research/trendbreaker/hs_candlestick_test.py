"""
Next Murphy-book idea after MA/VWAP (hs_ma_vwap_test.py, rejected): Chart
Construction ch.3 covers candlesticks (p.37) - genuinely distinct from
everything tested so far this session (H&S itself, trendlines, MAs,
oscillators, volume/VSA). Testing the classic, well-defined candlestick
reversal signal - the ENGULFING pattern - as a confluence filter at the H&S
breakout bar, same eval_filtered() harness as every other confluence test.

Engulfing != the VSA "effort vs result" close-position idea already tested
and rejected (hs_confluence_test.py TEST "effort") - that measured where a
SINGLE bar's close sits within its own range; engulfing is a TWO-bar
reversal construction (today's real body fully contains yesterday's real
body, opposite color) and was never built here before.

1. BEARISH ENGULFING at breakout (top/bearish breakouts only): today red,
   body opens >= yesterday's close and closes <= yesterday's open.
2. BULLISH ENGULFING at breakout (inverse/bullish breakouts only): mirror.
3. Same test but searched over a small window around the breakout bar
   (engulfing often prints 1-2 bars before/after the confirming close),
   not just the exact confirmation bar.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from hs_next_round_test import find_breakouts_full
from hs_confluence_test import eval_filtered, report

np.random.seed(42)
BREAK_TOL = 0.35


def bearish_engulf(o, c, i):
    return c[i - 1] > o[i - 1] and c[i] < o[i] and o[i] >= c[i - 1] and c[i] <= o[i - 1]


def bullish_engulf(o, c, i):
    return c[i - 1] < o[i - 1] and c[i] > o[i] and o[i] <= c[i - 1] and c[i] >= o[i - 1]


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    o15 = df15["open"].values
    breakouts, h, l, c, atr = find_breakouts_full(df15, break_tol=BREAK_TOL)

    print("=" * 95)
    print("BASELINE (current best: pullback 0.75xATR/30bar + break_tol=0.35 + runner 0.5xATR, no confluence)")
    print("=" * 95)
    base_res, base_missed, _ = eval_filtered(breakouts, h, l, c, lambda b: True)
    report(base_res, "no confluence filter", filtered_out=0)

    print("\n" + "=" * 95)
    print("TEST 1: ENGULFING CANDLE EXACTLY AT THE BREAKOUT (CONFIRMATION) BAR")
    print("=" * 95)
    def allow_engulf_exact(b):
        q = b["brk_q"]
        if q < 1:
            return False
        return bearish_engulf(o15, c, q) if b["top"] else bullish_engulf(o15, c, q)
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_engulf_exact)
    report(res, "engulfing exactly at breakout bar", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 2: ENGULFING CANDLE WITHIN +/-2 BARS OF THE BREAKOUT")
    print("=" * 95)
    for window in (1, 2, 3):
        def allow_engulf_window(b, window=window):
            q = b["brk_q"]
            for k in range(max(1, q - window), min(len(c), q + window + 1)):
                if bearish_engulf(o15, c, k) if b["top"] else bullish_engulf(o15, c, k):
                    return True
            return False
        res, missed, fo = eval_filtered(breakouts, h, l, c, allow_engulf_window)
        report(res, f"engulfing within +/-{window} bars of breakout", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 3: ENGULFING AT THE HEAD ITSELF (classic reversal-at-extreme signal)")
    print("=" * 95)
    def allow_engulf_head(b):
        i = b["i_head"]
        if i < 1:
            return False
        for k in range(max(1, i - 1), min(len(c), i + 2)):
            if bearish_engulf(o15, c, k) if b["top"] else bullish_engulf(o15, c, k):
                return True
        return False
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_engulf_head)
    report(res, "engulfing within 1 bar of the head", filtered_out=fo)
