"""
A genuinely different, LIGHTWEIGHT scalp construction - explicitly NOT
gated behind Aurelius's full 5-MA alignment stack (c vs 2400, 21>50>150>600,
slope, crisscross, volume, S&R). User's ask: many more trades than Aurelius
(885 over ~3.5yrs = 0.7/day), short hold, exit constantly for a small FIXED
dollar profit (not ATR-scaled) - "a couple dollars".

Trigger: a fast EMA cross (price crossing a single short EMA, nothing else -
the simplest, fastest, most frequent real signal there is). Two periods
tested (9 and 5) since "fast" is a knob, not a fixed choice. Edge-triggered
(fires once per cross, not every bar price stays on one side).

Exit: FIXED DOLLAR target and stop (1 price unit = $1 at 0.01 lot, same
convention as every other script in this project), not ATR-scaled - because
"a couple dollars, constantly" is literally what was asked for, regardless
of the volatility regime. Same bounded forward-scan / random-direction-
control methodology as battery3.py and scalp_bounce_test.py: both
hypothetical buy/sell outcomes computed per trigger in one pass, so the
control isolates whether the EMA-cross's OWN direction beats a coin flip
at the identical trigger/TP/SL structure.
"""
import sys
sys.path.insert(0, ".")
import numpy as np
import pandas as pd
import engine as E
import sim as S
from engine import POINT, ema
from battery3 import report_outcome_set

MAXHOLD_BARS_DEFAULT = 500


def fixed_tp_sl_outcomes(ctx, triggers, tp_usd, sl_usd, maxhold=MAXHOLD_BARS_DEFAULT):
    """Same construction as battery3.tp_sl_outcomes, but TP/SL are FIXED
    price-unit (=$ at 0.01 lot) distances, not ATR multiples."""
    close, high, low, spread, n = ctx["close"], ctx["high"], ctx["low"], ctx["spread"], ctx["n"]
    out = []
    dropped = 0
    for i, real_dir in triggers:
        fill_i = i + 1
        if fill_i >= n:
            continue
        raw = close[i]
        sc = spread[fill_i] * POINT
        entry_buy, entry_sell = raw + sc, raw - sc
        tp_buy, sl_buy = entry_buy + tp_usd, entry_buy - sl_usd
        tp_sell, sl_sell = entry_sell - tp_usd, entry_sell + sl_usd
        pnl_buy = pnl_sell = None
        for k in range(fill_i, min(fill_i + maxhold, n)):
            if pnl_buy is None:
                hit_tp, hit_sl = high[k] >= tp_buy, low[k] <= sl_buy
                if hit_tp or hit_sl:
                    pnl_buy = (sl_buy - entry_buy) if hit_sl else (tp_buy - entry_buy)
            if pnl_sell is None:
                hit_tp, hit_sl = low[k] <= tp_sell, high[k] >= sl_sell
                if hit_tp or hit_sl:
                    pnl_sell = (entry_sell - sl_sell) if hit_sl else (entry_sell - tp_sell)
            if pnl_buy is not None and pnl_sell is not None:
                break
        if pnl_buy is None or pnl_sell is None:
            dropped += 1
            continue
        out.append((pnl_buy, pnl_sell, i, real_dir))
    return out, dropped


def find_ema_cross_triggers(close, ema_arr):
    above = close > ema_arr
    cross_up = above & ~np.concatenate(([False], above[:-1])) & ~np.isnan(ema_arr)
    cross_dn = (~above) & np.concatenate(([False], above[:-1])) & ~np.isnan(ema_arr)
    trig = [(i, 1.0) for i in np.where(cross_up)[0]] + [(i, -1.0) for i in np.where(cross_dn)[0]]
    trig.sort(key=lambda t: t[0])
    return trig


if __name__ == "__main__":
    df = E.load_m5()
    h4 = E.load_h4()
    ctx = E.build_context(df, h4, params=E.P)
    n = ctx["n"]
    close = ctx["close"]

    base_trades = S.simulate(ctx, params=E.P)
    print("BASELINE (Aurelius's real full system, for reference):", S.stats(base_trades))
    print(f"n_bars={n} (~{n/288:.0f} trading days)\n")

    for period in (9, 5):
        ema_arr = ema(close, period)
        triggers = find_ema_cross_triggers(close, ema_arr)
        print("=" * 70)
        print(f"EMA({period}) CROSS - no trend filter, no alignment stack, no volume/S&R gate")
        print(f"  {len(triggers)} triggers over {n} bars -> {len(triggers)/(n/288):.1f}/day "
              f"({sum(1 for _,d in triggers if d>0)} up-cross, {sum(1 for _,d in triggers if d<0)} down-cross)")

        for maxhold, hold_label in ((6, "~30min"), (24, "~2h")):
            print(f"\n  --- max hold = {maxhold} bars ({hold_label}) ---")
            for tp_usd, sl_usd in ((1.0, 1.0), (2.0, 2.0), (2.0, 1.0), (3.0, 2.0), (3.0, 3.0)):
                out, dropped = fixed_tp_sl_outcomes(ctx, triggers, tp_usd, sl_usd, maxhold=maxhold)
                report_outcome_set(f"tp=${tp_usd} sl=${sl_usd} (dropped={dropped}/{len(triggers)})", out, n)
        print()
