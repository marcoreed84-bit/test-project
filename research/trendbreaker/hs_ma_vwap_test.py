"""
User: "you have also tested head and shoulders against moving averages,
vwap and so on" - no, not yet. hs_confluence_test.py covered RSI (shipped),
RSI divergence (rejected), Stochastic (no benefit), VSA effort-vs-result
(rejected), Savin/Weller/Zvingelis R6/R7/R9 (neutral), trendline confluence
(untestable with power). MA/VWAP trend-context filters were never run.
Filling that gap now, same real construction (single-position-sequenced,
pullback 0.75xATR/30bar + BREAK_TOL_ATR=0.35 + 0.5xATR trailing runner as
the base to filter on top of), same eval_filtered() harness.

Three real tests, all as an ENTRY FILTER (only take the trade when the
condition also holds, exit logic unchanged):

1. MA TREND SIDE: price on the "right" side of a longer MA at the breakout
   bar - close < MA for a top/bearish breakout, close > MA for an
   inverse/bullish breakout (classic "trade the break WITH the dominant
   trend" filter). EMA(50) and EMA(200), both real MT5 iMA(MODE_EMA) ports
   already used elsewhere this session.
2. MA SLOPE: the same MA sloping in the breakout's own direction (falling
   for top, rising for inverse) at the breakout bar - a distinct condition
   from #1 (side vs direction of travel).
3. SESSION VWAP SIDE: price on the "right" side of the real SessionVWAP()
   (session_vwap() in research/aurelius/engine.py, already validated
   against Aurelius_EA.mq5's own SessionVWAP()) at the breakout bar - same
   logic as #1 but VWAP instead of a fixed-period MA.
"""
import sys
sys.path.insert(0, "/home/user/test-project/research/aurelius")
sys.path.insert(0, "/home/user/test-project/research/trendbreaker")
import numpy as np
import engine as E
from engine import ema, session_vwap
from hs_next_round_test import find_breakouts_full
from hs_confluence_test import eval_filtered, report

np.random.seed(42)
BREAK_TOL = 0.35


if __name__ == "__main__":
    df5 = E.load_m5()
    df15 = E.resample_m15_from_m5(df5)
    breakouts, h, l, c, atr = find_breakouts_full(df15, break_tol=BREAK_TOL)

    print("=" * 95)
    print("BASELINE (current best: pullback 0.75xATR/30bar + break_tol=0.35 + runner 0.5xATR, no confluence)")
    print("=" * 95)
    base_res, base_missed, _ = eval_filtered(breakouts, h, l, c, lambda b: True)
    report(base_res, "no confluence filter", filtered_out=0)

    ema50 = ema(c, 50)
    ema200 = ema(c, 200)
    vwap = session_vwap(df15)

    print("\n" + "=" * 95)
    print("TEST 1: MA TREND SIDE (close on the breakout's own side of the MA at the breakout bar)")
    print("=" * 95)
    for name, m in (("EMA50", ema50), ("EMA200", ema200)):
        def allow_side(b, m=m):
            mv = m[b["brk_q"]]
            if np.isnan(mv):
                return False
            return (c[b["brk_q"]] < mv) if b["top"] else (c[b["brk_q"]] > mv)
        res, missed, fo = eval_filtered(breakouts, h, l, c, allow_side)
        report(res, f"{name} trend side", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 2: MA SLOPE (MA itself sloping in the breakout's direction at the breakout bar)")
    print("=" * 95)
    for name, m in (("EMA50", ema50), ("EMA200", ema200)):
        for lookback in (10, 20):
            def allow_slope(b, m=m, lookback=lookback):
                q = b["brk_q"]
                if q - lookback < 0 or np.isnan(m[q]) or np.isnan(m[q - lookback]):
                    return False
                slope = m[q] - m[q - lookback]
                return (slope < 0) if b["top"] else (slope > 0)
            res, missed, fo = eval_filtered(breakouts, h, l, c, allow_slope)
            report(res, f"{name} slope (lookback {lookback})", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 3: SESSION VWAP SIDE (close on the breakout's own side of session VWAP)")
    print("=" * 95)
    def allow_vwap(b):
        vv = vwap[b["brk_q"]]
        if np.isnan(vv):
            return False
        return (c[b["brk_q"]] < vv) if b["top"] else (c[b["brk_q"]] > vv)
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_vwap)
    report(res, "session VWAP side", filtered_out=fo)

    print("\n" + "=" * 95)
    print("TEST 4: MA + VWAP AGREE (both EMA50 side and VWAP side confirm)")
    print("=" * 95)
    def allow_both(b):
        mv = ema50[b["brk_q"]]
        vv = vwap[b["brk_q"]]
        if np.isnan(mv) or np.isnan(vv):
            return False
        top = b["top"]
        side_ma = (c[b["brk_q"]] < mv) if top else (c[b["brk_q"]] > mv)
        side_vw = (c[b["brk_q"]] < vv) if top else (c[b["brk_q"]] > vv)
        return side_ma and side_vw
    res, missed, fo = eval_filtered(breakouts, h, l, c, allow_both)
    report(res, "EMA50 + VWAP both agree", filtered_out=fo)
