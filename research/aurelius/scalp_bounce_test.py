"""
User's construction: in an established trend, price bouncing off a moving
average, caught for a FEW CANDLES only - not a long hold. Tests this as its
own scalp exit, separate from Aurelius's real trend-following hold, using
Aurelius's own REAL trend+bounce definition as the trigger (not a new one):
  trend  = ctx["aligned_buy"/"aligned_sell"]   (c vs 2400, 21>50>150>600 stack)
  bounce = ctx["pullback_ok_buy"/"pullback_ok_sell"]  (price touched the 50
           MA within pullback_tol_atr in the last pullback_bars bars, and
           has since closed back on the trend side of it)
Both are Aurelius's own real, already-validated arrays - this is not a new
indicator, it's a new EXIT on top of an existing real signal.

Trigger = the EDGE of (trend & bounce), i.e. the first bar it turns true,
not every bar it stays true - otherwise a single multi-bar touch fires the
same "trade" repeatedly. This is what gives the "2-3 times a day" cadence.

Exit: tight scalp TP/SL (both small ATR multiples, not the wide 3xATR swing
stop tested earlier), bounded to a short max hold (a genuinely short hold,
not "eventually"). Same rigor as battery3.py: computes BOTH hypothetical
buy/sell outcomes per trigger in one forward pass, so the random-direction
control isolates whether trading WITH the trend at a bounce beats a random
50/50 direction choice at the exact same trigger bars/TP/SL structure -
separate from whether the trigger/structure alone is profitable.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import engine as E
import sim as S
from battery3 import tp_sl_outcomes, report_outcome_set

if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4, params=E.P)
    n = ctx["n"]

    base_trades = S.simulate(ctx, params=E.P)
    print("BASELINE (Aurelius's real full system, real trend-following hold):", S.stats(base_trades))
    print(f"n_bars={n}\n")

    trend_buy = ctx["aligned_buy"]
    trend_sell = ctx["aligned_sell"]
    bounce_buy = ctx["pullback_ok_buy"]
    bounce_sell = ctx["pullback_ok_sell"]

    sig_buy = trend_buy & bounce_buy
    sig_sell = trend_sell & bounce_sell

    # edge trigger: first bar the condition turns true, not every bar it holds
    trig_buy = sig_buy & ~np.concatenate(([False], sig_buy[:-1]))
    trig_sell = sig_sell & ~np.concatenate(([False], sig_sell[:-1]))

    triggers = [(i, 1.0) for i in np.where(trig_buy)[0]] + [(i, -1.0) for i in np.where(trig_sell)[0]]
    triggers.sort(key=lambda t: t[0])
    print(f"trend+bounce EDGE triggers: {len(triggers)} total "
          f"({sum(1 for _,d in triggers if d>0)} buy, {sum(1 for _,d in triggers if d<0)} sell) "
          f"over {n} bars (~{n/288:.0f} trading days -> "
          f"{len(triggers)/(n/288):.2f}/day)\n")

    print("=" * 70)
    print("SCALP TP/SL grid - tight stop, small target, SHORT max hold "
          "(real 'a few candles' constraint, not 'eventually')")
    for maxhold_bars, hold_label in ((6, "~30min"), (12, "~1h")):
        print(f"\n--- max hold = {maxhold_bars} bars ({hold_label}) ---")
        for tp_atr, sl_atr in ((0.3, 0.3), (0.3, 0.5), (0.5, 0.5), (0.5, 0.75)):
            out, dropped = tp_sl_outcomes(ctx, triggers, tp_atr, sl_atr, maxhold=maxhold_bars)
            report_outcome_set(f"tp={tp_atr}xATR sl={sl_atr}xATR (dropped={dropped}/{len(triggers)})", out, n)
